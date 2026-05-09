import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional
from models import Listing


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_tables(conn)
    _migrate(conn)
    _seed_catalog(conn)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scrape_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            items_scraped INTEGER DEFAULT 0,
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS catalog (
            id TEXT PRIMARY KEY,        -- brand_modelcode, ej. "willard_ub620"
            brand TEXT NOT NULL,
            model_code TEXT NOT NULL,
            capacity_ah REAL,
            cca INTEGER,
            voltage_v REAL,
            type TEXT,                  -- standard | agm | efb | gel
            category TEXT,              -- auto | start_stop | moto | industrial
            polarity TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS catalog_equivalences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT NOT NULL REFERENCES catalog(id),
            equivalent_model_id TEXT NOT NULL REFERENCES catalog(id),
            UNIQUE(model_id, equivalent_model_id)
        );

        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scrape_run_id INTEGER REFERENCES scrape_runs(id),
            scraped_at TEXT NOT NULL,
            source TEXT NOT NULL,

            external_id TEXT,
            url TEXT,

            title TEXT NOT NULL,
            brand TEXT,
            model TEXT,

            voltage_v REAL,
            capacity_ah REAL,
            cca INTEGER,
            polarity TEXT,

            price REAL NOT NULL,
            original_price REAL,
            currency TEXT DEFAULT 'ARS',
            discount_pct REAL,

            installments_qty INTEGER,
            installment_amount REAL,
            installment_rate REAL,

            free_shipping INTEGER,
            has_installation INTEGER,
            delivery_available INTEGER,

            seller_name TEXT,
            seller_id TEXT,
            seller_reputation TEXT,
            is_official_store INTEGER,

            condition TEXT,
            available_quantity INTEGER,
            sold_quantity INTEGER,

            raw_data TEXT,

            catalog_model_id TEXT REFERENCES catalog(id)
        );

        CREATE INDEX IF NOT EXISTS idx_listings_external_id
            ON listings(external_id);
        CREATE INDEX IF NOT EXISTS idx_listings_scraped_at
            ON listings(scraped_at);
        CREATE INDEX IF NOT EXISTS idx_listings_brand
            ON listings(brand);
        CREATE INDEX IF NOT EXISTS idx_listings_source
            ON listings(source);
    """)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """Aplica migraciones sobre bases de datos existentes."""
    existing_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(listings)").fetchall()
    }
    if "catalog_model_id" not in existing_cols:
        conn.execute("ALTER TABLE listings ADD COLUMN catalog_model_id TEXT")
        conn.commit()

    # Índice sobre la columna (recién agregada o ya existente)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_listings_catalog_model_id ON listings(catalog_model_id)"
    )
    conn.commit()

    existing_tables = {
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "catalog" not in existing_tables:
        conn.executescript("""
            CREATE TABLE catalog (
                id TEXT PRIMARY KEY,
                brand TEXT NOT NULL,
                model_code TEXT NOT NULL,
                capacity_ah REAL,
                cca INTEGER,
                voltage_v REAL,
                type TEXT,
                category TEXT,
                polarity TEXT,
                notes TEXT
            );
            CREATE TABLE catalog_equivalences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL REFERENCES catalog(id),
                equivalent_model_id TEXT NOT NULL REFERENCES catalog(id),
                UNIQUE(model_id, equivalent_model_id)
            );
        """)
        conn.commit()


def _seed_catalog(conn: sqlite3.Connection) -> None:
    from catalog import ALL_MODELS, EQUIVALENCES
    conn.executemany(
        """INSERT OR REPLACE INTO catalog
           (id, brand, model_code, capacity_ah, cca, voltage_v, type, category, polarity, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (m.id, m.brand, m.model_code, m.capacity_ah, m.cca,
             m.voltage_v, m.type, m.category, m.polarity, m.notes)
            for m in ALL_MODELS
        ],
    )
    conn.executemany(
        """INSERT OR IGNORE INTO catalog_equivalences (model_id, equivalent_model_id)
           VALUES (?, ?)""",
        list(EQUIVALENCES.items()),
    )
    conn.commit()


def save_run(conn: sqlite3.Connection, source: str) -> int:
    cur = conn.execute(
        "INSERT INTO scrape_runs (started_at, source, status) VALUES (?, ?, 'running')",
        (_now(), source),
    )
    conn.commit()
    return cur.lastrowid


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    items_scraped: int,
    error: Optional[str] = None,
) -> None:
    conn.execute(
        """UPDATE scrape_runs
           SET finished_at=?, status=?, items_scraped=?, error_message=?
           WHERE id=?""",
        (_now(), status, items_scraped, error, run_id),
    )
    conn.commit()


def insert_listings(
    conn: sqlite3.Connection, run_id: int, listings: list[Listing]
) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    inserted = 0

    for listing in listings:
        # Deduplicación: un ítem por día por fuente
        if listing.external_id:
            exists = conn.execute(
                """SELECT 1 FROM listings
                   WHERE external_id=? AND source=? AND DATE(scraped_at)=?""",
                (listing.external_id, listing.source, today),
            ).fetchone()
            if exists:
                continue

        conn.execute(
            """INSERT INTO listings (
                scrape_run_id, scraped_at, source,
                external_id, url,
                title, brand, model,
                voltage_v, capacity_ah, cca, polarity,
                price, original_price, currency, discount_pct,
                installments_qty, installment_amount, installment_rate,
                free_shipping, has_installation, delivery_available,
                seller_name, seller_id, seller_reputation, is_official_store,
                condition, available_quantity, sold_quantity,
                raw_data, catalog_model_id
            ) VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )""",
            (
                run_id, _now(), listing.source,
                listing.external_id, listing.url,
                listing.title, listing.brand, listing.model,
                listing.voltage_v, listing.capacity_ah, listing.cca, listing.polarity,
                listing.price, listing.original_price, listing.currency, listing.discount_pct,
                listing.installments_qty, listing.installment_amount, listing.installment_rate,
                int(listing.free_shipping), int(listing.has_installation), int(listing.delivery_available),
                listing.seller_name, listing.seller_id, listing.seller_reputation, int(listing.is_official_store),
                listing.condition, listing.available_quantity, listing.sold_quantity,
                listing.raw_data, listing.catalog_model_id,
            ),
        )
        inserted += 1

    conn.commit()
    return inserted


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
