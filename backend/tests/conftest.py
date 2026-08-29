"""
Global pytest configuration.

CRITICAL SAFETY NOTE: several test fixtures TRUNCATE/DELETE core tables as part
of setup. Those fixtures must never run against the real dev/demo database
(moneyops_v2) — doing so previously wiped the live Incident Lab dataset and the
Action Governor audit trail. This file forces every test run onto an isolated
`<db>_test` database, created on demand, and hard-fails before any test runs if
that isolation didn't take effect.
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_real_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@127.0.0.1:5432/moneyops_v2")
_parts = urlsplit(_real_url)
_db_name = _parts.path.lstrip("/")
if not _db_name.endswith("_test"):
    _test_db_name = f"{_db_name}_test"
    _test_url = urlunsplit((_parts.scheme, _parts.netloc, f"/{_test_db_name}", _parts.query, _parts.fragment))
else:
    _test_db_name = _db_name
    _test_url = _real_url

# Must happen before ANY `app.*` import — app.core.config reads DATABASE_URL at
# module import time and caches it in a singleton `settings` object.
os.environ["DATABASE_URL"] = _test_url

# Create the test database if it doesn't exist yet (connect to the admin `postgres` db).
_admin_url = urlunsplit((_parts.scheme, _parts.netloc, "/postgres", _parts.query, _parts.fragment))
try:
    _admin_conn = psycopg2.connect(_admin_url)
    _admin_conn.autocommit = True
    _admin_cur = _admin_conn.cursor()
    _admin_cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_test_db_name,))
    if not _admin_cur.fetchone():
        _admin_cur.execute(f'CREATE DATABASE "{_test_db_name}"')
    _admin_cur.close()
    _admin_conn.close()
except Exception as e:
    raise RuntimeError(
        f"Could not provision isolated test database '{_test_db_name}': {e}. "
        f"Refusing to fall back to the real database."
    )

from app.core.config import settings  # noqa: E402  (must import after env override above)
from app.engine.database import init_db, get_db_connection  # noqa: E402

if not settings.DATABASE_URL.rstrip("/").split("/")[-1].endswith("_test"):
    raise RuntimeError(
        f"Test isolation failed: settings.DATABASE_URL resolved to "
        f"'{settings.DATABASE_URL}', which does not target a '_test' database. "
        f"Refusing to run tests that could truncate real data."
    )


@pytest.fixture(scope="session", autouse=True)
def _init_test_schema():
    init_db()
    yield


@pytest.fixture(autouse=True)
def _guard_against_wrong_database():
    """Belt-and-suspenders: re-check on every single test, not just once at import time."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT current_database();")
    row = cur.fetchone()
    dbname = row["current_database"] if isinstance(row, dict) else row[0]
    cur.close()
    conn.close()
    if not dbname.endswith("_test"):
        pytest.fail(
            f"SAFETY ABORT: test connected to '{dbname}', which is not an isolated "
            f"'_test' database. Refusing to proceed — this fixture may TRUNCATE data."
        )
