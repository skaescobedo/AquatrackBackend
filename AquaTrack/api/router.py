from fastapi import APIRouter
from api import auth, granjas, estanques, ciclos, siembra_plan, siembra_estanque

router = APIRouter()
router.include_router(auth.router)
router.include_router(granjas.router)
router.include_router(estanques.router)
router.include_router(ciclos.router)
router.include_router(siembra_plan.router)
router.include_router(siembra_estanque.router)