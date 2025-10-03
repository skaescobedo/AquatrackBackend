from fastapi import APIRouter
from api import auth, granja, estanque, ciclo, siembra, biometria, proyeccion, plan_cosechas, cosecha, tarea

router = APIRouter()
router.include_router(auth.router)
router.include_router(granja.router)
router.include_router(estanque.router)
router.include_router(ciclo.router)
router.include_router(siembra.router)
router.include_router(biometria.router)
router.include_router(proyeccion.router)
router.include_router(plan_cosechas.router)
router.include_router(cosecha.router)
router.include_router(tarea.router)
