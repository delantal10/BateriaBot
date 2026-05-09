"""
Scrapers HTML secundarios (best-effort).
Cada función captura lo que puede; si falla, logea el error y devuelve lista vacía.

Fuentes incluidas:
  - bateriasdeautos.com.ar  → distribuidora Moura con HTML estático
  - vzh.com.ar              → distribuidora Willard y otras marcas
  - carrefour.com.ar        → supermercado (API interna de búsqueda)
  - changomas.com.ar        → supermercado (ex-Walmart)
  - aca.org.ar              → beneficios ACA para socios (baterías)

NOTA sobre ACA: el sitio del ACA no publica precios de baterías en línea,
sino que lista los prestadores de servicio de batería adheridos. La función
aquí captura esos prestadores y la información de contacto disponible, lo
que sirve para saber dónde validar el precio presencial como socio ACA.
Los precios reales con descuento ACA deben consultarse directamente en
cada prestador adherido.
"""

import logging
import json
import re
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from models import Listing
from config import (
    DEFAULT_HEADERS, HTTP_TIMEOUT,
    CARREFOUR_QUERIES, CARREFOUR_EXCLUDE_KEYWORDS, MIN_CAR_BATTERY_PRICE_ARS,
)

logger = logging.getLogger(__name__)

# ─── helpers ──────────────────────────────────────────────────────────────────

def _get(url: str, params: Optional[dict] = None, is_json: bool = False):
    """GET sincrónico con User-Agent configurado. Devuelve texto o dict, o None si falla."""
    try:
        with httpx.Client(
            headers=DEFAULT_HEADERS,
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
            verify=False,  # algunos sitios argentinos tienen certs mal configurados
        ) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json() if is_json else resp.text
    except Exception as e:
        logger.warning(f"[HTML] GET {url} falló: {e}")
        return None


def _parse_price(text: str) -> Optional[float]:
    """Extrae el primer número de tipo precio de un string."""
    cleaned = re.sub(r"[^\d,.]", "", text.strip())
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


# ─── bateriasdeautos.com.ar ────────────────────────────────────────────────────

