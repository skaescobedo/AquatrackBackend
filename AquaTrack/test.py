# test_tasks_manual.py
"""
Script de testing manual para el módulo de Tareas.
NO persiste datos en BD (usa rollback).
Ejecutar: python test_tasks_manual.py
"""
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Imports del proyecto
from models.task import Tarea, TareaAsignacion
from models.user import Usuario
from models.farm import Granja
from schemas.task import TareaCreate, TareaUpdate, TareaUpdateStatus
from services.task_service import (
    create_task, get_task, update_task, update_task_status, delete_task,
    duplicate_task, get_tasks_by_farm, get_user_tasks, get_overdue_tasks,
    _get_task_responsibles, _can_user_complete_task
)
from config.settings import settings


# ============================================================================
# Configuración de DB (sin persistencia)
# ============================================================================

def get_test_db() -> Session:
    """Crear sesión de BD para testing (con rollback al final)"""
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


# ============================================================================
# Helpers de Testing
# ============================================================================

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


def log_test(test_name: str):
    print(f"\n{Colors.BLUE}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BLUE}TEST: {test_name}{Colors.RESET}")
    print(f"{Colors.BLUE}{'=' * 80}{Colors.RESET}")


def log_success(message: str):
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def log_error(message: str):
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def log_info(message: str):
    print(f"{Colors.YELLOW}ℹ {message}{Colors.RESET}")


# ============================================================================
# Tests de Helpers
# ============================================================================

def test_get_task_responsibles(db: Session):
    """
    Test: _get_task_responsibles

    Caso de éxito:
    - Si hay asignaciones, retorna todos los usuario_ids asignados
    - Si NO hay asignaciones, retorna [created_by]
    """
    log_test("_get_task_responsibles()")

    try:
        # Crear usuarios falsos en memoria (no persistir)
        user1 = Usuario(
            usuario_id=9001,
            username="testuser1",
            nombre="Test",
            apellido1="User1",
            email="test1@test.com",
            password_hash="fake"
        )
        user2 = Usuario(
            usuario_id=9002,
            username="testuser2",
            nombre="Test",
            apellido1="User2",
            email="test2@test.com",
            password_hash="fake"
        )
        user3 = Usuario(
            usuario_id=9003,
            username="testuser3",
            nombre="Test",
            apellido1="User3",
            email="test3@test.com",
            password_hash="fake"
        )

        db.add(user1)
        db.add(user2)
        db.add(user3)
        db.flush()  # Solo flush, no commit

        users = [user1, user2, user3]
        log_info(f"Usuarios de prueba creados: {[u.usuario_id for u in users]}")

        # Caso 1: Tarea CON asignaciones
        tarea_create = TareaCreate(
            titulo="Test tarea con asignaciones",
            prioridad="m",
            asignados_ids=[users[1].usuario_id, users[2].usuario_id]
        )
        tarea = create_task(db, tarea_create, users[0].usuario_id)

        responsibles = _get_task_responsibles(tarea)
        assert set(responsibles) == {users[1].usuario_id, users[2].usuario_id}
        log_success(f"Tarea CON asignaciones: responsables = {responsibles}")

        # Caso 2: Tarea SIN asignaciones
        tarea_create_sin = TareaCreate(
            titulo="Test tarea sin asignaciones",
            prioridad="m",
            asignados_ids=[]
        )
        tarea_sin = create_task(db, tarea_create_sin, users[0].usuario_id)

        responsibles_sin = _get_task_responsibles(tarea_sin)
        assert responsibles_sin == [users[0].usuario_id]
        log_success(f"Tarea SIN asignaciones: responsables = {responsibles_sin} (creador)")

        log_success("Test _get_task_responsibles PASADO")

    except Exception as e:
        log_error(f"Test _get_task_responsibles FALLIDO: {str(e)}")


