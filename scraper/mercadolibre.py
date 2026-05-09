"""
Scraper de MercadoLibre Argentina via HTML con JSON embebido.

La API REST de búsqueda (api.mercadolibre.com/sites/MLA/search) devuelve 403
desde redes residenciales/locales. En cambio, listado.mercadolibre.com.ar
devuelve 200 con todos los datos embebidos en un bloque JSON dentro del HTML
(variable 'results' en el script de hidratación del servidor).

Paginación: URL pattern _Desde_<n> (n=1, 51, 101, ...)
"""

import asyncio
import json
import logging
import re
from typing import Optional
import httpx
from models import Listing
from config import (
    ML_SEARCH_URL,
    ML_LIMIT,
    MAX_ITEMS_PER_QUERY,
    RATE_LIMIT_DELAY,
    HTTP_TIMEOUT,
    MAX_RETRIES,
    ML_SEARCH_QUERIES,
    ML_ATTRIBUTE_MAP,
    DEFAULT_HEADERS,
)

logger = logging.getLogger(__name__)

ML_BASE_URL = "https://listado.mercadolibre.com.ar"

# URLs de búsqueda por marca/categoría para el scraper HTML
# Willard y Moura: búsquedas prioritarias con más páginas
# Las demás marcas se capturan igual via la búsqueda general
ML_SEARCH_URLS = [
    f"{ML_BASE_URL}/bateria-de-auto-willard",
    f"{ML_BASE_URL}/bateria-de-auto-unibat",       # Unibat = misma empresa que Willard
    f"{ML_BASE_URL}/bateria-de-auto-moura",
    f"{ML_BASE_URL}/bateria-de-auto",              # General: captura Bosch, Varta, etc.
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


async def run_all_searches() -> list[Listing]:
    """Scrapea todas las URLs de búsqueda y devuelve listings deduplicados."""
    seen_ids: set[str] = set()
    all_listings: list[Listing] = []

    async with httpx.AsyncClient(
        headers=_BROWSER_HEADERS, timeout=HTTP_TIMEOUT, follow_redirects=True
    ) as client:
        for base_url in ML_SEARCH_URLS:
            label = base_url.split("/")[-1]
            logger.info(f"[ML] Scrapeando: {label}")
            try:
                listings = await _scrape_all_pages(client, base_url)
                new_count = 0
                for listing in listings:
                    key = listing.external_id or listing.url or listing.title
                    if key in seen_ids:
                        continue
                    seen_ids.add(key)
                    all_listings.append(listing)
                    new_count += 1
                logger.info(f"[ML] {label}: {new_count} ítems nuevos")
            except Exception as e:
                logger.error(f"[ML] Error scrapeando '{label}': {e}")

    logger.info(f"[ML] Total acumulado: {len(all_listings)} ítems únicos")
    return all_listings


async def _scrape_all_pages(
    client: httpx.AsyncClient, base_url: str
) -> list[Listing]:
    listings: list[Listing] = []
    offset = 1  # ML usa _Desde_1, _Desde_51, _Desde_101...

    while len(listings) < MAX_ITEMS_PER_QUERY:
        url = base_url if offset == 1 else f"{base_url}_Desde_{offset}"
        html = await _fetch_html(client, url)
        if not html:
            break

        items, total = _extract_results(html)
        if not items:
            break

        for item in items:
            listing = _parse_item(item)
            if listing:
                listings.append(listing)

        offset += ML_LIMIT
        if offset > total:
            break

        await asyncio.sleep(RATE_LIMIT_DELAY)

    return listings


async def _fetch_html(client: httpx.AsyncClient, url: str) -> Optional[str]:
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                logger.warning(f"[ML] Rate limit (429), esperando {wait}s")
                await asyncio.sleep(wait)
            else:
                logger.warning(f"[ML] HTTP {resp.status_code} para {url}")
                return None
        except httpx.RequestError as e:
            wait = 2 ** (attempt + 1)
            logger.warning(f"[ML] Error de red (intento {attempt+1}): {e}")
            await asyncio.sleep(wait)
    return None


def _extract_results(html: str) -> tuple[list[dict], int]:
    """Extrae el array 'results' embebido en el HTML y el total de resultados."""
    # Buscar el bloque results (puede empezar con MLAU o MLA)
    for prefix in ('"results":[{"id":"MLAU', '"results":[{"id":"MLA'):
        idx = html.find(prefix)
        if idx < 0:
            continue
        start = idx + len('"results":')
        depth = 0
        end = start
        for i, c in enumerate(html[start:], start):
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        try:
            items = json.loads(html[start:end])
        except json.JSONDecodeError:
            return [], 0

        # Extraer total de resultados
        total = 0
        m = re.search(r'"paging":\{"total":(\d+)', html)
        if m:
            total = int(m.group(1))

        return items, total

    return [], 0


def _parse_item(item: dict) -> Optional[Listing]:
    try:
        bbw = item.get("buy_box_winner", {})
        if not bbw:
            return None

        price = bbw.get("price") or bbw.get("sale_price", {}).get("amount")
        if not price:
            return None

        title = item.get("title") or item.get("name", "")
        attrs = _extract_attributes(item.get("attributes", []))
        shipping = bbw.get("shipping", {})
        installments = bbw.get("installments") or {}
        seller = bbw.get("seller", {})
        sale_price = bbw.get("sale_price", {})

        original_price = (
            bbw.get("original_price")
            or sale_price.get("regular_amount")
        )

        delivery_available = shipping.get("mode", "not_specified") != "not_specified"
        has_installation = "instalaci" in title.lower()

        # Tasa de cuotas: si no figura explícitamente asumimos 0 (ML las muestra sin interés)
        inst_rate = installments.get("rate", 0.0)

        return Listing(
            source="mercadolibre",
            external_id=bbw.get("id") or item.get("id"),
            url=bbw.get("permalink"),
            title=title,
            brand=attrs.get("brand"),
            model=attrs.get("model"),
            voltage_v=attrs.get("voltage_v"),
            capacity_ah=attrs.get("capacity_ah"),
            cca=attrs.get("cca"),
            polarity=attrs.get("polarity"),
            price=float(price),
            original_price=float(original_price) if original_price else None,
            currency=bbw.get("currency_id", "ARS"),
            installments_qty=installments.get("quantity"),
            installment_amount=installments.get("amount"),
            installment_rate=inst_rate,
            free_shipping=shipping.get("free_shipping", False),
            has_installation=has_installation,
            delivery_available=delivery_available,
            seller_name=seller.get("nickname"),
            seller_id=str(seller.get("id", "")),
            seller_reputation=seller.get("seller_reputation", {}).get("power_seller_status"),
            is_official_store=bbw.get("official_store_id") is not None,
            condition=bbw.get("condition"),
            available_quantity=bbw.get("available_quantity"),
            sold_quantity=bbw.get("sold_quantity") or item.get("sold_quantity"),
            raw_data=json.dumps({"item": item, "bbw": bbw}, ensure_ascii=False),
        )
    except Exception as e:
        logger.error(f"[ML] Error parseando ítem {item.get('id')}: {e}")
        return None


def _extract_attributes(attributes: list[dict]) -> dict:
    result: dict = {}
    for attr in attributes:
        attr_id = attr.get("id", "")
        field = ML_ATTRIBUTE_MAP.get(attr_id)
        if not field:
            continue
        value = attr.get("value_name")
        if value:
            result[field] = value
    return result
