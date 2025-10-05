# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.router import router as api_router
from utils.db import Base, engine

# =====================================
# Inicializar la app
# =====================================
app = FastAPI(
    title="AquaTrack API",
    description="Backend principal del sistema AquaTrack.",
    version="1.0.0",
)

# =====================================
# Configuración de CORS
# =====================================
origins = [
    "http://localhost:5173",  # ejemplo para front en Vite
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # o ["*"] si aún no tienes frontend definido
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================
# Inicializar Base de Datos
# =====================================
Base.metadata.create_all(bind=engine)

# =====================================
# Incluir Routers
# =====================================
app.include_router(api_router)

# =====================================
# Ruta raíz de prueba
# =====================================
@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Bienvenido a AquaTrack API"}

# =====================================
# Entry point (para uvicorn)
# =====================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