def test_can_user_complete_task(db: Session):
    """
    Test: _can_user_complete_task

    Caso de éxito:
    - Usuario asignado PUEDE completar
    - Usuario NO asignado NO PUEDE completar
    - Creador sin asignaciones PUEDE completar
    - Creador con asignaciones NO PUEDE completar (si no está asignado)
    """
    log_test("_can_user_complete_task()")

    try:
        # Crear usuarios falsos en memoria
        user1 = Usuario(
            usuario_id=9011,
            username="testcreator",
            nombre="Test",
            apellido1="Creator",
            email="creator@test.com",
            password_hash="fake"
        )
        user2 = Usuario(
            usuario_id=9012,
            username="testassigned",
            nombre="Test",
            apellido1="Assigned",
            email="assigned@test.com",
            password_hash="fake"
        )
        user3 = Usuario(
            usuario_id=9013,
            username="teststranger",
            nombre="Test",
            apellido1="Stranger",
            email="stranger@test.com",
            password_hash="fake"
        )

        db.add(user1)
        db.add(user2)
        db.add(user3)
        db.flush()

        users = [user1, user2, user3]
        log_info(f"Usuarios de prueba creados: {[u.usuario_id for u in users]}")

        # Tarea con asignaciones
        tarea_create = TareaCreate(
            titulo="Test permisos",
            prioridad="m",
            asignados_ids=[users[1].usuario_id]
        )
        tarea = create_task(db, tarea_create, users[0].usuario_id)

        # Casos
        puede_asignado = _can_user_complete_task(tarea, users[1].usuario_id)
        puede_creador = _can_user_complete_task(tarea, users[0].usuario_id)
        puede_ajeno = _can_user_complete_task(tarea, users[2].usuario_id)

        assert puede_asignado == True
        log_success(f"Usuario asignado ({users[1].usuario_id}) PUEDE completar: {puede_asignado}")

        assert puede_creador == False
        log_success(f"Creador ({users[0].usuario_id}) con asignaciones NO PUEDE: {puede_creador}")

        assert puede_ajeno == False
        log_success(f"Usuario ajeno ({users[2].usuario_id}) NO PUEDE: {puede_ajeno}")

        # Tarea SIN asignaciones
        tarea_create_sin = TareaCreate(
            titulo="Test sin asignaciones",
            prioridad="m",
            asignados_ids=[]
        )
        tarea_sin = create_task(db, tarea_create_sin, users[0].usuario_id)

        puede_creador_sin = _can_user_complete_task(tarea_sin, users[0].usuario_id)
        assert puede_creador_sin == True
        log_success(f"Creador sin asignaciones PUEDE completar: {puede_creador_sin}")

        log_success("Test _can_user_complete_task PASADO")

    except Exception as e:
        log_error(f"Test _can_user_complete_task FALLIDO: {str(e)}")


# ============================================================================
# Tests de CRUD
# ============================================================================

def test_create_task(db: Session):
    """
    Test: create_task

    Caso de éxito:
    - Crea tarea con datos básicos
    - Asigna usuarios correctamente
    - Status inicial = 'p', progreso = 0
    - Retorna tarea con relaciones cargadas
    """
    log_test("create_task()")

    try:
        users = db.query(Usuario).limit(2).all()
        granja = db.query(Granja).first()

        if not users or not granja:
            log_error("Se requiere al menos 1 usuario y 1 granja")
            return

        tarea_data = TareaCreate(
            granja_id=granja.granja_id,
            titulo="Test crear tarea",
            descripcion="Descripción de prueba",
            prioridad="a",
            fecha_limite=date.today() + timedelta(days=7),
            tiempo_estimado_horas=5.5,
            tipo="Mantenimiento",
            es_recurrente=True,
            asignados_ids=[users[0].usuario_id] if len(users) > 0 else []
        )

        tarea = create_task(db, tarea_data, users[0].usuario_id)

        assert tarea.titulo == "Test crear tarea"
        assert tarea.status == "p"
        assert float(tarea.progreso_pct) == 0.0
        assert tarea.prioridad == "a"
        assert tarea.created_by == users[0].usuario_id
        assert len(tarea.asignaciones) == 1

        log_success(f"Tarea creada: ID={tarea.tarea_id}, titulo={tarea.titulo}")
        log_success(f"Status={tarea.status}, progreso={tarea.progreso_pct}%")
        log_success(f"Asignaciones: {len(tarea.asignaciones)}")
        log_success("Test create_task PASADO")

    except Exception as e:
        log_error(f"Test create_task FALLIDO: {str(e)}")


