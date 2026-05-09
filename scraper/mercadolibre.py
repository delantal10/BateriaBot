"""
Scraper de MercadoLibre Argentina — HTML + cookies de sesión de Chrome.

La API REST (/sites/MLA/search) devuelve 403 sin permisos de marketplace.
En cambio, listado.mercadolibre.com.ar sirve un HTML de 1.7MB con todos los
datos embebidos en formato "polycard" (componentes JSON por producto).

Requiere sesión activa de ML en Chrome (Profile 1). Las cookies se leen
automáticamente con browser_cookie3.
"""

import asyncio
import json
import logging
import re
import os
from typing import Optional

import httpx
from models import Listing
from config import MAX_ITEMS_PER_QUERY, RATE_LIMIT_DELAY, HTTP_TIMEOUT, MAX_RETRIES

logger = logging.getLogger(__name__)

ML_BASE = "https://listado.mercadolibre.com.ar"

ML_SEARCH_PATHS = [
    "/bateria-de-auto-willard",
    "/bateria-de-auto-unibat",
    "/bateria-de-auto-moura",
    "/bateria-de-auto",
]

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
}

CHROME_PROFILE = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Profile 1/Cookies"
)


def _get_session_cookies() -> dict:
    """
    Lee cookies de sesión de ML. Orden de prioridad:
    1. Variables de entorno ML_COOKIE_* (Streamlit Cloud / servidor)
    2. Chrome Profile 1 local (Mac con sesión activa)
    """
    # 1. Env vars (Streamlit secrets o .env)
    env_ssid = os.environ.get("ML_COOKIE_SSID", "")
    if env_ssid:
        cookies = {
            "ssid":              env_ssid,
            "p_dsid":            os.environ.get("ML_COOKIE_P_DSID", ""),
            "p_edsid":           os.environ.get("ML_COOKIE_P_EDSID", ""),
            "x-meli-session-id": os.environ.get("ML_COOKIE_SESSION_ID", ""),
            "dsid":              os.environ.get("ML_COOKIE_DSID", ""),
            "edsid":             os.environ.get("ML_COOKIE_EDSID", ""),
        }
        cookies = {k: v for k, v in cookies.items() if v}
        logger.info(f"[ML] Cookies cargadas desde variables de entorno ({len(cookies)} cookies)")
        return cookies

    # 2. Chrome local
    try:
        import browser_cookie3
        jar = browser_cookie3.chrome(
            cookie_file=CHROME_PROFILE,
            domain_name="mercadolibre",
        )
        cookies = {c.name: c.value for c in jar}
        if cookies.get("ssid"):
            logger.info(f"[ML] Cookies de Chrome cargadas ({len(cookies)} cookies, usuario: {cookies.get('orgnickp', '?')})")
            return cookies
        logger.warning("[ML] Chrome no tiene sesión activa de ML")
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"[ML] Chrome no disponible: {e}")

    logger.error(
        "[ML] Sin cookies de sesión. Opciones:\n"
        "  · Local: abrí ML en Chrome y volvé a correr\n"
        "  · Nube:  corré 'python export_ml_cookies.py' y pegá en Streamlit secrets"
    )
    return {}


def is_session_expired(html: str) -> bool:
    """Detecta si la respuesta es una página de sesión vencida o captcha."""
    if len(html) < 50_000:
        return True
    if "account-verification" in html or "micro-landing" in html[:2000]:
        return True
    if "_n.ctx.r=" not in html:
        return True
    return False


async def run_all_searches() -> list[Listing]:
    cookies = _get_session_cookies()
    if not cookies.get("ssid"):
        logger.warning("[ML] Sin sesión activa — los resultados pueden estar vacíos")

    seen_ids: set[str] = set()
    all_listings: list[Listing] = []

    async with httpx.AsyncClient(
        headers=_BROWSER_HEADERS,
        cookies=cookies,
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
    ) as client:
        for path in ML_SEARCH_PATHS:
            label = path.strip("/")
            logger.info(f"[ML] Scrapeando: {label}")
            try:
                listings = await _scrape_all_pages(client, path)
                added = 0
                for listing in listings:
                    key = listing.external_id or listing.url or listing.title
                    if key in seen_ids:
                        continue
                    seen_ids.add(key)
                    all_listings.append(listing)
                    added += 1
                logger.info(f"[ML] {label}: {added} ítems nuevos")
            except Exception as e:
                logger.error(f"[ML] Error en '{label}': {e}", exc_info=True)

    logger.info(f"[ML] Total acumulado: {len(all_listings)} ítems únicos")
    return all_listings


async def _scrape_all_pages(client: httpx.AsyncClient, base_path: str) -> list[Listing]:
    listings: list[Listing] = []
    offset = 1  # ML usa _Desde_1, _Desde_51, _Desde_101...

    while len(listings) < MAX_ITEMS_PER_QUERY:
        url = f"{ML_BASE}{base_path}" if offset == 1 else f"{ML_BASE}{base_path}_Desde_{offset}"
        html = await _fetch(client, url)
        if not html:
            break

        items, total = _extract_polycards(html)
        if not items:
            break

        for item in items:
            listing = _parse_polycard(item)
            if listing:
                listings.append(listing)

        offset += 50
        if offset > total or total == 0:
            break

        await asyncio.sleep(RATE_LIMIT_DELAY)

    return listings


