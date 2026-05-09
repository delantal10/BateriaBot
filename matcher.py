"""
Identificador de modelos de batería.

Estrategia (en orden de confianza):
1. Regex por código de modelo en el título
2. Marca + Ah + CCA  ← método principal cuando no hay código explícito
3. Marca + Ah solo   ← fallback si no hay CCA disponible
"""

import re
import logging
from typing import Optional
from catalog import ALL_MODELS, CatalogModel, CATALOG_BY_ID

logger = logging.getLogger(__name__)

# ── Extracción de specs desde título ─────────────────────────────────────────

# Ah: "45Ah", "45 Ah", "45AH", "12x45" (voltaje x Ah)
_RE_AH = re.compile(
    r"(?:12\s*[xX×]\s*(\d+(?:[.,]\d+)?)"   # formato "12x45"
    r"|(\d+(?:[.,]\d+)?)\s*Ah)",             # formato "45Ah"
    re.IGNORECASE,
)

# CCA / SAE / EN: "500A SAE", "500 SAE", "500 CCA", "500A CCA", "500 EN"
# Excluye voltaje (12V) y Ah
_RE_CCA = re.compile(
    r"(\d{3,4})\s*A?\s*(?:SAE|CCA|EN)\b",
    re.IGNORECASE,
)
# Alternativa: número seguido de "A" suelto (ej. "430A") — solo si hay 3+ dígitos y no es Ah
_RE_CCA_BARE = re.compile(
    r"\b(\d{3,4})\s*A\b(?!\s*[Hh])",   # "430A" pero no "430Ah"
    re.IGNORECASE,
)


def extract_ah(text: str) -> Optional[float]:
    m = _RE_AH.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def extract_cca(text: str) -> Optional[int]:
    """Extrae CCA/SAE del título. Prefiere matches explícitos (SAE/CCA/EN)."""
    m = _RE_CCA.search(text)
    if m:
        return int(m.group(1))
    m = _RE_CCA_BARE.search(text)
    if m:
        val = int(m.group(1))
        # Descartar valores que parecen Ah (< 200) o voltaje
        if val >= 200:
            return val
    return None


# ── Patrones de modelo explícito ──────────────────────────────────────────────

_RE_UB        = re.compile(r"\bUB[\s\-]?(\d{3,4})\b", re.IGNORECASE)
_RE_MOURA_MOTO= re.compile(r"\bMA(\d{1,2})[\s\-]([ADI]{1,2})\b", re.IGNORECASE)
_RE_MOURA_SS  = re.compile(r"\b(MF|MA)(\d{2})([A-Z]{2})\b", re.IGNORECASE)
_RE_MOURA_100 = re.compile(r"\bM(E|F|A)?(\d{3})([A-Z]{2,3})\b", re.IGNORECASE)
_RE_MOURA_STD = re.compile(r"\b(ME?)(\d{2})([A-Z]{2,3})\b", re.IGNORECASE)

# ── Índice de aliases ─────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return text.upper().replace(" ", "").replace("-", "")

_ALIAS_INDEX: dict[str, CatalogModel] = {}
for _m in ALL_MODELS:
    for _alias in [_m.model_code] + _m.aliases:
        _ALIAS_INDEX[_norm(_alias)] = _m


# ── Matching por specs ────────────────────────────────────────────────────────

def _match_by_specs(
    brand: Optional[str],
    ah: Optional[float],
    cca: Optional[int],
    category: str = "auto",
) -> Optional[CatalogModel]:
    """
    Identifica modelo por marca + Ah + CCA.
    Tolerancias: ±3 Ah, ±30 CCA.
    """
    if not ah:
        return None

    brand_up = brand.upper() if brand else None

    candidates = [
        m for m in ALL_MODELS
        if m.category == category
        and (
            not brand_up
            or m.brand.upper() in brand_up
            or brand_up in m.brand.upper()
        )
        and abs((m.capacity_ah or -999) - ah) <= 3.0
    ]

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Con CCA podemos resolver la mayoría de ambigüedades
    if cca:
        with_cca = [c for c in candidates if abs((c.cca or -999) - cca) <= 30]
        if len(with_cca) == 1:
            return with_cca[0]
        if len(with_cca) > 1:
            # Aún ambiguo — devolver el de menor distancia combinada
            return min(
                with_cca,
                key=lambda c: abs((c.capacity_ah or 0) - ah) + abs((c.cca or 0) - cca) * 0.1,
            )

    # Sin CCA y múltiples candidatos: devolver solo si hay uno con Ah exacto
    exact_ah = [c for c in candidates if abs((c.capacity_ah or -999) - ah) <= 1.0]
    if len(exact_ah) == 1:
        return exact_ah[0]

    return None


