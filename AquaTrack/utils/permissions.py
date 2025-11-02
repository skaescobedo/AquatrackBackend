"""
Sistema de autorización basado en roles y scopes.

VERSIÓN DEFINITIVA - Sin funcionalidades no implementadas

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
# Catálogo de Scopes Disponibles (GRANULARIZADOS Y REALES)
# ============================================================================

class Scopes:
    """
    Catálogo completo de scopes disponibles en el sistema.

    Solo incluye funcionalidades IMPLEMENTADAS.

    Nomenclatura:
    - ver_* : Solo lectura
    - crear_* : Solo crear
    - editar_* : Solo editar
    - eliminar_* : Solo eliminar
    - gestionar_* : Crear + Editar + Eliminar (scope completo)
    """

    # ========================================================================
    # INFRAESTRUCTURA
    # ========================================================================

    # Estanques
    CREAR_ESTANQUES = "crear_estanques"
    EDITAR_ESTANQUES = "editar_estanques"
    ELIMINAR_ESTANQUES = "eliminar_estanques"
    GESTIONAR_ESTANQUES = "gestionar_estanques"

    # Ciclos
    CREAR_CICLOS = "crear_ciclos"
    EDITAR_CICLOS = "editar_ciclos"
    CERRAR_CICLOS = "cerrar_ciclos"  # Operación crítica
    GESTIONAR_CICLOS = "gestionar_ciclos"

    # ========================================================================
    # OPERACIONES TÉCNICAS
    # ========================================================================

    # Proyecciones
    VER_PROYECCIONES = "ver_proyecciones"  # ← NUEVO: Lectura ahora requiere scope
    CREAR_PROYECCIONES = "crear_proyecciones"
    EDITAR_PROYECCIONES = "editar_proyecciones"
    ELIMINAR_PROYECCIONES = "eliminar_proyecciones"
    DUPLICAR_PROYECCIONES = "duplicar_proyecciones"
    GESTIONAR_PROYECCIONES = "gestionar_proyecciones"

    # Siembras
    CREAR_SIEMBRAS = "crear_siembras"
    EDITAR_SIEMBRAS = "editar_siembras"
    ELIMINAR_SIEMBRAS = "eliminar_siembras"
    GESTIONAR_SIEMBRAS = "gestionar_siembras"

    # Cosechas
    CREAR_COSECHAS = "crear_cosechas"
    EDITAR_COSECHAS = "editar_cosechas"
    ELIMINAR_COSECHAS = "eliminar_cosechas"
    GESTIONAR_COSECHAS = "gestionar_cosechas"

    # Biometrías
    CREAR_BIOMETRIAS = "crear_biometrias"
    EDITAR_BIOMETRIAS = "editar_biometrias"
    ELIMINAR_BIOMETRIAS = "eliminar_biometrias"
    GESTIONAR_BIOMETRIAS = "gestionar_biometrias"

    # ========================================================================
    # TAREAS
    # ========================================================================

    VER_TODAS_TAREAS = "ver_todas_tareas"  # Ver todas las tareas de la granja
    VER_MIS_TAREAS = "ver_mis_tareas"  # Ver solo mis tareas (Operador)

    CREAR_TAREAS = "crear_tareas"
    EDITAR_TAREAS = "editar_tareas"
    ELIMINAR_TAREAS = "eliminar_tareas"
    ASIGNAR_TAREAS = "asignar_tareas"
    CAMBIAR_ESTADO_TAREAS = "cambiar_estado_tareas"
    DUPLICAR_TAREAS = "duplicar_tareas"
    GESTIONAR_TAREAS = "gestionar_tareas"  # Bundle completo

    COMPLETAR_MIS_TAREAS = "completar_mis_tareas"  # Marcar como completada (Operador)

    # ========================================================================
    # ANALYTICS Y REPORTES
    # ========================================================================

    VER_ANALYTICS = "ver_analytics"  # Dashboards (ciclo, estanque, stats)
    VER_DATOS_BASICOS = "ver_datos_basicos"  # Info básica (Operador)
    VER_TODO = "ver_todo"  # Lectura completa (Consultor)

    # ========================================================================
    # GESTIÓN DE USUARIOS
    # ========================================================================

    VER_USUARIOS_GRANJA = "ver_usuarios_granja"  # Ver lista de usuarios
    GESTIONAR_USUARIOS_GRANJA = "gestionar_usuarios_granja"  # Asignar + roles


# ============================================================================
# Scopes por Defecto según Rol
# ============================================================================

DEFAULT_SCOPES_BY_ROLE = {
    RoleNames.ADMIN_GRANJA: [
        # Infraestructura
        Scopes.GESTIONAR_ESTANQUES,
        Scopes.GESTIONAR_CICLOS,

        # Operaciones técnicas
        Scopes.VER_PROYECCIONES,
        Scopes.GESTIONAR_PROYECCIONES,
        Scopes.DUPLICAR_PROYECCIONES,
        Scopes.GESTIONAR_SIEMBRAS,
        Scopes.GESTIONAR_COSECHAS,
        Scopes.GESTIONAR_BIOMETRIAS,

        # Tareas
        Scopes.GESTIONAR_TAREAS,

        # Analytics
        Scopes.VER_ANALYTICS,

        # Usuarios
        Scopes.VER_USUARIOS_GRANJA,
    ],

    RoleNames.BIOLOGO: [
        # Operaciones técnicas
        Scopes.VER_PROYECCIONES,
        Scopes.GESTIONAR_PROYECCIONES,
        Scopes.DUPLICAR_PROYECCIONES,
        Scopes.GESTIONAR_SIEMBRAS,
        Scopes.GESTIONAR_COSECHAS,
        Scopes.GESTIONAR_BIOMETRIAS,

        # Tareas
        Scopes.GESTIONAR_TAREAS,

        # Analytics
        Scopes.VER_ANALYTICS,

        # Usuarios
        Scopes.VER_USUARIOS_GRANJA,
    ],

    RoleNames.OPERADOR: [
        # Tareas (solo propias)
        Scopes.VER_MIS_TAREAS,
        Scopes.COMPLETAR_MIS_TAREAS,

        # Analytics (datos básicos)
        Scopes.VER_DATOS_BASICOS,
    ],

    RoleNames.CONSULTOR: [
        # Lectura completa
        Scopes.VER_TODO,
    ],
}

# ============================================================================
# Scopes Opcionales por Rol
# ============================================================================

OPTIONAL_SCOPES_BY_ROLE = {
    RoleNames.ADMIN_GRANJA: [
        # Gestión de usuarios
        Scopes.GESTIONAR_USUARIOS_GRANJA,
    ],

    RoleNames.BIOLOGO: [
        # Tareas (gestión completa)
        Scopes.EDITAR_TAREAS,
        Scopes.ELIMINAR_TAREAS,
    ],

    RoleNames.OPERADOR: [
        # Sin scopes opcionales
    ],

    RoleNames.CONSULTOR: [
        # Sin scopes opcionales
    ],
}


# ============================================================================
# Mapeo de Scopes "gestionar_*" a sus scopes granulares
# ============================================================================

GESTIONAR_SCOPE_MAPPINGS = {
    Scopes.GESTIONAR_ESTANQUES: [
        Scopes.CREAR_ESTANQUES,
        Scopes.EDITAR_ESTANQUES,
        Scopes.ELIMINAR_ESTANQUES,
    ],
    Scopes.GESTIONAR_CICLOS: [
        Scopes.CREAR_CICLOS,
        Scopes.EDITAR_CICLOS,
        Scopes.CERRAR_CICLOS,
    ],
    Scopes.GESTIONAR_PROYECCIONES: [
        Scopes.VER_PROYECCIONES,
        Scopes.CREAR_PROYECCIONES,
        Scopes.EDITAR_PROYECCIONES,
        Scopes.ELIMINAR_PROYECCIONES,
        Scopes.DUPLICAR_PROYECCIONES,
    ],
    Scopes.GESTIONAR_SIEMBRAS: [
        Scopes.CREAR_SIEMBRAS,
        Scopes.EDITAR_SIEMBRAS,
        Scopes.ELIMINAR_SIEMBRAS,
    ],
    Scopes.GESTIONAR_COSECHAS: [
        Scopes.CREAR_COSECHAS,
        Scopes.EDITAR_COSECHAS,
        Scopes.ELIMINAR_COSECHAS,
    ],
    Scopes.GESTIONAR_BIOMETRIAS: [
        Scopes.CREAR_BIOMETRIAS,
        Scopes.EDITAR_BIOMETRIAS,
        Scopes.ELIMINAR_BIOMETRIAS,
    ],
    Scopes.GESTIONAR_TAREAS: [
        Scopes.VER_TODAS_TAREAS,
        Scopes.CREAR_TAREAS,
        Scopes.EDITAR_TAREAS,
        Scopes.ELIMINAR_TAREAS,
        Scopes.ASIGNAR_TAREAS,
        Scopes.CAMBIAR_ESTADO_TAREAS,
        Scopes.DUPLICAR_TAREAS,
    ],
}


# ============================================================================
# Validación Base
# ============================================================================

def ensure_user_in_farm_or_admin(
        db: Session,
        user_id: int,
        granja_id: int,
        is_admin_global: bool
):
    """
    Validar que usuario pertenezca a la granja o sea admin global.

    IMPORTANTE: Valida que el usuario esté ACTIVO (status='a') en la granja.

    Args:
        db: Sesión de BD
        user_id: ID del usuario
        granja_id: ID de la granja
        is_admin_global: Si el usuario es admin global

    Raises:
        HTTPException 403: Si no pertenece a la granja o está inactivo
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
            detail="No pertenece a la granja o su acceso está inactivo"
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

    IMPORTANTE: Solo retorna información si el usuario está ACTIVO (status='a').

    Returns:
        (rol_nombre, scopes)
    """
    user = db.get(Usuario, usuario_id)
    if user and user.is_admin_global:
        # Admin Global tiene TODOS los scopes
        all_scopes = [
            # Infraestructura
            Scopes.CREAR_ESTANQUES,
            Scopes.EDITAR_ESTANQUES,
            Scopes.ELIMINAR_ESTANQUES,
            Scopes.GESTIONAR_ESTANQUES,
            Scopes.CREAR_CICLOS,
            Scopes.EDITAR_CICLOS,
            Scopes.CERRAR_CICLOS,
            Scopes.GESTIONAR_CICLOS,
            # Proyecciones
            Scopes.VER_PROYECCIONES,
            Scopes.CREAR_PROYECCIONES,
            Scopes.EDITAR_PROYECCIONES,
            Scopes.ELIMINAR_PROYECCIONES,
            Scopes.DUPLICAR_PROYECCIONES,
            Scopes.GESTIONAR_PROYECCIONES,
            # Siembras
            Scopes.CREAR_SIEMBRAS,
            Scopes.EDITAR_SIEMBRAS,
            Scopes.ELIMINAR_SIEMBRAS,
            Scopes.GESTIONAR_SIEMBRAS,
            # Cosechas
            Scopes.CREAR_COSECHAS,
            Scopes.EDITAR_COSECHAS,
            Scopes.ELIMINAR_COSECHAS,
            Scopes.GESTIONAR_COSECHAS,
            # Biometrías
            Scopes.CREAR_BIOMETRIAS,
            Scopes.EDITAR_BIOMETRIAS,
            Scopes.ELIMINAR_BIOMETRIAS,
            Scopes.GESTIONAR_BIOMETRIAS,
            # Tareas
            Scopes.VER_TODAS_TAREAS,
            Scopes.VER_MIS_TAREAS,
            Scopes.CREAR_TAREAS,
            Scopes.EDITAR_TAREAS,
            Scopes.ELIMINAR_TAREAS,
            Scopes.ASIGNAR_TAREAS,
            Scopes.CAMBIAR_ESTADO_TAREAS,
            Scopes.DUPLICAR_TAREAS,
            Scopes.GESTIONAR_TAREAS,
            Scopes.COMPLETAR_MIS_TAREAS,
            # Analytics
            Scopes.VER_ANALYTICS,
            Scopes.VER_DATOS_BASICOS,
            Scopes.VER_TODO,
            # Usuarios
            Scopes.VER_USUARIOS_GRANJA,
            Scopes.GESTIONAR_USUARIOS_GRANJA,
        ]
        return ("Admin Global", all_scopes)

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
    Verificar si usuario tiene un scope específico.

    Si tiene scope "gestionar_*", automáticamente tiene scopes granulares.
    """
    if is_admin_global:
        return True

    rol_nombre, scopes = get_user_role_and_scopes(db, usuario_id, granja_id)

    if not rol_nombre:
        return False

    # Verificación directa
    if required_scope in scopes:
        return True

    # Verificación por scope "gestionar_*"
    for gestionar_scope, sub_scopes in GESTIONAR_SCOPE_MAPPINGS.items():
        if gestionar_scope in scopes and required_scope in sub_scopes:
            return True

    # Scope especial VER_TODO (Consultor)
    if Scopes.VER_TODO in scopes:
        # VER_TODO da acceso de lectura a TODOS los módulos
        if required_scope.startswith("ver_"):
            return True

    return False


