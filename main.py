#!/usr/bin/env python3
"""
BateriaBot — entrypoint principal.

Ejecuta todos los scrapers, guarda los resultados en SQLite y reporta un resumen.
Diseñado para correr vía cron semanal:
    0 8 * * 1 /usr/bin/python3 /Users/nandioperations/BateriaBot/main.py >> bateriabot.log 2>&1
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from config import DB_PATH
from database import init_db, save_run, finish_run, insert_listings
from matcher import classify_listings
from supabase_sync import run_sync
from scraper import mercadolibre
from scraper.html_scrapers import (
    scrape_bateriasdeautos,
    scrape_easy,
    scrape_fravega,
    scrape_norauto,
    scrape_aca,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

SECONDARY_SCRAPERS = [
    ("bateriasdeautos", scrape_bateriasdeautos),   # Moura distribuidor oficial
    ("fravega",         scrape_fravega),            # Willard blindadas con descuentos
    ("norauto",         scrape_norauto),            # Moura + otras, instalación en local
    ("easy",            scrape_easy),               # Baterías genéricas grandes superficies
    ("aca",             scrape_aca),                # Prestadores ACA (informativo)
]


async def run() -> None:
    started = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info(f"BateriaBot iniciado: {started.strftime('%Y-%m-%d %H:%M UTC')}")
    logger.info(f"Base de datos: {DB_PATH}")
    logger.info("=" * 60)

    conn = init_db(DB_PATH)
    total_inserted = 0

    # ── MercadoLibre (fuente primaria, async) ──────────────────────────────
    run_id = save_run(conn, "mercadolibre")
    try:
        ml_listings = await mercadolibre.run_all_searches()
        classify_listings(ml_listings)
        inserted = insert_listings(conn, run_id, ml_listings)
        finish_run(conn, run_id, "success", inserted)
        total_inserted += inserted
        logger.info(f"[ML] ✓ {inserted} registros guardados")
    except Exception as e:
        finish_run(conn, run_id, "error", 0, str(e))
        logger.error(f"[ML] ✗ Error fatal: {e}")

    # ── Scrapers secundarios (síncronos, best-effort) ──────────────────────
    for source_name, scraper_fn in SECONDARY_SCRAPERS:
        run_id = save_run(conn, source_name)
        try:
            listings = scraper_fn()
            classify_listings(listings)
            inserted = insert_listings(conn, run_id, listings)
            finish_run(conn, run_id, "success", inserted)
            total_inserted += inserted
            logger.info(f"[{source_name}] ✓ {inserted} registros guardados")
        except Exception as e:
            finish_run(conn, run_id, "error", 0, str(e))
            logger.error(f"[{source_name}] ✗ Error: {e}")

    # ── Sincronizar con Supabase ───────────────────────────────────────────────
    logger.info("Sincronizando con Supabase...")
    run_sync(conn, since=started.isoformat())

    conn.close()

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    logger.info("=" * 60)
    logger.info(f"Finalizado en {elapsed:.1f}s — {total_inserted} registros nuevos totales")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run())