def scrape_bateriasdeautos() -> list[Listing]:
    """
    Scraper de lista de precios de baterías Moura en bateriasdeautos.com.ar.

    El sitio usa el plugin Divi Table Maker de WordPress. Estructura:
      div.dvmd_tm_trow  → fila completa (la primera es el header con class dvmd_tm_bhead)
      div.dvmd_tm_cdata → celda de datos dentro de cada fila

    Columnas en orden: Nombre Comercial | Aplicaciones | Precio 6 cuotas | Precio de oferta | Tienda
    """
    url = "https://www.bateriasdeautos.com.ar/encuentra-tu-bateria/lista-de-precios/"
    html = _get(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    listings: list[Listing] = []

    for row in soup.select("div.dvmd_tm_trow"):
        cells = [c.get_text(strip=True) for c in row.select("div.dvmd_tm_cdata")]

        # Estructura real del sitio — filas de datos (6 columnas):
        # [0]=Nombre Comercial  [1]=Specs(12xAh)  [2]=Aplicaciones
        # [3]=Precio 6 cuotas   [4]=Precio oferta  [5]=Tienda/Link
        # (el header tiene un campo vacío extra al inicio, pero los datos no)
        if len(cells) < 5:
            continue

        model = cells[0]
        # Saltar filas de encabezado repetidas (el header tiene "NOMBRE COMERCIAL" en cells[0] o cells[1])
        if not model or model.upper() in ("NOMBRE COMERCIAL", "") or "PRECIO" in model.upper():
            continue

        specs = cells[1]       # e.g. "12x50 (40Ah)"
        applications = cells[2]
        price_cuotas = _parse_price(cells[3])
        price_offer = _parse_price(cells[4])

        price = price_offer or price_cuotas
        if not price:
            continue

        # Extraer amperios desde el campo de specs "12x50 (40Ah)" o "45 Ah"
        capacity_ah = _extract_ah(specs)

        full_title = f"Moura {model}"
        if applications:
            full_title += f" — {applications}"

        listings.append(Listing(
            source="bateriasdeautos",
            title=full_title,
            brand="Moura",
            model=model,
            capacity_ah=capacity_ah,
            price=price,
            original_price=price_cuotas if price_cuotas and price_cuotas != price else None,
            installments_qty=6 if price_cuotas else None,
            installment_amount=round(price_cuotas / 6, 2) if price_cuotas else None,
            installment_rate=0.0,
            delivery_available=False,
            url=url,
        ))

    logger.info(f"[bateriasdeautos] {len(listings)} ítems encontrados")
    return listings


# ─── vzh.com.ar ────────────────────────────────────────────────────────────────

def scrape_vzh() -> list[Listing]:
    """Scraper del catálogo de baterías de vzh.com.ar."""
    url = "https://www.vzh.com.ar/baterias"
    html = _get(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    listings: list[Listing] = []

    # Selector genérico: ajustar si el sitio cambia su estructura
    for item in soup.select(".product-item, .item, article.product"):
        title_el = item.select_one(".product-title, h2, h3, .name")
        price_el = item.select_one(".price, .product-price, [class*='price']")
        link_el = item.select_one("a[href]")

        if not title_el or not price_el:
            continue

        title = title_el.get_text(strip=True)
        price = _parse_price(price_el.get_text(strip=True))
        if not price:
            continue

        listings.append(Listing(
            source="vzh",
            title=title,
            brand=_guess_brand(title),
            price=price,
            delivery_available=True,
            url=("https://www.vzh.com.ar" + link_el["href"]) if link_el else url,
        ))

    logger.info(f"[vzh] {len(listings)} ítems encontrados")
    return listings


# ─── Easy ──────────────────────────────────────────────────────────────────────

def scrape_easy() -> list[Listing]:
    """
    Scraper de baterías de auto en Easy Argentina (plataforma VTEX).
    Easy vende baterías de arranque reales (marcas Mateo, Champion, Conroll).
    Útil como referencia de precio en grandes superficies.
    """
    url = "https://www.easy.com.ar/api/catalog_system/pub/products/search/bateria%20auto%2012v"
    data = _get(url, params={"_from": 0, "_to": 49}, is_json=True)

    if not data or not isinstance(data, list):
        logger.info("[Easy] Sin resultados o API no disponible")
        return []

    listings: list[Listing] = []
    for product in data:
        try:
            name = product.get("productName", "")
            if not name:
                continue

            name_lower = name.lower()
            if any(kw in name_lower for kw in CARREFOUR_EXCLUDE_KEYWORDS):
                continue

            items = product.get("items", [{}])
            sellers = items[0].get("sellers", [{}]) if items else [{}]
            offer = sellers[0].get("commertialOffer", {}) if sellers else {}
            price = offer.get("Price")

            if not price or float(price) < MIN_CAR_BATTERY_PRICE_ARS:
                continue

            original = offer.get("ListPrice")
            installments_raw = offer.get("Installments", [])
            best_inst = _best_installment(installments_raw)

            listings.append(Listing(
                source="easy",
                external_id=str(product.get("productId", "")),
                url=f"https://www.easy.com.ar/{product.get('linkText', '')}",
                title=name,
                brand=_guess_brand(name),
                price=float(price),
                original_price=float(original) if original else None,
                installments_qty=best_inst.get("qty"),
                installment_amount=best_inst.get("amount"),
                installment_rate=best_inst.get("rate"),
                delivery_available=True,
                raw_data=json.dumps(product, ensure_ascii=False),
            ))
        except Exception as e:
            logger.debug(f"[Easy] Error parseando producto: {e}")

    logger.info(f"[Easy] {len(listings)} ítems encontrados")
    return listings



def _best_installment(installments: list) -> dict:
    """Selecciona el plan de cuotas con mayor cantidad y tasa 0 si existe."""
    zero_rate = [i for i in installments if i.get("InterestRate", 1) == 0]
    candidates = zero_rate or installments
    if not candidates:
        return {}
    best = max(candidates, key=lambda i: i.get("NumberOfInstallments", 0))
    return {
        "qty": best.get("NumberOfInstallments"),
        "amount": best.get("Value"),
        "rate": best.get("InterestRate"),
    }




# ─── Fravega ───────────────────────────────────────────────────────────────────

def scrape_fravega() -> list[Listing]:
    """
    Scraper de Fravega Argentina (plataforma VTEX Legacy).
    Tiene Willard blindadas con descuentos y planes de hasta 24 cuotas.
    """
    base = "https://www.fravega.com/api/catalog_system/pub/products/search"
    queries = ["bateria willard", "bateria moura", "bateria auto 12v"]
    seen_ids: set[str] = set()
    listings: list[Listing] = []

    for query in queries:
        url = f"{base}/{query.replace(' ', '%20')}"
        data = _get(url, params={"_from": 0, "_to": 49}, is_json=True)
        if not data or not isinstance(data, list):
            continue

        for product in data:
            try:
                name = product.get("productName", "")
                if not name:
                    continue
                name_lower = name.lower()
                if any(kw in name_lower for kw in CARREFOUR_EXCLUDE_KEYWORDS):
                    continue

                items = product.get("items", [{}])
                sellers = items[0].get("sellers", [{}]) if items else [{}]
                offer = sellers[0].get("commertialOffer", {}) if sellers else {}
                price = offer.get("Price")
                if not price or float(price) < MIN_CAR_BATTERY_PRICE_ARS:
                    continue

                product_id = str(product.get("productId", ""))
                if product_id in seen_ids:
                    continue
                seen_ids.add(product_id)

                original = offer.get("ListPrice")
                best_inst = _best_installment(offer.get("Installments", []))
                link = product.get("link", "") or ""

                listings.append(Listing(
                    source="fravega",
                    external_id=product_id,
                    url=link if link.startswith("http") else f"https://www.fravega.com{link}",
                    title=name,
                    brand=_guess_brand(name),
                    price=float(price),
                    original_price=float(original) if original else None,
                    installments_qty=best_inst.get("qty"),
                    installment_amount=best_inst.get("amount"),
                    installment_rate=best_inst.get("rate"),
                    delivery_available=True,
                    raw_data=json.dumps(product, ensure_ascii=False),
                ))
            except Exception as e:
                logger.debug(f"[Fravega] Error parseando producto: {e}")

    logger.info(f"[Fravega] {len(listings)} ítems encontrados")
    return listings


# ─── Norauto ───────────────────────────────────────────────────────────────────

def scrape_norauto() -> list[Listing]:
    """
    Scraper de Norauto Argentina (plataforma VTEX Legacy).
    Tiene Moura, Mateo, Eurorepar y Cobelak. Servicio de instalación en local.
    """
    url = "https://www.norauto.com.ar/api/catalog_system/pub/products/search/bateria%20auto%2012v"
    data = _get(url, params={"_from": 0, "_to": 49}, is_json=True)

    if not data or not isinstance(data, list):
        logger.info("[Norauto] Sin resultados o API no disponible")
        return []

    listings: list[Listing] = []
    for product in data:
        try:
            name = product.get("productName", "")
            if not name:
                continue
            name_lower = name.lower()
            if any(kw in name_lower for kw in CARREFOUR_EXCLUDE_KEYWORDS):
                continue

            items = product.get("items", [{}])
            sellers = items[0].get("sellers", [{}]) if items else [{}]
            offer = sellers[0].get("commertialOffer", {}) if sellers else {}
            price = offer.get("Price")
            if not price or float(price) < MIN_CAR_BATTERY_PRICE_ARS:
                continue

            original = offer.get("ListPrice")
            best_inst = _best_installment(offer.get("Installments", []))
            link = product.get("link", "") or ""

            listings.append(Listing(
                source="norauto",
                external_id=str(product.get("productId", "")),
                url=link if link.startswith("http") else f"https://www.norauto.com.ar{link}",
                title=name,
                brand=_guess_brand(name) or product.get("brand"),
                price=float(price),
                original_price=float(original) if original else None,
                installments_qty=best_inst.get("qty"),
                installment_amount=best_inst.get("amount"),
                installment_rate=best_inst.get("rate"),
                has_installation=True,   # Norauto tiene servicio de instalación en local
                delivery_available=True,
                raw_data=json.dumps(product, ensure_ascii=False),
            ))
        except Exception as e:
            logger.debug(f"[Norauto] Error parseando producto: {e}")

    logger.info(f"[Norauto] {len(listings)} ítems encontrados")
    return listings


# ─── ACA (Automóvil Club Argentino) ────────────────────────────────────────────

def scrape_aca() -> list[Listing]:
    """
    El ACA no publica precios de baterías online: ofrece descuentos en
    prestadores adheridos que deben consultarse presencialmente.

    Esta función captura la lista de prestadores de batería adheridos al ACA
    y los guarda como registros informativos (sin precio) para que el socio
    sepa a qué locales concurrir para obtener el precio con descuento ACA.

    Fuente: https://www.aca.org.ar/pages/categorias/baterias
    """
    url = "https://www.aca.org.ar/pages/categorias/baterias"
    html = _get(url)
    if not html:
        # Intento alternativo de la sección de beneficios
        url = "https://www.aca.org.ar/pages/beneficios"
        html = _get(url)
    if not html:
        logger.info("[ACA] Sitio no disponible — sin datos")
        return []

    soup = BeautifulSoup(html, "html.parser")
    listings: list[Listing] = []

    # El ACA lista prestadores como tarjetas o filas con nombre, dirección, teléfono
    for card in soup.select(".prestador, .beneficio, .card, article"):
        name_el = card.select_one("h2, h3, h4, .name, .title, strong")
        if not name_el:
            continue

        name = name_el.get_text(strip=True)
        if not name or len(name) < 3:
            continue

        # Busca dirección y teléfono como contexto
        address_el = card.select_one(".address, .direccion, [class*='address']")
        phone_el = card.select_one(".phone, .telefono, [class*='phone']")
        address = address_el.get_text(strip=True) if address_el else ""
        phone = phone_el.get_text(strip=True) if phone_el else ""

        extra = f"{address} | {phone}".strip(" |")
        title = f"[ACA Prestador] {name}" + (f" — {extra}" if extra else "")

        # Precio 0 indica "informativo / consultar precio"
        listings.append(Listing(
            source="aca",
            title=title,
            price=0.0,
            delivery_available=False,
            url=url,
        ))

    if not listings:
        # Si no encontró tarjetas estructuradas, guarda una entrada genérica
        listings.append(Listing(
            source="aca",
            title="[ACA] Beneficio batería — consultar prestadores en aca.org.ar/pages/categorias/baterias",
            price=0.0,
            delivery_available=False,
            url=url,
        ))
        logger.info("[ACA] No se encontraron prestadores estructurados; entrada genérica guardada")
    else:
        logger.info(f"[ACA] {len(listings)} prestadores encontrados")

    return listings


# ─── Utilidades ────────────────────────────────────────────────────────────────

def _extract_ah(text: str) -> Optional[float]:
    """Extrae capacidad en Ah de strings como '12x50 (40Ah)' o '45 Ah'."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*[Aa][Hh]", text)
    if m:
        return float(m.group(1).replace(",", "."))
    # Formato "VxAh" e.g. "12x50" → 50 Ah
    m2 = re.search(r"\d+x(\d+)", text)
    if m2:
        return float(m2.group(1))
    return None


_BRAND_KEYWORDS = {
    "willard": "Willard",
    "unibat": "Unibat",
    "moura": "Moura",
    "bosch": "Bosch",
    "varta": "Varta",
    "fiamm": "Fiamm",
    "ac delco": "AC Delco",
    "acdelco": "AC Delco",
    "remy": "Remy",
    "tudor": "Tudor",
    "banner": "Banner",
}

def _guess_brand(title: str) -> Optional[str]:
    """Intenta detectar la marca a partir del título del producto."""
    lower = title.lower()
    for keyword, brand in _BRAND_KEYWORDS.items():
        if keyword in lower:
            return brand
    return None
