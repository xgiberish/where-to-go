#!/usr/bin/env python3
"""
Where To Go — setup verification script.

Run from backend/:
    python scripts/verify_setup.py

Checks:
  1. Required environment variables are set (not placeholders)
  2. Database is reachable
  3. pgvector extension is installed
  4. Row counts for users, agent_runs, embeddings
"""
import asyncio
import sys
from pathlib import Path

# Make `app` importable when run from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

# ── Helpers ───────────────────────────────────────────────────────────────────

OK = "  \033[32m✓\033[0m"
FAIL = "  \033[31m✗\033[0m"
WARN = "  \033[33m!\033[0m"


def _header(title: str) -> None:
    print(f"\n── {title} {'─' * max(0, 44 - len(title))}")


# ── Checks ────────────────────────────────────────────────────────────────────

_PLACEHOLDERS = {"change-me", "...", "AIza...", "gsk_...", "YOUR_GEMINI_KEY_HERE", "YOUR_GROQ_KEY_HERE"}

_SECRET_KEY_DEFAULT = "change-me-to-a-random-32-char-string"


def _check_field(label: str, val: str, prefix: str = "") -> bool:
    """Validate a single settings field. Returns True if OK."""
    if not val or any(p in val for p in _PLACEHOLDERS):
        print(f"{FAIL} {label}: not set or still a placeholder")
        return False
    if label == "SECRET_KEY" and val == _SECRET_KEY_DEFAULT:
        print(f"{WARN} {label}: still using default — generate one with secrets.token_hex(32)")
        return False
    if prefix and not val.startswith(prefix):
        print(f"{WARN} {label}: unexpected format (expected prefix '{prefix}')")
    masked = val[:8] + "…" if len(val) > 8 else "***"
    print(f"{OK} {label}: {masked}")
    return True


def check_env_vars(settings) -> bool:
    """Read all values from the Settings object (loaded from .env via config.py)."""
    _header("Environment variables")
    checks = [
        _check_field("DATABASE_URL",  settings.database_url,  "postgresql+asyncpg://"),
        _check_field("SECRET_KEY",    settings.secret_key),
        _check_field("GEMINI_API_KEY", settings.gemini_api_key, "AIza"),
        _check_field("GROQ_API_KEY",   settings.groq_api_key,   "gsk_"),
    ]
    return all(checks)


def check_models() -> None:
    _header("Model configuration")
    settings = get_settings()
    print(f"  cheap  → {settings.cheap_model}  (Groq)")
    print(f"  strong → {settings.strong_model}  (Gemini)")
    print(f"  embed  → {settings.embedding_model}  ({settings.embedding_provider}, {settings.embedding_dim}d)")


async def check_db() -> bool:
    _header("Database connection")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        settings = get_settings()
        safe_url = settings.database_url.split("@")[-1]  # hide credentials
        print(f"{OK} Connected  (@{safe_url})")
        return True
    except Exception as exc:
        print(f"{FAIL} Connection failed: {exc}")
        return False


async def check_pgvector() -> bool:
    _header("pgvector extension")
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            row = result.fetchone()
        if row:
            print(f"{OK} Installed (version {row[0]})")
            return True
        print(f"{FAIL} Not installed — run:  CREATE EXTENSION IF NOT EXISTS vector;")
        return False
    except Exception as exc:
        print(f"{FAIL} Check failed: {exc}")
        return False


_TABLE_ORDER = ["users", "agent_runs", "embeddings"]


async def count_rows() -> None:
    _header("Table row counts")
    async with engine.connect() as conn:
        for table in _TABLE_ORDER:
            try:
                result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))  # noqa: S608
                count = result.scalar()
                print(f"{OK} {table:<14} {count:>6} rows")
            except Exception as exc:
                print(f"{FAIL} {table:<14} error: {exc}")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    settings = get_settings()
    print(f"\nWhere To Go — Setup Verification")
    print(f"  app_name : {settings.app_name}")
    print(f"  debug    : {settings.debug}")

    env_ok = check_env_vars(settings)
    check_models()
    db_ok = await check_db()

    if db_ok:
        vec_ok = await check_pgvector()
        await count_rows()
    else:
        vec_ok = False

    _header("Summary")
    if env_ok and db_ok and vec_ok:
        print(f"{OK} All checks passed — ready to run.\n")
    else:
        failed = [n for n, ok in [("env", env_ok), ("db", db_ok), ("pgvector", vec_ok)] if not ok]
        print(f"{FAIL} Failed: {', '.join(failed)}\n")
        sys.exit(1)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
