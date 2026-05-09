"""
Sincronización SQLite → Supabase.

Sube los listings nuevos y mantiene el catálogo actualizado.
Se llama automáticamente al final de cada run de main.py.

Para correr manualmente (sube todo lo que haya en SQLite):
    python supabase_sync.py
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone

from supabase import create_client, Client

logger = logging.getLogger(__name__)


def _get_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "Faltan SUPABASE_URL o SUPABASE_KEY en el .env"
        )
    return create_client(url, key)


# ── Catálogo ──────────────────────────────────────────────────────────────────

def sync_catalog(client: Client, conn: sqlite3.Connection) -> None:
    """Sube catálogo y equivalencias (upsert — reemplaza si ya existe)."""
    rows = conn.execute(
        "SELECT id, brand, model_code, capacity_ah, cca, voltage_v, type, category, polarity, notes FROM catalog"
    ).fetchall()
    cols = ["id", "brand", "model_code", "capacity_ah", "cca", "voltage_v", "type", "category", "polarity", "notes"]
    data = [dict(zip(cols, r)) for r in rows]

    if data:
        client.table("catalog").upsert(data, on_conflict="id").execute()
        logger.info(f"[supabase] catálogo: {len(data)} modelos sincronizados")

    eq_rows = conn.execute(
        "SELECT model_id, equivalent_model_id FROM catalog_equivalences"
    ).fetchall()
    eq_data = [{"model_id": r[0], "equivalent_model_id": r[1]} for r in eq_rows]
    if eq_data:
        client.table("catalog_equivalences").upsert(
            eq_data, on_conflict="model_id,equivalent_model_id"
        ).execute()
        logger.info(f"[supabase] equivalencias: {len(eq_data)} pares sincronizados")


# ── Listings ──────────────────────────────────────────────────────────────────

def sync_listings(
    client: Client,
    conn: sqlite3.Connection,
    since: str | None = None,
) -> int:
    """
    Sube listings nuevos a Supabase.
    `since`: ISO timestamp — solo sube listings scraped_at > since.
    Si es None, sube todos los listings.
    """
    query = """
        SELECT
            id, scrape_run_id, scraped_at, source,
            external_id, url, title, brand, model,
            voltage_v, capacity_ah, cca, polarity,
            price, original_price, currency, discount_pct,
            installments_qty, installment_amount, installment_rate,
            free_shipping, has_installation, delivery_available,
            seller_name, seller_id, seller_reputation, is_official_store,
            condition, available_quantity, sold_quantity,
            catalog_model_id
        FROM listings
    """
    params: list = []
    if since:
        query += " WHERE scraped_at > ?"
        params.append(since)
    query += " ORDER BY scraped_at DESC"

    rows = conn.execute(query, params).fetchall()
    if not rows:
        logger.info("[supabase] listings: nada nuevo para subir")
        return 0

    cols = [
        "id", "scrape_run_id", "scraped_at", "source",
        "external_id", "url", "title", "brand", "model",
        "voltage_v", "capacity_ah", "cca", "polarity",
        "price", "original_price", "currency", "discount_pct",
        "installments_qty", "installment_amount", "installment_rate",
        "free_shipping", "has_installation", "delivery_available",
        "seller_name", "seller_id", "seller_reputation", "is_official_store",
        "condition", "available_quantity", "sold_quantity",
        "catalog_model_id",
    ]
    # Convertir ints SQLite (0/1) a bool para Postgres
    bool_cols = {"free_shipping", "has_installation", "delivery_available", "is_official_store"}

    data = []
    for row in rows:
        d = dict(zip(cols, row))
        for bc in bool_cols:
            if d[bc] is not None:
                d[bc] = bool(d[bc])
        # raw_data no se sube (puede ser muy grande y no es útil en el dashboard)
        data.append(d)

    # Upsert en lotes de 500 para no superar el límite de payload
    BATCH = 500
    total = 0
    for i in range(0, len(data), BATCH):
        batch = data[i : i + BATCH]
        client.table("listings").upsert(batch, on_conflict="id").execute()
        total += len(batch)

    logger.info(f"[supabase] listings: {total} registros subidos")
    return total


# ── Scrape runs ───────────────────────────────────────────────────────────────

def sync_scrape_runs(client: Client, conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT id, started_at, finished_at, source, status, items_scraped, error_message FROM scrape_runs"
    ).fetchall()
    cols = ["id", "started_at", "finished_at", "source", "status", "items_scraped", "error_message"]
    data = [dict(zip(cols, r)) for r in rows]
    if data:
        client.table("scrape_runs").upsert(data, on_conflict="id").execute()
        logger.info(f"[supabase] scrape_runs: {len(data)} filas sincronizadas")


# ── Entrada principal ─────────────────────────────────────────────────────────

def run_sync(conn: sqlite3.Connection, since: str | None = None) -> None:
    """
    Punto de entrada llamado desde main.py al final de cada run.
    `since`: solo sube listings más nuevos que este timestamp.
    """
    try:
        client = _get_client()
        sync_catalog(client, conn)
        sync_scrape_runs(client, conn)
        sync_listings(client, conn, since=since)
    except Exception as e:
        logger.error(f"[supabase] Error en sincronización: {e}")


if __name__ == "__main__":
    # Ejecución manual: sube todo
    import sys
    from pathlib import Path
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")

    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    run_sync(conn)
    conn.close()
    print("Sincronización completa.")
