from fastapi import APIRouter
from .auth import router as auth_router
from .farms import router as farms_router
from .ponds import router as ponds_router
from .cycles import router as cycles_router
from .seeding import router as seeding_router
from .biometria import router as biometria_router
from .harvest import router as harvest_router
from .projections import router as proj_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(farms_router)
api_router.include_router(ponds_router)
api_router.include_router(cycles_router)
api_router.include_router(seeding_router)
api_router.include_router(biometria_router)
api_router.include_router(harvest_router)
api_router.include_router(proj_router)