"""
Utilidades centralizadas para manejo de fechas y timestamps.
Todas las operaciones usan America/Mazatlan como zona horaria de referencia.

IMPORTANTE: Esta implementación es INDEPENDIENTE de la zona horaria del servidor MySQL.
Todos los timestamps se convierten explícitamente a Mazatlán antes de persistir.

Convención del sistema:
- Si un datetime llega **naive** (sin tzinfo), se interpreta como **hora de Mazatlán**.
- Si un datetime llega **aware** (con tzinfo), se convierte a **Mazatlán** y se
  persiste como naive en Mazatlán (sin tzinfo).
"""
from datetime import datetime, date, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo

    MAZATLAN_TZ = ZoneInfo("America/Mazatlan")
    UTC_TZ = ZoneInfo("UTC")
except ImportError:
    # Fallback para Python < 3.9
    import pytz

    MAZATLAN_TZ = pytz.timezone("America/Mazatlan")
    UTC_TZ = pytz.UTC


def now_mazatlan() -> datetime:
    """
    Retorna el datetime actual en zona horaria de Mazatlán (naive para MySQL DATETIME).
    """
    return datetime.now(MAZATLAN_TZ).replace(tzinfo=None, microsecond=0)


def now_mazatlan_aware() -> datetime:
    """
    Retorna el datetime actual en zona horaria de Mazatlán (con tzinfo).
    Útil para cálculos y comparaciones antes de persistir.
    """
    return datetime.now(MAZATLAN_TZ)


def today_mazatlan() -> date:
    """
    Retorna la fecha actual (date) en zona horaria de Mazatlán.
    """
    return datetime.now(MAZATLAN_TZ).date()


def to_mazatlan_naive(dt: datetime) -> datetime:
    """
    Normaliza un datetime a hora de Mazatlán SIN tzinfo (naive) para persistencia.

    Regla:
    - Si dt es NAIVE (tzinfo=None) => se interpreta como hora de **Mazatlán** y
      se devuelve tal cual (limpiando microsegundos).
    - Si dt es AWARE => se convierte a Mazatlán y se devuelve sin tzinfo.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=None, microsecond=0)
    return dt.astimezone(MAZATLAN_TZ).replace(tzinfo=None, microsecond=0)


def from_mazatlan_to_utc(dt: datetime) -> datetime:
    """
    Convierte un datetime naive (asumiendo Mazatlán) a UTC naive.
    Útil si necesitas almacenar en UTC explícitamente.
    """
    dt_mzt = dt.replace(tzinfo=MAZATLAN_TZ)
    return dt_mzt.astimezone(UTC_TZ).replace(tzinfo=None, microsecond=0)


def date_to_mazatlan_datetime(
        d: date,
        hour: int = 0,
        minute: int = 0,
        second: int = 0
) -> datetime:
    """
    Convierte un objeto date a datetime en zona horaria de Mazatlán (naive).
    """
    dt_aware = datetime(d.year, d.month, d.day, hour, minute, second, tzinfo=MAZATLAN_TZ)
    return dt_aware.replace(tzinfo=None)


def date_range_mazatlan(
        start_date: date,
        end_date: date
) -> tuple[datetime, datetime]:
    """
    Convierte un rango de fechas a datetimes de inicio y fin del día en Mazatlán (naive).
    """
    start_dt = date_to_mazatlan_datetime(start_date, 0, 0, 0)
    end_dt = date_to_mazatlan_datetime(end_date, 23, 59, 59)
    return start_dt, end_dt


def parse_date_filter(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normaliza un datetime para usar en filtros de consultas (o None).
    """
    if dt is None:
        return None
    return to_mazatlan_naive(dt)


def add_days_mazatlan(dt: datetime, days: int) -> datetime:
    """
    Suma días a un datetime manteniendo la hora de Mazatlán correcta.
    Maneja cambios de horario de verano automáticamente.
    """
    dt_aware = dt.replace(tzinfo=MAZATLAN_TZ)
    result_aware = dt_aware + timedelta(days=days)
    return result_aware.replace(tzinfo=None, microsecond=0)


def get_week_start_mazatlan(dt: datetime) -> datetime:
    """
    Obtiene el inicio de la semana (lunes 00:00:00) en Mazatlán (naive).
    """
    dt_aware = dt.replace(tzinfo=MAZATLAN_TZ)
    days_since_monday = dt_aware.weekday()
    week_start = dt_aware - timedelta(days=days_since_monday)
    return week_start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


def is_same_day_mazatlan(dt1: datetime, dt2: datetime) -> bool:
    """
    Compara si dos datetimes son el mismo día en Mazatlán.
    """
    date1 = to_mazatlan_naive(dt1).date()
    date2 = to_mazatlan_naive(dt2).date()
    return date1 == date2
