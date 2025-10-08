from fastapi import APIRouter
from api import auth, granjas, estanques, ciclos, siembra_plan, siembra_estanque, plan_cosechas, cosecha_ola, cosecha_estanque, biometria, proyeccion

router = APIRouter()
router.include_router(auth.router)
router.include_router(granjas.router)
router.include_router(estanques.router)
router.include_router(ciclos.router)
router.include_router(siembra_plan.router)
router.include_router(siembra_estanque.router)
router.include_router(plan_cosechas.router)
router.include_router(cosecha_ola.router)
router.include_router(cosecha_estanque.router)
router.include_router(biometria.router)
router.include_router(proyeccion.router)