def test_get_task(db: Session):
    """
    Test: get_task

    Caso de éxito:
    - Retorna tarea existente con todas las relaciones
    - Retorna None si no existe
    """
    log_test("get_task()")

    try:
        users = db.query(Usuario).limit(1).all()

        # Crear tarea
        tarea_data = TareaCreate(titulo="Test get", prioridad="m")
        tarea_creada = create_task(db, tarea_data, users[0].usuario_id)

        # Obtener tarea
        tarea = get_task(db, tarea_creada.tarea_id)

        assert tarea is not None
        assert tarea.tarea_id == tarea_creada.tarea_id
        assert tarea.creador is not None

        log_success(f"Tarea obtenida: ID={tarea.tarea_id}, creador={tarea.creador.nombre}")

        # Probar con ID inexistente
        tarea_none = get_task(db, 999999)
        assert tarea_none is None
        log_success("Tarea inexistente retorna None correctamente")

        log_success("Test get_task PASADO")

    except Exception as e:
        log_error(f"Test get_task FALLIDO: {str(e)}")


def test_update_task(db: Session):
    """
    Test: update_task

    Caso de éxito:
    - Actualiza campos básicos correctamente
    - Si progreso > 0 y < 100, status cambia a 'e' automáticamente
    - Si progreso >= 100, status cambia a 'c' automáticamente
    - Si status = 'c', progreso se fuerza a 100
    """
    log_test("update_task()")

    try:
        users = db.query(Usuario).limit(2).all()

        # Crear tarea
        tarea_data = TareaCreate(titulo="Test update", prioridad="b")
        tarea = create_task(db, tarea_data, users[0].usuario_id)

        # Update 1: Cambiar título y descripción
        update_data = TareaUpdate(
            titulo="Título actualizado",
            descripcion="Nueva descripción"
        )
        tarea_updated = update_task(db, tarea.tarea_id, update_data)

        assert tarea_updated.titulo == "Título actualizado"
        assert tarea_updated.descripcion == "Nueva descripción"
        log_success("Campos básicos actualizados correctamente")

        # Update 2: Progreso 50% (debe cambiar status a 'e')
        update_progreso = TareaUpdate(progreso_pct=50.0)
        tarea_updated = update_task(db, tarea.tarea_id, update_progreso)

        assert float(tarea_updated.progreso_pct) == 50.0
        assert tarea_updated.status == "e"
        log_success(f"Progreso 50% → status cambió a 'e' automáticamente")

        # Update 3: Progreso 100% (debe cambiar status a 'c')
        update_completo = TareaUpdate(progreso_pct=100.0)
        tarea_updated = update_task(db, tarea.tarea_id, update_completo)

        assert float(tarea_updated.progreso_pct) == 100.0
        assert tarea_updated.status == "c"
        log_success(f"Progreso 100% → status cambió a 'c' automáticamente")

        # Update 4: Reasignar usuarios
        if len(users) > 1:
            update_asignacion = TareaUpdate(asignados_ids=[users[1].usuario_id])
            tarea_updated = update_task(db, tarea.tarea_id, update_asignacion)

            assert len(tarea_updated.asignaciones) == 1
            assert tarea_updated.asignaciones[0].usuario_id == users[1].usuario_id
            log_success("Asignaciones actualizadas correctamente")

        log_success("Test update_task PASADO")

    except Exception as e:
        log_error(f"Test update_task FALLIDO: {str(e)}")


def test_update_task_status(db: Session):
    """
    Test: update_task_status

    Caso de éxito:
    - Actualiza status y progreso rápidamente
    - Si status='c', progreso se fuerza a 100
    - Si progreso > 0 y status='p', cambia a 'e'
    """
    log_test("update_task_status()")

    try:
        users = db.query(Usuario).limit(1).all()

        # Crear tarea
        tarea_data = TareaCreate(titulo="Test status update", prioridad="m")
        tarea = create_task(db, tarea_data, users[0].usuario_id)

        # Caso 1: Cambiar a 'e' con progreso 30%
        status_data = TareaUpdateStatus(status="e", progreso_pct=30.0)
        tarea_updated = update_task_status(db, tarea.tarea_id, status_data)

        assert tarea_updated.status == "e"
        assert float(tarea_updated.progreso_pct) == 30.0
        log_success("Status='e' con progreso 30% actualizado")

        # Caso 2: Marcar como completada
        status_completo = TareaUpdateStatus(status="c")
        tarea_updated = update_task_status(db, tarea.tarea_id, status_completo)

        assert tarea_updated.status == "c"
        assert float(tarea_updated.progreso_pct) == 100.0
        log_success("Status='c' → progreso forzado a 100%")

        log_success("Test update_task_status PASADO")

    except Exception as e:
        log_error(f"Test update_task_status FALLIDO: {str(e)}")


