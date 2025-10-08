from __future__ import annotations
import os
from datetime import datetime, timedelta
from typing import Iterable
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.archivo import Archivo
from models.archivo_proyeccion import ArchivoProyeccion
from models.proyeccion import Proyeccion
from models.proyeccion_linea import ProyeccionLinea
from config.settings import settings

# Estructura canónica que esperamos extraer de archivo
class Line:
    def __init__(self, fecha_plan, pp_g, sob_pct_linea, incremento_g_sem=None, cosecha_flag=False, retiro_org_m2=None, edad_dias=None, semana_idx=None, nota=None):
        self.fecha_plan = fecha_plan
        self.pp_g = pp_g
        self.sob_pct_linea = sob_pct_linea
        self.incremento_g_sem = incremento_g_sem
        self.cosecha_flag = bool(cosecha_flag)
        self.retiro_org_m2 = retiro_org_m2
        self.edad_dias = edad_dias
        self.semana_idx = semana_idx
        self.nota = nota

def _parse_local(archivo: Archivo) -> list[Line]:
    """
    Parser local mínimo:
    - CSV o XLSX con columnas: fecha_plan, pp_g, sob_pct_linea
      opcionales: incremento_g_sem, cosecha_flag, retiro_org_m2, edad_dias, semana_idx, nota
    - Validaciones: fechas válidas; pp_g>=0; sob in [0,100]; saltos de 7 días (si hay 2+ filas)
    """
    path = archivo.storage_path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="file_blob_not_found")

    ext = os.path.splitext(path)[1].lower()
    try:
        import pandas as pd
        if ext in [".csv"]:
            df = pd.read_csv(path)
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(path)
        elif ext in [".pdf"]:
            # No parseamos PDF localmente en S2
            raise HTTPException(status_code=415, detail="pdf_parsing_not_supported_in_sprint2")
        else:
            raise HTTPException(status_code=415, detail="unsupported_extension")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"ingest_parse_error: {e}")

    required = {"fecha_plan", "pp_g", "sob_pct_linea"}
    missing = required - set(df.columns.map(str))
    if missing:
        raise HTTPException(status_code=422, detail=f"missing_required_columns: {sorted(missing)}")

    # Normaliza
    df = df.copy()
    df["fecha_plan"] = pd.to_datetime(df["fecha_plan"]).dt.date
    for col in ["pp_g", "sob_pct_linea", "incremento_g_sem", "retiro_org_m2", "edad_dias", "semana_idx"]:
        if col in df.columns:
            # deja NaN para opcionales
            pass

    # Orden por fecha
    df = df.sort_values("fecha_plan")

    # Validaciones numéricas
    if (df["pp_g"] < 0).any():
        raise HTTPException(status_code=422, detail="invalid_pp_g_negative")
    if (df["sob_pct_linea"] < 0).any() or (df["sob_pct_linea"] > 100).any():
        raise HTTPException(status_code=422, detail="invalid_sob_out_of_range")

    # Validar saltos de 7 días si hay varias filas
    fechas = df["fecha_plan"].tolist()
    if len(fechas) >= 2:
        for prev, nxt in zip(fechas, fechas[1:]):
            delta = (nxt - prev).days
            if delta != 7:
                raise HTTPException(status_code=422, detail=f"invalid_week_spacing: expected 7, got {delta} between {prev} and {nxt}")

    # Derivar semana_idx si no viene
    if "semana_idx" not in df.columns:
        df["semana_idx"] = range(0, len(df))
    else:
        df["semana_idx"] = df["semana_idx"].fillna(method="ffill").fillna(0).astype(int)

    # Derivar edad_dias si no viene (desde la primera fecha = edad 0)
    if "edad_dias" not in df.columns:
        base = df["fecha_plan"].iloc[0]
        df["edad_dias"] = df["fecha_plan"].apply(lambda d: (d - base).days)

    # Bandera cosecha_flag
    if "cosecha_flag" in df.columns:
        df["cosecha_flag"] = df["cosecha_flag"].astype(bool)
    else:
        df["cosecha_flag"] = False

    lines: list[Line] = []
    for _, row in df.iterrows():
        lines.append(
            Line(
                fecha_plan=row["fecha_plan"],
                pp_g=float(row["pp_g"]),
                sob_pct_linea=float(row["sob_pct_linea"]),
                incremento_g_sem=float(row["incremento_g_sem"]) if "incremento_g_sem" in df.columns and not pd.isna(row["incremento_g_sem"]) else None,
                cosecha_flag=bool(row["cosecha_flag"]),
                retiro_org_m2=float(row["retiro_org_m2"]) if "retiro_org_m2" in df.columns and not pd.isna(row["retiro_org_m2"]) else None,
                edad_dias=int(row["edad_dias"]) if "edad_dias" in df.columns and not pd.isna(row["edad_dias"]) else None,
                semana_idx=int(row["semana_idx"]) if "semana_idx" in df.columns and not pd.isna(row["semana_idx"]) else None,
                nota=str(row["nota"]) if "nota" in df.columns and not pd.isna(row.get("nota")) else None,
            )
        )
    return lines

