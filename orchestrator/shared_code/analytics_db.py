import logging
import os
from contextlib import contextmanager
from typing import Iterator, Any

# Make psycopg optional to avoid breaking the entire function app
try:
    import psycopg
    PSYCOPG_AVAILABLE = True
except ImportError:
    psycopg = None  # type: ignore
    PSYCOPG_AVAILABLE = False


_logger = logging.getLogger(__name__)


def _build_dsn() -> str:
    host = os.getenv("PULSE_ANALYTICS_DB_HOST", "").strip()
    name = os.getenv("PULSE_ANALYTICS_DB_NAME", "").strip()
    user = os.getenv("PULSE_ANALYTICS_DB_USER", "").strip()
    password = os.getenv("PULSE_ANALYTICS_DB_PASSWORD", "").strip()
    port = os.getenv("PULSE_ANALYTICS_DB_PORT", "5432").strip() or "5432"

    if not host or not name or not user or not password:
        raise RuntimeError(
            "Analytics database configuration is incomplete. "
            "Expected PULSE_ANALYTICS_DB_HOST/NAME/USER/PASSWORD to be set.",
        )

    _logger.info("analytics_db: configuring connection", extra={"host": host, "db": name})

    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


@contextmanager
def get_connection() -> Iterator[Any]:
    """Yield a psycopg connection to the analytics database.

    Connections are opened on demand using env configuration and closed after
    use. Autocommit is enabled because callers typically perform single-row
    inserts or short read/write transactions.
    """
    if not PSYCOPG_AVAILABLE:
        raise RuntimeError(
            "psycopg is not installed. Install with: pip install psycopg[binary]"
        )

    dsn = _build_dsn()
    conn = psycopg.connect(dsn, autocommit=True)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            _logger.exception("analytics_db: failed to close connection")