async def _fetch(client: httpx.AsyncClient, url: str) -> Optional[str]:
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                if is_session_expired(resp.text):
                    logger.error(
                        "[ML] Sesión vencida o captcha detectado. "
                        "Abrí MercadoLibre en Chrome para renovar cookies, "
                        "o actualizá ML_COOKIE_SSID en Streamlit secrets."
                    )
                    return None
                return resp.text
            elif resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                logger.warning(f"[ML] Rate limit, esperando {wait}s")
                await asyncio.sleep(wait)
            else:
                logger.warning(f"[ML] HTTP {resp.status_code} para {url}")
                return None
        except httpx.RequestError as e:
            logger.warning(f"[ML] Error de red (intento {attempt + 1}): {e}")
            await asyncio.sleep(2 ** (attempt + 1))
    return None


def _extract_polycards(html: str) -> tuple[list[dict], int]:
    """
    Extrae los polycards desde el script _n.ctx.r embebido en el HTML de ML.
    Ruta: appProps.pageProps.initialState.results[n].polycard
    """
    # Extraer el bloque _n.ctx.r={...}
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    state_script = next((s for s in scripts if '_n.ctx.r=' in s and 'user_product_id' in s), None)
    if not state_script:
        return [], 0

    idx = state_script.find('_n.ctx.r=')
    json_start = idx + len('_n.ctx.r=')
    depth = 0
    end = json_start
    for i, c in enumerate(state_script[json_start:json_start + 1_200_000], json_start):
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    try:
        data = json.loads(state_script[json_start:end])
    except json.JSONDecodeError:
        return [], 0

    initial = (
        data.get('appProps', {})
            .get('pageProps', {})
            .get('initialState', {})
    )
    results = initial.get('results', [])
    total = initial.get('paging', {}).get('total', len(results))

    items = []
    for res in results:
        polycard = res.get('polycard')
        if not polycard:
            continue
        meta = polycard.get('metadata', {})
        comps = polycard.get('components', [])
        if not comps:
            continue
        items.append({'id': meta.get('id', ''), 'metadata': meta, 'components': comps})

    return items, total


def _parse_polycard(item: dict) -> Optional[Listing]:
    """Parsea un objeto polycard al modelo Listing."""
    try:
        meta = item.get("metadata", {})
        item_id = item.get("id") or meta.get("id", "")
        if not item_id:
            return None

        components = item.get("components", [])
        comp_by_type = {c.get("type"): c for c in components if isinstance(c, dict)}

        # Título
        title_comp = comp_by_type.get("title", {})
        title = title_comp.get("title", {}).get("text", "")
        if not title:
            return None

        # Precio
        price_comp = comp_by_type.get("price", {})
        price_data = price_comp.get("price", {})
        current = price_data.get("current_price", {})
        price = current.get("value")
        if not price:
            return None

        original = price_data.get("previous_price", {}).get("value")

        # Cuotas
        inst_data = price_data.get("installments", {})
        inst_qty = None
        inst_amount = None
        inst_rate = 0.0
        inst_no_interest = inst_data.get("no_interest", True)
        for val in inst_data.get("values", []):
            if val.get("key") == "payment_method":
                pass  # medio de pago
            elif val.get("key") == "price":
                inst_amount = val.get("price", {}).get("value")
        # Extraer cantidad de cuotas del texto ("6 cuotas...")
        inst_text = inst_data.get("text", "")
        m = re.search(r'(\d+)\s+cuotas', inst_text)
        if m:
            inst_qty = int(m.group(1))
        if inst_qty and inst_amount and price:
            inst_rate = 0.0 if inst_no_interest else round((inst_qty * inst_amount / price - 1) * 100, 2)

        # Envío
        shipping_comp = comp_by_type.get("shipping", {})
        shipping_text = ""
        for part in shipping_comp.get("text", {}).get("values", []):
            shipping_text += part.get("label", {}).get("text", "")
        free_shipping = "gratis" in shipping_text.lower()

        # URL
        permalink = meta.get("url", "")
        if not permalink:
            url_comp = comp_by_type.get("title", {})
            permalink = url_comp.get("title", {}).get("url", "")

        # Atributos del item
        has_installation = "instalaci" in title.lower()

        return Listing(
            source="mercadolibre",
            external_id=item_id,
            url=permalink,
            title=title,
            brand=None,
            model=None,
            voltage_v=None,
            capacity_ah=None,
            cca=None,
            polarity=None,
            price=float(price),
            original_price=float(original) if original else None,
            currency="ARS",
            installments_qty=inst_qty,
            installment_amount=float(inst_amount) if inst_amount else None,
            installment_rate=inst_rate,
            free_shipping=free_shipping,
            has_installation=has_installation,
            delivery_available=True,
            seller_name=None,
            seller_id=None,
            seller_reputation=None,
            is_official_store=False,
            condition="new",
            available_quantity=None,
            sold_quantity=None,
            raw_data=json.dumps(item, ensure_ascii=False),
        )
    except Exception as e:
        logger.error(f"[ML] Error parseando polycard {item.get('item_id')}: {e}")
        return None
