import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "baterias.db"))

# MercadoLibre API
ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
ML_SEARCH_URL = "https://api.mercadolibre.com/sites/MLA/search"
ML_ITEMS_URL = "https://api.mercadolibre.com/items"
ML_LIMIT = 50           # máximo permitido por request
MAX_ITEMS_PER_QUERY = 500
RATE_LIMIT_DELAY = 0.5  # segundos entre requests
HTTP_TIMEOUT = 30       # segundos
MAX_RETRIES = 3

# Búsquedas en MercadoLibre
# La categoría MLA1747 = "Baterías para Autos y Camionetas"
ML_SEARCH_QUERIES = [
    {"category": "MLA1747"},
    {"category": "MLA1747", "q": "bateria willard"},
    {"category": "MLA1747", "q": "bateria unibat"},
    {"category": "MLA1747", "q": "bateria moura"},
    {"category": "MLA1747", "q": "bateria bosch"},
    {"category": "MLA1747", "q": "bateria varta"},
    {"category": "MLA1747", "q": "bateria ac delco"},
    {"category": "MLA1747", "q": "bateria fiamm"},
    {"category": "MLA1747", "q": "bateria tudor"},
    {"category": "MLA1747", "q": "bateria remy"},
]

# Mapeo de IDs de atributos ML a campos del modelo
ML_ATTRIBUTE_MAP = {
    "BRAND": "brand",
    "MODEL": "model",
    "AMPERAGE_CAPACITY": "capacity_ah",
    "VOLTAGE": "voltage_v",
    "CCA": "cca",
    "POLARITY": "polarity",
}

# Scrapers HTML secundarios
SECONDARY_SCRAPERS = [
    "bateriasdeautos",
    "vzh",
]

SCRAPER_URLS = {
    "bateriasdeautos": "https://www.bateriasdeautos.com.ar/encuentra-tu-bateria/lista-de-precios/",
    "vzh": "https://www.vzh.com.ar/baterias",
}

# Búsquedas específicas para Carrefour (plataforma VTEX)
# Carrefour no vende baterías 12V de arranque directamente; estas consultas
# buscan por marca y se filtran por palabras clave para excluir juguetes y accesorios.
CARREFOUR_QUERIES = [
    "bateria willard",
    "bateria moura",
    "bateria bosch 12v",
    "bateria varta auto",
    "bateria acumulador auto",
]

# Palabras en el título que indican que NO es una batería de auto real
CARREFOUR_EXCLUDE_KEYWORDS = [
    "a batería",       # juguetes "auto a batería"
    "cargador",        # cargadores de batería
    "inflador",        # infladores
    "probador",        # probadores/analizadores
    "arrancador portátil",  # arrancadores de emergencia
    "linterna",
    "moto cortadora",
    "ciclo profundo",  # baterías solares / náuticas
    "solar",           # baterías solares
    "náutica",
    "nautica",
]

MIN_CAR_BATTERY_PRICE_ARS = 80_000  # umbral mínimo de precio para baterías reales

# Headers para requests HTTP (evita bloqueos básicos por User-Agent)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
    "Accept": "application/json, text/html",
}