def user_has_any_scope(
        db: Session,
        usuario_id: int,
        granja_id: int,
        required_scopes: list[str],
        is_admin_global: bool = False
) -> bool:
    """Verificar si usuario tiene AL MENOS UNO de los scopes."""
    if is_admin_global:
        return True

    return any(
        user_has_scope(db, usuario_id, granja_id, scope, is_admin_global)
        for scope in required_scopes
    )


def user_has_all_scopes(
        db: Session,
        usuario_id: int,
        granja_id: int,
        required_scopes: list[str],
        is_admin_global: bool = False
) -> bool:
    """Verificar si usuario tiene TODOS los scopes."""
    if is_admin_global:
        return True

    return all(
        user_has_scope(db, usuario_id, granja_id, scope, is_admin_global)
        for scope in required_scopes
    )


def get_user_farms_with_scope(
        db: Session,
        usuario_id: int,
        required_scopes: list[str],
        is_admin_global: bool = False
) -> list[int]:
    """
    Obtener IDs de granjas donde el usuario tiene AL MENOS UNO de los scopes requeridos.

    Esta función es útil para:
    - Listar recursos filtrados por granjas con permiso
    - Validar permisos antes de crear/modificar
    - Poblar UI con granjas disponibles

    Args:
        db: Sesión de BD
        usuario_id: ID del usuario
        required_scopes: Lista de scopes requeridos (con OR lógico)
        is_admin_global: Si el usuario es admin global

    Returns:
        Lista de granja_ids donde tiene AL MENOS UNO de los scopes

    Examples:
        >>> # Obtener granjas donde puede ver usuarios
        >>> granja_ids = get_user_farms_with_scope(
        ...     db, user_id,
        ...     [Scopes.VER_USUARIOS_GRANJA, Scopes.GESTIONAR_USUARIOS_GRANJA],
        ...     user.is_admin_global
        ... )

        >>> # Obtener granjas donde puede ver proyecciones
        >>> granja_ids = get_user_farms_with_scope(
        ...     db, user_id,
        ...     [Scopes.VER_PROYECCIONES, Scopes.GESTIONAR_PROYECCIONES],
        ...     user.is_admin_global
        ... )
    """
    if is_admin_global:
        # Admin Global tiene acceso a todas las granjas activas
        from models.farm import Granja
        granjas = db.query(Granja.granja_id).filter(Granja.is_active == True).all()
        return [g[0] for g in granjas]

    # Obtener todas las granjas del usuario activas
    user_farms = (
        db.query(UsuarioGranja.granja_id)
        .filter(
            UsuarioGranja.usuario_id == usuario_id,
            UsuarioGranja.status == "a"
        )
        .all()
    )

    # Filtrar solo las que tienen alguno de los scopes requeridos
    granjas_con_permiso = []
    for (farm_id,) in user_farms:
        if user_has_any_scope(db, usuario_id, farm_id, required_scopes, is_admin_global):
            granjas_con_permiso.append(farm_id)

    return granjas_con_permiso


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
    """Validar que usuario tenga un scope específico (lanza excepción si no)."""
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
    """Validar que usuario tenga AL MENOS UNO de los scopes."""
    if not user_has_any_scope(db, usuario_id, granja_id, required_scopes, is_admin_global):
        scopes_str = ", ".join(required_scopes)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permiso denegado. Requiere uno de: {scopes_str}"
        )


