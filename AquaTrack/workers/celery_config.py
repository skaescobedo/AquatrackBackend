from celery import Celery
from config.settings import settings
import sys
from pathlib import Path

app = Celery(
    'aquatrack',
    broker=settings.REDIS_URL or 'redis://localhost:6380/0',
    backend=settings.REDIS_URL or 'redis://localhost:6380/0',
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Mexico_City',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutos hard limit
    task_soft_time_limit=25 * 60,  # 25 minutos soft timeout
)

# Asegurar que AquaTrack está en el path
sys.path.insert(0, str(Path(__file__).parent.parent))

app.autodiscover_tasks(['workers'])