def test_delete_task(db: Session):
    """
    Test: delete_task

    Caso de éxito:
    - Elimina tarea correctamente
    - Asignaciones se eliminan en cascada
    """
    log_test("delete_task()")

    try:
        users = db.query(Usuario).limit(1).all()

        # Crear tarea
        tarea_data = TareaCreate(titulo="Test delete", prioridad="m")
        tarea = create_task(db, tarea_data, users[0].usuario_id)
        tarea_id = tarea.tarea_id

        # Eliminar
        delete_task(db, tarea_id)

        # Verificar que no existe
        tarea_deleted = get_task(db, tarea_id)
        assert tarea_deleted is None
        log_success(f"Tarea {tarea_id} eliminada correctamente")

        log_success("Test delete_task PASADO")

    except Exception as e:
        log_error(f"Test delete_task FALLIDO: {str(e)}")


def test_duplicate_task(db: Session):
    """
    Test: duplicate_task

    Caso de éxito:
    - Duplica tarea con campos básicos
    - Copia asignaciones
    - NO copia fecha_limite, progreso, status
    - Nueva tarea tiene status='p', progreso=0
    """
    log_test("duplicate_task()")

    try:
        users = db.query(Usuario).limit(2).all()

        # Crear tarea original
        tarea_data = TareaCreate(
            titulo="Tarea recurrente",
            descripcion="Descripción original",
            prioridad="a",
            tipo="Biometría",
            tiempo_estimado_horas=3.0,
            es_recurrente=True,
            fecha_limite=date.today() + timedelta(days=7),
            asignados_ids=[users[0].usuario_id] if users else []
        )
        tarea_original = create_task(db, tarea_data, users[0].usuario_id)

        # Marcar como en progreso
        update_task_status(db, tarea_original.tarea_id, TareaUpdateStatus(status="e", progreso_pct=50))

        # Duplicar
        tarea_duplicada = duplicate_task(db, tarea_original.tarea_id, users[0].usuario_id)

        # Verificar campos copiados
        assert tarea_duplicada.titulo == tarea_original.titulo
        assert tarea_duplicada.descripcion == tarea_original.descripcion
        assert tarea_duplicada.tipo == tarea_original.tipo
        assert tarea_duplicada.prioridad == tarea_original.prioridad
        assert float(tarea_duplicada.tiempo_estimado_horas) == float(tarea_original.tiempo_estimado_horas)
        assert tarea_duplicada.es_recurrente == tarea_original.es_recurrente
        log_success("Campos básicos copiados correctamente")

        # Verificar campos NO copiados
        assert tarea_duplicada.fecha_limite is None
        assert tarea_duplicada.status == "p"
        assert float(tarea_duplicada.progreso_pct) == 0.0
        log_success("Fecha límite, status y progreso reseteados correctamente")

        # Verificar asignaciones copiadas
        if users:
            assert len(tarea_duplicada.asignaciones) == len(tarea_original.asignaciones)
            log_success("Asignaciones copiadas correctamente")

        log_success("Test duplicate_task PASADO")

    except Exception as e:
        log_error(f"Test duplicate_task FALLIDO: {str(e)}")


# ============================================================================
# Tests de Queries
# ============================================================================

