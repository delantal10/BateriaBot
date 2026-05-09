#!/usr/bin/env python3
"""
Exporta las cookies de sesión de MercadoLibre desde Chrome.
Usalo para actualizar Streamlit secrets cuando las cookies expiran.

Uso:
    python3 export_ml_cookies.py
"""

import os
from pathlib import Path

CHROME_PROFILE = Path.home() / "Library/Application Support/Google/Chrome/Profile 1/Cookies"
COOKIE_KEYS = ["ssid", "p_dsid", "p_edsid", "x-meli-session-id", "dsid", "edsid"]
ENV_NAMES = {
    "ssid":              "ML_COOKIE_SSID",
    "p_dsid":            "ML_COOKIE_P_DSID",
    "p_edsid":           "ML_COOKIE_P_EDSID",
    "x-meli-session-id": "ML_COOKIE_SESSION_ID",
    "dsid":              "ML_COOKIE_DSID",
    "edsid":             "ML_COOKIE_EDSID",
}

try:
    import browser_cookie3
except ImportError:
    print("Instalá browser-cookie3: pip install browser-cookie3")
    raise SystemExit(1)

jar = browser_cookie3.chrome(cookie_file=str(CHROME_PROFILE), domain_name="mercadolibre")
cookies = {c.name: c.value for c in jar}

if not cookies.get("ssid"):
    print("ERROR: No hay sesión activa de ML en Chrome.")
    print("Abrí mercadolibre.com.ar, iniciá sesión y volvé a correr este script.")
    raise SystemExit(1)

print("=" * 60)
print("Cookies de MercadoLibre exportadas OK")
print("=" * 60)
print()
print("─── Para .env local ────────────────────────────────────────")
for key in COOKIE_KEYS:
    val = cookies.get(key, "")
    if val:
        print(f'{ENV_NAMES[key]}={val}')

print()
print("─── Para Streamlit secrets (secrets.toml) ──────────────────")
for key in COOKIE_KEYS:
    val = cookies.get(key, "")
    if val:
        print(f'{ENV_NAMES[key]} = "{val}"')

print()
print("─── Instrucciones ──────────────────────────────────────────")
print("1. Copiá los valores de arriba")
print("2. En Streamlit Cloud → tu app → Settings → Secrets")
print("3. Pegá y guardá")
print("4. La app va a usar estas cookies automáticamente")
print()
print("Las cookies duran varias semanas. Cuando ML dé 0 resultados,")
print("volvé a correr este script.")
