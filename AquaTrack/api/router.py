from fastapi import APIRouter
from api import auth, granjas, estanques

router = APIRouter()
router.include_router(auth.router)
router.include_router(granjas.router)
router.include_router(estanques.router)