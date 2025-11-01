# utils/permissions.py
"""
Sistema de autorización basado en roles y scopes.

Basado en: docs/sistema_roles_permisos.md

Arquitectura:
- Admin Global (is_admin_global=True): Acceso total a todo
- Roles en granjas: Admin Granja, Biólogo, Operador, Consultor
- Scopes: Permisos granulares (por defecto + opcionales)
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user import Usuario, UsuarioGranja
from models.role import Rol


# ============================================================================
# Constantes de Roles (deben coincidir con BD)
# ============================================================================

class RoleNames:
    """Nombres de roles del sistema (deben coincidir exactamente con tabla rol)"""
    ADMIN_GRANJA = "Admin granja"
    BIOLOGO = "Biologo"
    OPERADOR = "Operador"
    CONSULTOR = "Consultor"


# ============================================================================
# Catálogo de Scopes Disponibles
# ============================================================================

class Scopes:
    """
    Catálogo completo de scopes disponibles en el sistema.

    Nomenclatura:
    - gestionar_* : Crear, editar, eliminar
    - ver_* : Solo lectura
    - crear_* : Solo crear
    """
    # Infraestructura
    GESTIONAR_ESTANQUES = "gestionar_estanques"
    GESTIONAR_CICLOS = "gestionar_ciclos"

    # Operaciones técnicas
    GESTIONAR_PROYECCIONES = "gestionar_proyecciones"
    GESTIONAR_SIEMBRAS = "gestionar_siembras"
    GESTIONAR_COSECHAS = "gestionar_cosechas"
    GESTIONAR_BIOMETRIAS = "gestionar_biometrias"

    # Tareas
    GESTIONAR_TAREAS = "gestionar_tareas"
    CREAR_TAREAS_TECNICAS = "crear_tareas_tecnicas"
    VER_TAREAS_ASIGNADAS = "ver_tareas_asignadas"
    COMPLETAR_TAREAS_ASIGNADAS = "completar_tareas_asignadas"

    # Analytics y reportes
    VER_ANALYTICS = "ver_analytics"
    VER_DATOS_BASICOS = "ver_datos_basicos"
    VER_TODO = "ver_todo"

    # Gestión de usuarios (scope OPCIONAL más importante)
    GESTION_USUARIOS = "gestion_usuarios"

    # Futuros (V2)
    # EXPORTAR_REPORTES = "exportar_reportes"
    # CONFIGURAR_ALERTAS = "configurar_alertas"
    # VER_COSTOS = "ver_costos"
    # EDITAR_PARAMETROS = "editar_parametros"


# ============================================================================
# Scopes por Defecto según Rol
# ============================================================================

DEFAULT_SCOPES_BY_ROLE = {
    RoleNames.ADMIN_GRANJA: [
        Scopes.GESTIONAR_ESTANQUES,
        Scopes.GESTIONAR_CICLOS,
        Scopes.GESTIONAR_PROYECCIONES,
        Scopes.GESTIONAR_SIEMBRAS,
        Scopes.GESTIONAR_COSECHAS,
        Scopes.GESTIONAR_BIOMETRIAS,
        Scopes.GESTIONAR_TAREAS,
        Scopes.VER_ANALYTICS,
        # Scopes opcionales se agregan manualmente:
        # - gestion_usuarios
    ],
    RoleNames.BIOLOGO: [
        Scopes.GESTIONAR_PROYECCIONES,
        Scopes.GESTIONAR_SIEMBRAS,
        Scopes.GESTIONAR_COSECHAS,
        Scopes.GESTIONAR_BIOMETRIAS,
        Scopes.CREAR_TAREAS_TECNICAS,
        Scopes.VER_ANALYTICS,
        # Scopes opcionales (futuro):
        # - configurar_alertas
    ],
    RoleNames.OPERADOR: [
        Scopes.VER_TAREAS_ASIGNADAS,
        Scopes.COMPLETAR_TAREAS_ASIGNADAS,
        Scopes.VER_DATOS_BASICOS,
        # No tiene scopes opcionales definidos aún
    ],
    RoleNames.CONSULTOR: [
        Scopes.VER_TODO,
        # Solo lectura, no tiene scopes opcionales
    ],
}

# ============================================================================
# Scopes Opcionales por Rol (pueden agregarse manualmente)
# ============================================================================

OPTIONAL_SCOPES_BY_ROLE = {
    RoleNames.ADMIN_GRANJA: [
        Scopes.GESTION_USUARIOS,  # ← Scope más importante
        # Futuros:
        # Scopes.EXPORTAR_REPORTES,
        # Scopes.VER_COSTOS,
    ],
    RoleNames.BIOLOGO: [
        # Futuros:
        # Scopes.CONFIGURAR_ALERTAS,
        # Scopes.EDITAR_PARAMETROS,
    ],
    RoleNames.OPERADOR: [
        # Sin scopes opcionales por ahora
    ],
    RoleNames.CONSULTOR: [
        # Sin scopes opcionales (solo lectura)
    ],
}


# ============================================================================
# Validación Base (ya existente, MANTENER)
# ============================================================================

def ensure_user_in_farm_or_admin(
        db: Session,
        user_id: int,
        granja_id: int,
        is_admin_global: bool
):
    """
    Validar que usuario pertenezca a la granja o sea admin global.

    Esta es la validación BÁSICA que se usa en TODOS los endpoints.
    Valida membership, no permisos específicos.

    Args:
        db: Sesión de BD
        user_id: ID del usuario
        granja_id: ID de la granja
        is_admin_global: Si el usuario es admin global

    Raises:
        HTTPException 403: Si no pertenece a la granja
    """
    if is_admin_global:
        return

    ug = (
        db.query(UsuarioGranja)
        .filter(
            UsuarioGranja.usuario_id == user_id,
            UsuarioGranja.granja_id == granja_id,
            UsuarioGranja.status == "a"
        )
        .first()
    )

    if not ug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No pertenece a la granja"
        )


# ============================================================================
# Funciones de Consulta de Permisos
# ============================================================================

def get_user_role_and_scopes(
        db: Session,
        usuario_id: int,
        granja_id: int
) -> tuple[str | None, list[str]]:
    """
    Obtener rol y scopes del usuario en una granja específica.

    Args:
        db: Sesión de BD
        usuario_id: ID del usuario
        granja_id: ID de la granja

    Returns:
        (rol_nombre, scopes) donde:
        - rol_nombre: Nombre del rol (ej: "Admin granja") o None si no pertenece
        - scopes: Lista de scopes (permisos) o [] si no tiene

    Nota:
        Admin Global retorna rol especial con todos los scopes disponibles
    """
    # Admin Global tiene todos los permisos en todas las granjas
    user = db.get(Usuario, usuario_id)
    if user and user.is_admin_global:
        # Admin Global tiene TODOS los scopes disponibles
        all_scopes = [
            Scopes.GESTIONAR_ESTANQUES,
            Scopes.GESTIONAR_CICLOS,
            Scopes.GESTIONAR_PROYECCIONES,
            Scopes.GESTIONAR_SIEMBRAS,
            Scopes.GESTIONAR_COSECHAS,
            Scopes.GESTIONAR_BIOMETRIAS,
            Scopes.GESTIONAR_TAREAS,
            Scopes.VER_ANALYTICS,
            Scopes.GESTION_USUARIOS,
            Scopes.VER_TODO,
        ]
        return ("Admin Global", all_scopes)

    # Buscar en usuario_granja
    ug = (
        db.query(UsuarioGranja, Rol)
        .join(Rol, UsuarioGranja.rol_id == Rol.rol_id)
        .filter(
            UsuarioGranja.usuario_id == usuario_id,
            UsuarioGranja.granja_id == granja_id,
            UsuarioGranja.status == "a"
        )
        .first()
    )

    if not ug:
        return (None, [])

    usuario_granja, rol = ug
    return (rol.nombre, usuario_granja.scopes or [])


def user_has_scope(
        db: Session,
        usuario_id: int,
        granja_id: int,
        required_scope: str,
        is_admin_global: bool = False
) -> bool:
    """
    Verificar si usuario tiene un scope específico en una granja.

    Args:
        db: Sesión de BD
        usuario_id: ID del usuario
        granja_id: ID de la granja
        required_scope: Scope requerido (ej: "gestion_usuarios")
        is_admin_global: Si el usuario es admin global (optimización)

    Returns:
        True si tiene el scope, False si no
    """
    # Admin Global siempre tiene todos los scopes
    if is_admin_global:
        return True

    rol_nombre, scopes = get_user_role_and_scopes(db, usuario_id, granja_id)

    if not rol_nombre:
        return False

    return required_scope in scopes


def user_has_any_scope(
        db: Session,
        usuario_id: int,
        granja_id: int,
        required_scopes: list[str],
        is_admin_global: bool = False
) -> bool:
    """
    Verificar si usuario tiene AL MENOS UNO de los scopes requeridos.

    Args:
        db: Sesión de BD
        usuario_id: ID del usuario
        granja_id: ID de la granja
        required_scopes: Lista de scopes (con tener 1 es suficiente)
        is_admin_global: Si el usuario es admin global

    Returns:
        True si tiene al menos uno de los scopes
    """
    if is_admin_global:
        return True

    rol_nombre, scopes = get_user_role_and_scopes(db, usuario_id, granja_id)

    if not rol_nombre:
        return False

    return any(scope in scopes for scope in required_scopes)


def user_has_all_scopes(
        db: Session,
        usuario_id: int,
        granja_id: int,
        required_scopes: list[str],
        is_admin_global: bool = False
) -> bool:
    """
    Verificar si usuario tiene TODOS los scopes requeridos.

    Args:
        db: Sesión de BD
        usuario_id: ID del usuario
        granja_id: ID de la granja
        required_scopes: Lista de scopes (debe tener todos)
        is_admin_global: Si el usuario es admin global

    Returns:
        True si tiene todos los scopes
    """
    if is_admin_global:
        return True

    rol_nombre, scopes = get_user_role_and_scopes(db, usuario_id, granja_id)

    if not rol_nombre:
        return False

    return all(scope in scopes for scope in required_scopes)


# ============================================================================
# Funciones de Validación (lanzan excepciones)
# ============================================================================

def ensure_user_has_scope(
        db: Session,
        usuario_id: int,
        granja_id: int,
        required_scope: str,
        is_admin_global: bool = False
):
    """
    Validar que usuario tenga un scope específico (lanza excepción si no).

    Args:
        db: Sesión de BD
        usuario_id: ID del usuario
        granja_id: ID de la granja
        required_scope: Scope requerido
        is_admin_global: Si el usuario es admin global

    Raises:
        HTTPException 403: Si no tiene el scope
    """
    if not user_has_scope(db, usuario_id, granja_id, required_scope, is_admin_global):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permiso denegado. Scope requerido: {required_scope}"
        )


def ensure_user_has_any_scope(
        db: Session,
        usuario_id: int,
        granja_id: int,
        required_scopes: list[str],
        is_admin_global: bool = False
):
    """
    Validar que usuario tenga AL MENOS UNO de los scopes (lanza excepción si no).

    Args:
        db: Sesión de BD
        usuario_id: ID del usuario
        granja_id: ID de la granja
        required_scopes: Lista de scopes aceptables
        is_admin_global: Si el usuario es admin global

    Raises:
        HTTPException 403: Si no tiene ninguno de los scopes
    """
    if not user_has_any_scope(db, usuario_id, granja_id, required_scopes, is_admin_global):
        scopes_str = ", ".join(required_scopes)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permiso denegado. Requiere uno de: {scopes_str}"
        )


# ============================================================================
# Helpers Específicos (para casos comunes)
# ============================================================================

def ensure_can_manage_users(db: Session, current_user: Usuario, granja_id: int):
    """
    Validar que usuario puede gestionar usuarios en una granja.

    Requiere:
    - Admin Global, O
    - Scope 'gestion_usuarios'

    Args:
        db: Sesión de BD
        current_user: Usuario autenticado
        granja_id: ID de la granja

    Raises:
        HTTPException 403: Si no tiene permiso
    """
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        granja_id,
        Scopes.GESTION_USUARIOS,
        current_user.is_admin_global
    )


def ensure_can_manage_tasks(db: Session, current_user: Usuario, granja_id: int):
    """
    Validar que usuario puede gestionar tareas.

    Requiere:
    - Admin Global, O
    - Scope 'gestionar_tareas', O
    - Scope 'crear_tareas_tecnicas'
    """
    ensure_user_has_any_scope(
        db,
        current_user.usuario_id,
        granja_id,
        [Scopes.GESTIONAR_TAREAS, Scopes.CREAR_TAREAS_TECNICAS],
        current_user.is_admin_global
    )


def ensure_can_manage_biometries(db: Session, current_user: Usuario, granja_id: int):
    """
    Validar que usuario puede gestionar biometrías.

    Requiere:
    - Admin Global, O
    - Scope 'gestionar_biometrias'
    """
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        granja_id,
        Scopes.GESTIONAR_BIOMETRIAS,
        current_user.is_admin_global
    )


def ensure_can_manage_cycles(db: Session, current_user: Usuario, granja_id: int):
    """
    Validar que usuario puede gestionar ciclos.

    Requiere:
    - Admin Global, O
    - Scope 'gestionar_ciclos'
    """
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        granja_id,
        Scopes.GESTIONAR_CICLOS,
        current_user.is_admin_global
    )


def ensure_can_manage_projections(db: Session, current_user: Usuario, granja_id: int):
    """
    Validar que usuario puede gestionar proyecciones.

    Requiere:
    - Admin Global, O
    - Scope 'gestionar_proyecciones'
    """
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        granja_id,
        Scopes.GESTIONAR_PROYECCIONES,
        current_user.is_admin_global
    )


def user_is_read_only(db: Session, usuario_id: int, granja_id: int) -> bool:
    """
    Verificar si usuario es solo lectura (Consultor).

    Args:
        db: Sesión de BD
        usuario_id: ID del usuario
        granja_id: ID de la granja

    Returns:
        True si es Consultor (solo lectura)
    """
    rol_nombre, _ = get_user_role_and_scopes(db, usuario_id, granja_id)
    return rol_nombre == RoleNames.CONSULTOR


# ============================================================================
# Funciones de Gestión de Scopes
# ============================================================================

def get_default_scopes_for_role(rol_nombre: str) -> list[str]:
    """
    Obtener scopes por defecto para un rol.

    Args:
        rol_nombre: Nombre del rol

    Returns:
        Lista de scopes por defecto
    """
    return DEFAULT_SCOPES_BY_ROLE.get(rol_nombre, []).copy()


def get_optional_scopes_for_role(rol_nombre: str) -> list[str]:
    """
    Obtener scopes opcionales disponibles para un rol.

    Args:
        rol_nombre: Nombre del rol

    Returns:
        Lista de scopes opcionales
    """
    return OPTIONAL_SCOPES_BY_ROLE.get(rol_nombre, []).copy()


def validate_scopes_for_role(rol_nombre: str, scopes_to_add: list[str]) -> bool:
    """
    Validar que los scopes sean válidos para un rol.

    Args:
        rol_nombre: Nombre del rol
        scopes_to_add: Lista de scopes a validar

    Returns:
        True si todos los scopes son válidos

    Raises:
        ValueError: Si algún scope no es válido para el rol
    """
    optional_scopes = OPTIONAL_SCOPES_BY_ROLE.get(rol_nombre, [])

    for scope in scopes_to_add:
        if scope not in optional_scopes:
            raise ValueError(
                f"Scope '{scope}' no es válido para el rol '{rol_nombre}'. "
                f"Scopes opcionales disponibles: {optional_scopes}"
            )

    return True