# ============================================================================
# Helpers Específicos
# ============================================================================

def ensure_can_view_users(db: Session, current_user: Usuario, granja_id: int):
    """Validar que usuario puede VER usuarios de una granja."""
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        granja_id,
        Scopes.VER_USUARIOS_GRANJA,
        current_user.is_admin_global
    )


def ensure_can_manage_users(db: Session, current_user: Usuario, granja_id: int):
    """Validar que usuario puede GESTIONAR usuarios (asignar + roles)."""
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        granja_id,
        Scopes.GESTIONAR_USUARIOS_GRANJA,
        current_user.is_admin_global
    )


def ensure_can_manage_tasks(db: Session, current_user: Usuario, granja_id: int):
    """Validar que usuario puede gestionar tareas."""
    ensure_user_has_any_scope(
        db,
        current_user.usuario_id,
        granja_id,
        [Scopes.GESTIONAR_TAREAS, Scopes.CREAR_TAREAS],
        current_user.is_admin_global
    )


def ensure_can_manage_biometries(db: Session, current_user: Usuario, granja_id: int):
    """Validar que usuario puede gestionar biometrías."""
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        granja_id,
        Scopes.GESTIONAR_BIOMETRIAS,
        current_user.is_admin_global
    )


def ensure_can_manage_cycles(db: Session, current_user: Usuario, granja_id: int):
    """Validar que usuario puede gestionar ciclos."""
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        granja_id,
        Scopes.GESTIONAR_CICLOS,
        current_user.is_admin_global
    )


