from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from utils.errors import install_error_handlers
from api.router import router as api_router


app = FastAPI(title="AquaTrack API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_error_handlers(app)

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

app.include_router(api_router)
