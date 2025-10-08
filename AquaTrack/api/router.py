from fastapi import APIRouter
from api import auth, granjas, estanques, files, ciclos, proyeccion, siembra_plan, siembra_estanque
# Aún pendientes (próximos sprints): plan_cosechas, cosecha_ola, cosecha_estanque, biometria.

router = APIRouter()
router.include_router(auth.router)
router.include_router(granjas.router)
router.include_router(estanques.router)
router.include_router(files.router)
router.include_router(ciclos.router)
router.include_router(proyeccion.router)
router.include_router(siembra_plan.router)
router.include_router(siembra_estanque.router)