def ensure_can_manage_projections(db: Session, current_user: Usuario, granja_id: int):
    """Validar que usuario puede gestionar proyecciones."""
    ensure_user_has_scope(
        db,
        current_user.usuario_id,
        granja_id,
        Scopes.GESTIONAR_PROYECCIONES,
        current_user.is_admin_global
    )


def user_is_read_only(db: Session, usuario_id: int, granja_id: int) -> bool:
    """Verificar si usuario es solo lectura (Consultor)."""
    rol_nombre, _ = get_user_role_and_scopes(db, usuario_id, granja_id)
    return rol_nombre == RoleNames.CONSULTOR


# ============================================================================
# Funciones de Gestión de Scopes
# ============================================================================

def get_default_scopes_for_role(rol_nombre: str) -> list[str]:
    """Obtener scopes por defecto para un rol."""
    return DEFAULT_SCOPES_BY_ROLE.get(rol_nombre, []).copy()


def get_optional_scopes_for_role(rol_nombre: str) -> list[str]:
    """Obtener scopes opcionales disponibles para un rol."""
    return OPTIONAL_SCOPES_BY_ROLE.get(rol_nombre, []).copy()


def validate_scopes_for_role(rol_nombre: str, scopes_to_add: list[str]) -> bool:
    """Validar que los scopes sean válidos para un rol."""
    optional_scopes = OPTIONAL_SCOPES_BY_ROLE.get(rol_nombre, [])

    for scope in scopes_to_add:
        if scope not in optional_scopes:
            raise ValueError(
                f"Scope '{scope}' no es válido para el rol '{rol_nombre}'. "
                f"Scopes opcionales disponibles: {optional_scopes}"
            )

    return True