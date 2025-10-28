from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from models.user import UsuarioGranja

def ensure_user_in_farm_or_admin(db: Session, user_id: int, granja_id: int, is_admin_global: bool):
    if is_admin_global:
        return
    ug = (
        db.query(UsuarioGranja)
        .filter(UsuarioGranja.usuario_id == user_id,
                UsuarioGranja.granja_id == granja_id,
                UsuarioGranja.status == "a")
        .first()
    )
    if not ug:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No pertenece a la granja")
