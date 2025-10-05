from enum import Enum

# =====================================================
# 🔐 USUARIOS / ACCESOS
# =====================================================
class UsuarioEstadoEnum(str, Enum):
    a = "a"  # Activo
    i = "i"  # Inactivo


# =====================================================
# 🧱 INFRAESTRUCTURA Y ESTANQUES
# =====================================================
class EstanqueStatusEnum(str, Enum):
    i = "i"  # Inactivo
    a = "a"  # Activo
    c = "c"  # Cerrado
    m = "m"  # Mantenimiento


# =====================================================
# 📋 TAREAS
# =====================================================
class TareaPrioridadEnum(str, Enum):
    b = "b"  # Baja
    m = "m"  # Media
    a = "a"  # Alta


class TareaEstadoEnum(str, Enum):
    p = "p"  # Pendiente
    e = "e"  # En ejecución
    c = "c"  # Completada
    x = "x"  # Cancelada


# =====================================================
# 🔁 CICLOS
# =====================================================
class CicloEstadoEnum(str, Enum):
    a = "a"  # Activo
    t = "t"  # Terminado


# =====================================================
# 📊 PROYECCIONES
# =====================================================
class ProyeccionStatusEnum(str, Enum):
    b = "b"  # Borrador
    p = "p"  # Publicada
    r = "r"  # Revisada
    x = "x"  # Cancelada


class ProyeccionSourceEnum(str, Enum):
    auto = "auto"          # Generada automáticamente
    archivo = "archivo"    # Proveniente de un archivo de proyección
    reforecast = "reforecast"  # Recalculada según datos reales


class ArchivoPropositoProyeccionEnum(str, Enum):
    insumo_calculo = "insumo_calculo"
    respaldo = "respaldo"
    reporte_publicado = "reporte_publicado"
    otro = "otro"


# =====================================================
# 🌱 SIEMBRAS
# =====================================================
class SiembraEstadoEnum(str, Enum):
    p = "p"  # Planeada
    f = "f"  # Finalizada


# =====================================================
# 🌾 COSECHAS
# =====================================================
class CosechaTipoEnum(str, Enum):
    p = "p"  # Parcial
    f = "f"  # Final


class CosechaEstadoEnum(str, Enum):
    p = "p"  # Pendiente
    r = "r"  # En curso
    x = "x"  # Cancelada


class CosechaEstadoDetEnum(str, Enum):
    p = "p"  # Pendiente
    c = "c"  # Completada
    x = "x"  # Cancelada


# =====================================================
# 📈 BIOMETRÍAS / SOB
# =====================================================
class SobFuenteEnum(str, Enum):
    operativa_actual = "operativa_actual"
    ajuste_manual = "ajuste_manual"
    reforecast = "reforecast"


# =====================================================
# 🔽 UTILIDADES
# =====================================================
class SortOrderEnum(str, Enum):
    asc = "asc"
    desc = "desc"