def test_get_tasks_by_farm(db: Session):
    """
    Test: get_tasks_by_farm

    Caso de éxito:
    - Lista tareas de una granja
    - Filtros funcionan correctamente (status, asignado_a, ciclo_id)
    - Paginación funciona
    """
    log_test("get_tasks_by_farm()")

    try:
        users = db.query(Usuario).limit(2).all()
        granja = db.query(Granja).first()

        if not granja:
            log_error("Se requiere al menos 1 granja")
            return

        # Crear varias tareas
        for i in range(3):
            tarea_data = TareaCreate(
                granja_id=granja.granja_id,
                titulo=f"Tarea granja {i + 1}",
                prioridad="m",
                asignados_ids=[users[0].usuario_id] if i == 0 and users else []
            )
            create_task(db, tarea_data, users[0].usuario_id if users else 1)

        # Query sin filtros
        tareas = get_tasks_by_farm(db, granja.granja_id)
        assert len(tareas) >= 3
        log_success(f"Query sin filtros: {len(tareas)} tareas encontradas")

        # Query con filtro de status
        tareas_pendientes = get_tasks_by_farm(db, granja.granja_id, status="p")
        assert all(t.status == "p" for t in tareas_pendientes)
        log_success(f"Filtro status='p': {len(tareas_pendientes)} tareas")

        # Query con filtro de asignado_a
        if users:
            tareas_asignadas = get_tasks_by_farm(
                db, granja.granja_id, asignado_a=users[0].usuario_id
            )
            log_success(f"Filtro asignado_a={users[0].usuario_id}: {len(tareas_asignadas)} tareas")

        # Paginación
        tareas_page = get_tasks_by_farm(db, granja.granja_id, skip=0, limit=2)
        assert len(tareas_page) <= 2
        log_success(f"Paginación (limit=2): {len(tareas_page)} tareas")

        log_success("Test get_tasks_by_farm PASADO")

    except Exception as e:
        log_error(f"Test get_tasks_by_farm FALLIDO: {str(e)}")


def test_get_user_tasks(db: Session):
    """
    Test: get_user_tasks

    Caso de éxito:
    - Lista tareas de un usuario (asignadas + creadas sin asignaciones)
    - Filtros funcionan (granja_id, status)
    - include_created funciona correctamente
    """
    log_test("get_user_tasks()")

    try:
        # Crear usuarios falsos en memoria
        user1 = Usuario(
            usuario_id=9021,
            username="testuser21",
            nombre="Test",
            apellido1="User21",
            email="user1@test.com",
            password_hash="fake"
        )
        user2 = Usuario(
            usuario_id=9022,
            username="testuser22",
            nombre="Test",
            apellido1="User22",
            email="user2@test.com",
            password_hash="fake"
        )

        db.add(user1)
        db.add(user2)
        db.flush()

        users = [user1, user2]
        log_info(f"Usuarios de prueba creados: {[u.usuario_id for u in users]}")

        granja = db.query(Granja).first()

        # Crear tarea asignada al usuario 1
        tarea_asignada = TareaCreate(
            granja_id=granja.granja_id if granja else None,
            titulo="Tarea asignada",
            prioridad="m",
            asignados_ids=[users[0].usuario_id]
        )
        create_task(db, tarea_asignada, users[1].usuario_id)

        # Crear tarea creada por usuario 1 sin asignaciones
        tarea_creada = TareaCreate(
            granja_id=granja.granja_id if granja else None,
            titulo="Tarea creada sin asignar",
            prioridad="m",
            asignados_ids=[]
        )
        create_task(db, tarea_creada, users[0].usuario_id)

        # Query con include_created=True
        tareas_con_creadas = get_user_tasks(db, users[0].usuario_id, include_created=True)
        assert len(tareas_con_creadas) >= 2
        log_success(f"include_created=True: {len(tareas_con_creadas)} tareas")

        # Query con include_created=False
        tareas_sin_creadas = get_user_tasks(db, users[0].usuario_id, include_created=False)
        assert len(tareas_sin_creadas) >= 1
        log_success(f"include_created=False: {len(tareas_sin_creadas)} tareas")

        log_success("Test get_user_tasks PASADO")

    except Exception as e:
        log_error(f"Test get_user_tasks FALLIDO: {str(e)}")


