from fastapi import APIRouter
from .auth import router as auth_router
from .farms import router as farms_router
from .ponds import router as ponds_router
from .cycles import router as cycles_router
from .seeding import router as seeding_router  # 👈 AGREGAR

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(farms_router)
api_router.include_router(ponds_router)
api_router.include_router(cycles_router)
api_router.include_router(seeding_router)  # 👈 AGREGAR