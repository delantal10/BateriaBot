"""
Catálogo oficial de modelos Willard/Unibat y Moura.
Fuente: "Comparativas UNIONBAT - MOURA.xlsx" (Ejercicio 2025-2026)

Para agregar un modelo: copiar una entrada existente y ajustar los valores.
Para actualizar specs: editar capacity_ah, cca, etc. de la entrada correspondiente.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CatalogModel:
    brand: str                      # "Willard", "Unibat", "Moura"
    model_code: str                 # Código oficial, ej. "UB620", "M22GD"
    aliases: list[str]              # Variantes de nombre en títulos de venta
    capacity_ah: Optional[float]    # Amperios-hora
    cca: Optional[int]              # Cold Cranking Amps (SAE)
    voltage_v: float = 12.0
    type: str = "standard"          # "standard" | "agm" | "efb" | "gel"
    category: str = "auto"          # "auto" | "start_stop" | "moto" | "industrial"
    polarity: Optional[str] = None  # "D" (derecha) | "I" (izquierda) | "D/I" (ambas)
    notes: str = ""

    @property
    def id(self) -> str:
        return f"{self.brand.lower().replace(' ', '_')}_{self.model_code.lower()}"


# ─────────────────────────────────────────────────────────────────────────────
# Willard / Unibat — Línea Auto estándar
# ─────────────────────────────────────────────────────────────────────────────
WILLARD_MODELS: list[CatalogModel] = [
    CatalogModel(
        brand="Willard", model_code="UB325",
        aliases=["UB 325", "UB-325", "325"],
        capacity_ah=32.0, cca=300, polarity="D",
        notes="Autos pequeños (Up!, Agile, Ká)",
    ),
    CatalogModel(
        brand="Willard", model_code="UB425",
        aliases=["UB 425", "UB-425", "425"],
        capacity_ah=42.0, cca=350, polarity="D",
        notes="Autos chicos-medianos",
    ),
    CatalogModel(
        brand="Willard", model_code="UB450",
        aliases=["UB 450", "UB-450", "450"],
        capacity_ah=45.0, cca=390, polarity="D",
        notes="Autos medianos (Gol, Palio, Fox)",
    ),
    CatalogModel(
        brand="Willard", model_code="UB620",
        aliases=["UB 620", "UB-620", "620"],
        capacity_ah=62.0, cca=520, polarity="D/I",
        notes="Autos medianos-altos (Logan, Sandero, Suran)",
    ),
    CatalogModel(
        brand="Willard", model_code="UB670",
        aliases=["UB 670", "UB-670", "670"],
        capacity_ah=67.0, cca=560, polarity="D",
        notes="Autos medianos con mayor demanda eléctrica",
    ),
    CatalogModel(
        brand="Willard", model_code="UB710",
        aliases=["UB 710", "UB-710", "710"],
        capacity_ah=71.0, cca=600,
        notes="SUVs medianas y pickups chicas",
    ),
    CatalogModel(
        brand="Willard", model_code="UB730",
        aliases=["UB 730", "UB-730", "730"],
        capacity_ah=73.0, cca=610, polarity="D/I",
        notes="SUVs y pickups medianas",
    ),
    CatalogModel(
        brand="Willard", model_code="UB740",
        aliases=["UB 740", "UB-740", "740"],
        capacity_ah=74.0, cca=640, polarity="D/I",
        notes="SUVs con alta demanda eléctrica",
    ),
    CatalogModel(
        brand="Willard", model_code="UB840",
        aliases=["UB 840", "UB-840", "840"],
        capacity_ah=84.0, cca=720, polarity="D/I",
        notes="Pickups y SUVs grandes (Hilux, S10, Amarok)",
    ),
    CatalogModel(
        brand="Willard", model_code="UB920",
        aliases=["UB 920", "UB-920", "920"],
        capacity_ah=92.0, cca=800, type="agm", polarity="I",
        notes="AGM — vehículos con alta demanda / Start-Stop",
    ),
    CatalogModel(
        brand="Willard", model_code="UB930",
        aliases=["UB 930", "UB-930", "930"],
        capacity_ah=93.0, cca=800,
        notes="Camionetas grandes y vehículos diesel pesados",
    ),
    CatalogModel(
        brand="Willard", model_code="UB980",
        aliases=["UB 980", "UB-980", "UB 1030", "UB-1030", "980", "1030"],
        capacity_ah=98.0, cca=850, polarity="D",
        notes="Camiones medianos y vehículos diesel de alta demanda",
    ),
    CatalogModel(
        brand="Willard", model_code="UB1100",
        aliases=["UB 1100", "UB-1100", "UB 1100+D", "1100"],
        capacity_ah=110.0, cca=950,
        notes="Camiones pesados",
    ),
    CatalogModel(
        brand="Willard", model_code="UB1300",
        aliases=["UB 1300", "UB-1300", "1300"],
        capacity_ah=130.0, cca=1100,
        notes="Camiones y maquinaria pesada",
    ),
]

# Unibat = misma empresa que Willard, mismos modelos con distinto nombre de marca
UNIBAT_MODELS: list[CatalogModel] = [
    CatalogModel(
        brand="Unibat",
        model_code=m.model_code,
        aliases=m.aliases,
        capacity_ah=m.capacity_ah,
        cca=m.cca,
        voltage_v=m.voltage_v,
        type=m.type,
        category=m.category,
        polarity=m.polarity,
        notes=m.notes,
    )
    for m in WILLARD_MODELS
]


# ─────────────────────────────────────────────────────────────────────────────
# Moura — Línea Auto estándar
# ─────────────────────────────────────────────────────────────────────────────
MOURA_AUTO_MODELS: list[CatalogModel] = [
    CatalogModel(
        brand="Moura", model_code="ME40FD",
        aliases=["ME 40 FD", "ME40FD", "ME 40FD", "40FD"],
        capacity_ah=40.0, cca=330,
        notes="Autos pequeños (Agile, Up!, Ká)",
    ),
    CatalogModel(
        brand="Moura", model_code="M18FD",
        aliases=["M 18 FD", "M18FD", "M 18FD", "18FD"],
        capacity_ah=45.0, cca=390,
        notes="Autos medianos (Gol, Palio, Fox)",
    ),
    CatalogModel(
        brand="Moura", model_code="M18SD",
        aliases=["M 18 SD", "M18SD", "M 18SD", "18SD"],
        capacity_ah=45.0, cca=390,
        notes="Autos chicos-medianos, polaridad inversa",
    ),
    CatalogModel(
        brand="Moura", model_code="M40FD",
        aliases=["M 40 FD", "M40FD", "M 40FD"],
        capacity_ah=45.0, cca=390,
        notes="Variante M40 serie FD",
    ),
    CatalogModel(
        brand="Moura", model_code="M22ED",
        aliases=["M 22 ED", "M22ED", "M 22ED", "22ED"],
        capacity_ah=55.0, cca=460,
        notes="Autos medianos",
    ),
    CatalogModel(
        brand="Moura", model_code="M22GD",
        aliases=["M 22 GD", "M22GD", "M 22GD", "22GD"],
        capacity_ah=60.0, cca=500,
        notes="Autos medianos (Sandero, Etios, Suran)",
    ),
    CatalogModel(
        brand="Moura", model_code="M20GD",
        aliases=["M 20 GD", "M20GD", "M 20GD", "20GD"],
        capacity_ah=60.0, cca=480,
        notes="Variante M20GD",
    ),
    CatalogModel(
        brand="Moura", model_code="M22JD",
        aliases=["M 22 JD", "M22JD", "M 22JD", "22JD"],
        capacity_ah=65.0, cca=540,
        notes="Autos medianos-altos",
    ),
    CatalogModel(
        brand="Moura", model_code="M22RD",
        aliases=["M 22 RD", "M22RD", "M 22RD", "22RD"],
        capacity_ah=70.0, cca=580,
        notes="SUVs medianas",
    ),
    CatalogModel(
        brand="Moura", model_code="M23GD",
        aliases=["M 23 GD", "M23GD", "M 23GD", "23GD"],
        capacity_ah=65.0, cca=560,
        notes="Autos medianos-altos",
    ),
    CatalogModel(
        brand="Moura", model_code="M24GD",
        aliases=["M 24 GD", "M24GD", "M 24GD", "24GD"],
        capacity_ah=70.0, cca=580,
        notes="SUVs medianas (Duster, T-Cross)",
    ),
    CatalogModel(
        brand="Moura", model_code="M24KD",
        aliases=["M 24 KD", "M24KD", "M 24KD", "24KD"],
        capacity_ah=70.0, cca=600,
        notes="SUVs con mayor demanda eléctrica",
    ),
    CatalogModel(
        brand="Moura", model_code="M26AD",
        aliases=["M 26 AD", "M26AD", "M 26AD", "26AD"],
        capacity_ah=75.0, cca=620,
        notes="Pickups medianas (Amarok 2.0, Ranger diesel)",
    ),
    CatalogModel(
        brand="Moura", model_code="M26GD",
        aliases=["M 26 GD", "M26GD", "M 26GD", "26GD"],
        capacity_ah=75.0, cca=640,
        notes="Pickups y SUVs grandes",
    ),
    CatalogModel(
        brand="Moura", model_code="M28KD",
        aliases=["M 28 KD", "M28KD", "M 28KD", "28KD"],
        capacity_ah=90.0, cca=750,
        notes="Pickups grandes (Hilux, S10, Amarok V6)",
    ),
    CatalogModel(
        brand="Moura", model_code="M30LD",
        aliases=["M 30 LD", "M30LD", "M 30LD", "30LD"],
        capacity_ah=85.0, cca=700,
        notes="Pickups grandes y SUVs de alta demanda",
    ),
    CatalogModel(
        brand="Moura", model_code="M90TD",
        aliases=["M 90 TD", "M90TD", "M 90TD", "90TD"],
        capacity_ah=93.0, cca=800,
        notes="Camionetas grandes y vehículos pesados",
    ),
    CatalogModel(
        brand="Moura", model_code="ME95QD",
        aliases=["ME 95 QD", "ME95QD", "ME 95QD", "95QD"],
        capacity_ah=95.0, cca=850,
        notes="Camiones medianos",
    ),
    CatalogModel(
        brand="Moura", model_code="M100HA",
        aliases=["M 100 HA", "M100HA", "M 100HA", "100HA"],
        capacity_ah=100.0, cca=900, type="agm",
        notes="AGM — alta demanda / vehículos pesados",
    ),
    CatalogModel(
        brand="Moura", model_code="ME135BD",
        aliases=["ME 135 BD", "ME135BD", "ME 135BD", "135BD"],
        capacity_ah=135.0, cca=1000,
        notes="Camiones pesados",
    ),
    CatalogModel(
        brand="Moura", model_code="ME150BD",
        aliases=["ME 150 BD", "ME150BD", "ME 150BD", "150BD"],
        capacity_ah=150.0, cca=1100,
        notes="Camiones pesados",
    ),
    CatalogModel(
        brand="Moura", model_code="M180BD",
        aliases=["M 180 BD", "M180BD", "M 180BD", "180BD"],
        capacity_ah=180.0, cca=1200,
        notes="Camiones y maquinaria pesada",
    ),
]

# ── Moura Start-Stop ──────────────────────────────────────────────────────────
MOURA_STARTSTOP_MODELS: list[CatalogModel] = [
    CatalogModel(
        brand="Moura", model_code="MF60AD",
        aliases=["MF 60 AD", "MF60AD", "MF 60AD"],
        capacity_ah=60.0, cca=540, type="efb", category="start_stop",
        notes="EFB Start-Stop 60Ah",
    ),
    CatalogModel(
        brand="Moura", model_code="MF72LD",
        aliases=["MF 72 LD", "MF72LD", "MF 72LD"],
        capacity_ah=72.0, cca=650, type="efb", category="start_stop",
        notes="EFB Start-Stop 72Ah",
    ),
    CatalogModel(
        brand="Moura", model_code="MF80CD",
        aliases=["MF 80 CD", "MF80CD", "MF 80CD"],
        capacity_ah=80.0, cca=720, type="efb", category="start_stop",
        notes="EFB Start-Stop 80Ah",
    ),
    CatalogModel(
        brand="Moura", model_code="MA80CD",
        aliases=["MA 80 CD", "MA80CD", "MA 80CD"],
        capacity_ah=80.0, cca=800, type="agm", category="start_stop",
        notes="AGM Start-Stop 80Ah",
    ),
]

# ── Moura Moto ────────────────────────────────────────────────────────────────
MOURA_MOTO_MODELS: list[CatalogModel] = [
    CatalogModel(brand="Moura", model_code="MA3-AD",  aliases=["MA3AD", "MA 3-AD"], capacity_ah=3.0,  cca=None, type="agm", category="moto", voltage_v=12.0),
    CatalogModel(brand="Moura", model_code="MA5-AD",  aliases=["MA5AD", "MA 5-AD"], capacity_ah=5.0,  cca=None, type="agm", category="moto", voltage_v=12.0),
    CatalogModel(brand="Moura", model_code="MA5-D",   aliases=["MA5D",  "MA 5-D"],  capacity_ah=5.0,  cca=None, type="agm", category="moto", voltage_v=12.0),
    CatalogModel(brand="Moura", model_code="MA6-D",   aliases=["MA6D",  "MA 6-D"],  capacity_ah=6.0,  cca=None, type="agm", category="moto", voltage_v=12.0),
    CatalogModel(brand="Moura", model_code="MA6-I",   aliases=["MA6I",  "MA 6-I"],  capacity_ah=6.0,  cca=None, type="agm", category="moto", voltage_v=12.0),
    CatalogModel(brand="Moura", model_code="MA8-I",   aliases=["MA8I",  "MA 8-I"],  capacity_ah=8.0,  cca=None, type="agm", category="moto", voltage_v=12.0),
]


# ─────────────────────────────────────────────────────────────────────────────
# Índice unificado
# ─────────────────────────────────────────────────────────────────────────────
ALL_MODELS: list[CatalogModel] = (
    WILLARD_MODELS
    + UNIBAT_MODELS
    + MOURA_AUTO_MODELS
    + MOURA_STARTSTOP_MODELS
    + MOURA_MOTO_MODELS
)

CATALOG_BY_ID: dict[str, CatalogModel] = {m.id: m for m in ALL_MODELS}


# ─────────────────────────────────────────────────────────────────────────────
# Equivalencias Willard/Unibat ↔ Moura
# Fuente: "Comparativas UNIONBAT - MOURA.xlsx"
# Formato: { willard_model_id : moura_model_id }
# ─────────────────────────────────────────────────────────────────────────────
EQUIVALENCES: dict[str, str] = {
    "willard_ub325":  "moura_m18sd",
    "willard_ub425":  "moura_m22jd",
    "willard_ub450":  "moura_m18fd",
    "willard_ub620":  "moura_m22gd",
    "willard_ub670":  "moura_m22ed",
    "willard_ub710":  "moura_m22rd",
    "willard_ub730":  "moura_m26ad",
    "willard_ub740":  "moura_m24kd",
    "willard_ub840":  "moura_m30ld",
    "willard_ub920":  "moura_m100ha",
    "willard_ub930":  "moura_m90td",
    "willard_ub980":  "moura_me95qd",
    "willard_ub1100": "moura_me135bd",
    "willard_ub1300": "moura_me150bd",
}

# Equivalencias inversas (Moura → Willard) generadas automáticamente
EQUIVALENCES_INVERSE: dict[str, str] = {v: k for k, v in EQUIVALENCES.items()}

# Unibat usa los mismos modelos que Willard
EQUIVALENCES.update({
    k.replace("willard_", "unibat_"): v
    for k, v in EQUIVALENCES.items()
    if k.startswith("willard_")
})


def get_equivalent(model_id: str) -> Optional[CatalogModel]:
    """Dado el id de un modelo, devuelve el modelo equivalente de la otra marca."""
    eq_id = EQUIVALENCES.get(model_id) or EQUIVALENCES_INVERSE.get(model_id)
    if eq_id:
        return CATALOG_BY_ID.get(eq_id)
    return None


from typing import Optional  # noqa: E402 — necesario para get_equivalent