def _next_version_for_cycle(db: Session, ciclo_id: int) -> str:
    # v1, v2, ... por ciclo
    q = db.query(func.count(Proyeccion.proyeccion_id)).filter(Proyeccion.ciclo_id == ciclo_id).scalar()
    return f"v{(q or 0) + 1}"

def ingest_draft_from_archivo(
    db: Session,
    *,
    ciclo_id: int,
    archivo_id: int,
    creada_por: int | None,
    source_type: str = "archivo",
    source_ref: str | None = None,
) -> Proyeccion:
    # archivo debe existir
    arch = db.get(Archivo, archivo_id)
    if not arch:
        raise HTTPException(status_code=404, detail="archivo_not_found")

    # Validar que NO exista borrador en el ciclo (BD también protege)
    existing_draft = (
        db.query(Proyeccion)
        .filter(Proyeccion.ciclo_id == ciclo_id, Proyeccion.status == "b")
        .first()
    )
    if existing_draft:
        raise HTTPException(status_code=409, detail="draft_projection_already_exists")

    # Parseo local (CSV/XLSX). PDF no en S2.
    lines = _parse_local(arch)
    if not lines:
        raise HTTPException(status_code=422, detail="ingest_no_lines")

    # Crea proyección borrador
    version = _next_version_for_cycle(db, ciclo_id)
    proy = Proyeccion(
        ciclo_id=ciclo_id,
        version=version,
        descripcion="Borrador generado desde archivo",
        status="b",
        is_current=False,
        creada_por=creada_por,
        source_type=source_type,
        source_ref=source_ref or arch.checksum,
    )
    db.add(proy)
    db.flush()  # obtiene proyeccion_id

    # Inserta líneas (bulk)
    bulk_rows = []
    for l in lines:
        bulk_rows.append(
            ProyeccionLinea(
                proyeccion_id=proy.proyeccion_id,
                edad_dias=l.edad_dias if l.edad_dias is not None else (l.semana_idx or 0) * 7,
                semana_idx=l.semana_idx if l.semana_idx is not None else 0,
                fecha_plan=l.fecha_plan,
                pp_g=l.pp_g,
                incremento_g_sem=l.incremento_g_sem,
                sob_pct_linea=l.sob_pct_linea,
                cosecha_flag=l.cosecha_flag,
                retiro_org_m2=l.retiro_org_m2,
                nota=l.nota,
            )
        )
    db.bulk_save_objects(bulk_rows)

    # Vincula archivo como insumo_calculo
    ap = ArchivoProyeccion(
        archivo_id=archivo_id,
        proyeccion_id=proy.proyeccion_id,
        proposito="insumo_calculo",
        notas="Archivo fuente de la proyección borrador",
    )
    db.add(ap)

    db.commit()
    db.refresh(proy)
    return proy
