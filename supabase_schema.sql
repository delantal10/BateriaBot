-- BateriaBot — Schema Supabase
-- Ejecutar en: Supabase → SQL Editor → New query

-- ── Catálogo de modelos ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS catalog (
    id          TEXT PRIMARY KEY,
    brand       TEXT NOT NULL,
    model_code  TEXT NOT NULL,
    capacity_ah REAL,
    cca         INTEGER,
    voltage_v   REAL,
    type        TEXT,       -- standard | agm | efb | gel
    category    TEXT,       -- auto | start_stop | moto | industrial
    polarity    TEXT,
    notes       TEXT
);

-- ── Equivalencias entre marcas ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS catalog_equivalences (
    id                  SERIAL PRIMARY KEY,
    model_id            TEXT NOT NULL REFERENCES catalog(id),
    equivalent_model_id TEXT NOT NULL REFERENCES catalog(id),
    UNIQUE(model_id, equivalent_model_id)
);

-- ── Ejecuciones del scraper ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scrape_runs (
    id            SERIAL PRIMARY KEY,
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    source        TEXT NOT NULL,
    status        TEXT NOT NULL,
    items_scraped INTEGER DEFAULT 0,
    error_message TEXT
);

-- ── Listings (precios scrapeados) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS listings (
    id                 INTEGER PRIMARY KEY,   -- mismo id que SQLite
    scrape_run_id      INTEGER REFERENCES scrape_runs(id),
    scraped_at         TIMESTAMPTZ,
    source             TEXT NOT NULL,

    external_id        TEXT,
    url                TEXT,
    title              TEXT NOT NULL,
    brand              TEXT,
    model              TEXT,

    voltage_v          REAL,
    capacity_ah        REAL,
    cca                INTEGER,
    polarity           TEXT,

    price              REAL NOT NULL,
    original_price     REAL,
    currency           TEXT DEFAULT 'ARS',
    discount_pct       REAL,

    installments_qty   INTEGER,
    installment_amount REAL,
    installment_rate   REAL,

    free_shipping      BOOLEAN,
    has_installation   BOOLEAN,
    delivery_available BOOLEAN,

    seller_name        TEXT,
    seller_id          TEXT,
    seller_reputation  TEXT,
    is_official_store  BOOLEAN,

    condition          TEXT,
    available_quantity INTEGER,
    sold_quantity      INTEGER,

    catalog_model_id   TEXT REFERENCES catalog(id)
);

CREATE INDEX IF NOT EXISTS idx_listings_catalog_model_id ON listings(catalog_model_id);
CREATE INDEX IF NOT EXISTS idx_listings_scraped_at       ON listings(scraped_at);
CREATE INDEX IF NOT EXISTS idx_listings_source           ON listings(source);
CREATE INDEX IF NOT EXISTS idx_listings_brand            ON listings(brand);

-- ── Vista comparativa (útil para dashboard) ────────────────────────────────
CREATE OR REPLACE VIEW precios_comparativos AS
SELECT
    l.scraped_at::date          AS fecha,
    l.source                    AS tienda,
    c.brand                     AS marca,
    c.model_code                AS modelo,
    c.capacity_ah               AS ah,
    c.cca,
    c.type                      AS tipo,
    l.price                     AS precio,
    l.original_price,
    l.discount_pct              AS descuento_pct,
    l.installments_qty          AS cuotas,
    l.installment_amount        AS monto_cuota,
    l.free_shipping             AS envio_gratis,
    l.has_installation          AS con_instalacion,
    eq.equivalent_model_id      AS modelo_equivalente_id,
    l.url
FROM listings l
JOIN catalog c ON c.id = l.catalog_model_id
LEFT JOIN catalog_equivalences eq ON eq.model_id = l.catalog_model_id
WHERE l.catalog_model_id IS NOT NULL;
