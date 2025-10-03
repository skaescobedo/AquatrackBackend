from fastapi import FastAPI
from config.settings import settings
from api.router import router as api_router

app = FastAPI(title=settings.APP_NAME)
app.include_router(api_router, prefix=settings.API_PREFIX)