# ── Función principal ─────────────────────────────────────────────────────────

def match_model(
    title: str,
    brand: Optional[str],
    capacity_ah: Optional[float],
    cca: Optional[int] = None,
) -> Optional[CatalogModel]:
    """
    Identifica el modelo de catálogo a partir de los datos del listing.
    capacity_ah y cca pueden venir del listing (atributos ML) o se extraen del título.
    """
    title_up = title.upper()

    # Completar specs desde el título si no vienen en los atributos
    ah  = capacity_ah or extract_ah(title)
    cca = cca or extract_cca(title)

    # ── 1. Código explícito UB ────────────────────────────────────────────────
    m = _RE_UB.search(title_up)
    if m:
        code = f"UB{m.group(1)}"
        brand_key = "unibat" if "UNIBAT" in title_up else "willard"
        result = CATALOG_BY_ID.get(f"{brand_key}_{code.lower()}")
        if result:
            return result
        result = _ALIAS_INDEX.get(_norm(code))
        if result:
            return result

    # ── 2. Moura moto MA#-X ──────────────────────────────────────────────────
    m = _RE_MOURA_MOTO.search(title_up)
    if m:
        code = f"MA{m.group(1)}-{m.group(2).upper()}"
        result = _ALIAS_INDEX.get(_norm(code))
        if result:
            return result

    # ── 3. Moura Start-Stop MF/MA (2-digit) ──────────────────────────────────
    m = _RE_MOURA_SS.search(title_up)
    if m:
        code = f"{m.group(1).upper()}{m.group(2)}{m.group(3).upper()}"
        result = _ALIAS_INDEX.get(_norm(code))
        if result:
            return result

    # ── 4. Moura 3-digit (M100HA, ME135BD …) ─────────────────────────────────
    m = _RE_MOURA_100.search(title_up)
    if m:
        prefix = (m.group(1) or "").upper()
        code = f"M{prefix}{m.group(2)}{m.group(3).upper()}"
        result = _ALIAS_INDEX.get(_norm(code))
        if result:
            return result

    # ── 5. Moura estándar 2-digit (M22GD, ME40FD …) ──────────────────────────
    m = _RE_MOURA_STD.search(title_up)
    if m:
        prefix = m.group(1).upper()
        code = f"{prefix}{m.group(2)}{m.group(3).upper()}"
        result = _ALIAS_INDEX.get(_norm(code))
        if result:
            return result

    # ── 6. Aliases literales ──────────────────────────────────────────────────
    title_norm = _norm(title)
    for alias_norm in sorted(_ALIAS_INDEX, key=len, reverse=True):
        if len(alias_norm) >= 4 and alias_norm in title_norm:
            return _ALIAS_INDEX[alias_norm]

    # ── 7. Marca + Ah + CCA (método principal sin código explícito) ───────────
    result = _match_by_specs(brand, ah, cca)
    if result:
        return result

    return None


def classify_listings(listings) -> None:
    """
    Anota catalog_model_id en cada listing in-place.
    Extrae Ah y CCA del título si no están en los atributos del listing.
    """
    if not listings:
        return
    matched = unmatched = 0
    for listing in listings:
        model = match_model(
            title=listing.title,
            brand=listing.brand,
            capacity_ah=listing.capacity_ah,
            cca=listing.cca,
        )
        listing.catalog_model_id = model.id if model else None
        if model:
            matched += 1
        else:
            unmatched += 1

    total = matched + unmatched
    pct = 100 * matched // total if total else 0
    logger.info(f"[matcher] {matched}/{total} listings clasificados ({pct}%) — {unmatched} sin match")