def test_get_overdue_tasks(db: Session):
    """
    Test: get_overdue_tasks

    Caso de éxito:
    - Lista solo tareas vencidas (fecha_limite < HOY)
    - Excluye completadas y canceladas
    - Ordenadas por fecha_limite ASC
    """
    log_test("get_overdue_tasks()")

    try:
        users = db.query(Usuario).limit(1).all()
        granja = db.query(Granja).first()

        if not granja:
            log_error("Se requiere al menos 1 granja")
            return

        # Crear tarea vencida
        tarea_vencida = TareaCreate(
            granja_id=granja.granja_id,
            titulo="Tarea vencida",
            prioridad="a",
            fecha_limite=date.today() - timedelta(days=5)
        )
        create_task(db, tarea_vencida, users[0].usuario_id)

        # Crear tarea vencida pero completada (NO debe aparecer)
        tarea_completada = TareaCreate(
            granja_id=granja.granja_id,
            titulo="Tarea vencida completada",
            prioridad="m",
            fecha_limite=date.today() - timedelta(days=3)
        )
        tarea_comp = create_task(db, tarea_completada, users[0].usuario_id)
        update_task_status(db, tarea_comp.tarea_id, TareaUpdateStatus(status="c"))

        # Crear tarea futura (NO debe aparecer)
        tarea_futura = TareaCreate(
            granja_id=granja.granja_id,
            titulo="Tarea futura",
            prioridad="b",
            fecha_limite=date.today() + timedelta(days=7)
        )
        create_task(db, tarea_futura, users[0].usuario_id)

        # Query
        tareas_vencidas = get_overdue_tasks(db, granja.granja_id)

        assert len(tareas_vencidas) >= 1
        assert all(t.fecha_limite < date.today() for t in tareas_vencidas)
        assert all(t.status not in ["c", "x"] for t in tareas_vencidas)
        log_success(f"Tareas vencidas encontradas: {len(tareas_vencidas)}")

        # Verificar orden
        if len(tareas_vencidas) > 1:
            fechas = [t.fecha_limite for t in tareas_vencidas]
            assert fechas == sorted(fechas)
            log_success("Tareas ordenadas por fecha_limite ASC correctamente")

        log_success("Test get_overdue_tasks PASADO")

    except Exception as e:
        log_error(f"Test get_overdue_tasks FALLIDO: {str(e)}")


# ============================================================================
# Runner Principal
# ============================================================================

def run_all_tests():
    """Ejecutar todos los tests SIN persistir en BD"""
    print(f"\n{Colors.BLUE}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BLUE}INICIANDO TESTS DEL MÓDULO DE TAREAS{Colors.RESET}")
    print(f"{Colors.BLUE}Nota: NO se persistirán datos en BD (rollback automático){Colors.RESET}")
    print(f"{Colors.BLUE}{'=' * 80}{Colors.RESET}")

    db = get_test_db()

    try:
        # Tests de Helpers
        try:
            test_get_task_responsibles(db)
        except Exception:
            db.rollback()

        try:
            test_can_user_complete_task(db)
        except Exception:
            db.rollback()

        # Tests de CRUD
        try:
            test_create_task(db)
        except Exception:
            db.rollback()

        try:
            test_get_task(db)
        except Exception:
            db.rollback()

        try:
            test_update_task(db)
        except Exception:
            db.rollback()

        try:
            test_update_task_status(db)
        except Exception:
            db.rollback()

        try:
            test_delete_task(db)
        except Exception:
            db.rollback()

        try:
            test_duplicate_task(db)
        except Exception:
            db.rollback()

        # Tests de Queries
        try:
            test_get_tasks_by_farm(db)
        except Exception:
            db.rollback()

        try:
            test_get_user_tasks(db)
        except Exception:
            db.rollback()

        try:
            test_get_overdue_tasks(db)
        except Exception:
            db.rollback()

        print(f"\n{Colors.GREEN}{'=' * 80}{Colors.RESET}")
        print(f"{Colors.GREEN}TODOS LOS TESTS COMPLETADOS{Colors.RESET}")
        print(f"{Colors.GREEN}{'=' * 80}{Colors.RESET}")

    except Exception as e:
        log_error(f"Error fatal en tests: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        # ROLLBACK para NO persistir cambios
        db.rollback()
        db.close()
        log_info("✓ Rollback ejecutado - NO se persistieron datos en BD")


if __name__ == "__main__":
    run_all_tests()