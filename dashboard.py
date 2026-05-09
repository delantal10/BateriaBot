#!/usr/bin/env python3
"""
BateriaBot Dashboard — ACA
Correr con: streamlit run dashboard.py
"""

import os
import base64
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

def _logo_b64() -> str:
    logo = Path(__file__).parent / "assets" / "logo_aca.png"
    if logo.exists():
        return base64.b64encode(logo.read_bytes()).decode()
    return ""

LOGO_B64 = _logo_b64()

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from supabase import create_client

# ── Configuración de página ───────────────────────────────────────────────────

st.set_page_config(
    page_title="BateriaBot · ACA",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── ACA brand colors ──
# Rojo ACA:    #DA2F37
# Amarillo ACA:#F5C200
# Fondo:       #F4F4F4
# Card:        #FFFFFF
# Texto:       #1A1A1A
# Gris suave:  #6B7280

st.markdown("""
<style>
/* ── Reset global a tema claro ACA ── */
.stApp { background-color: #F4F4F4 !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #1A1A1A !important;
    border-right: 3px solid #DA2F37;
}
section[data-testid="stSidebar"] * { color: #F4F4F4 !important; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stNumberInput label { color: #F5C200 !important; font-weight: 600; }
section[data-testid="stSidebar"] hr { border-color: #333; }

/* ── KPI cards ── */
div[data-testid="metric-container"] {
    background: #FFFFFF;
    border: none;
    border-left: 5px solid #DA2F37;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
div[data-testid="stMetricLabel"] { color: #6B7280 !important; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
div[data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 800; color: #1A1A1A !important; }
div[data-testid="stMetricDelta"] { font-size: 0.85rem !important; }

/* ── Dataframe ── */
div[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    background: white;
}

/* ── Títulos y texto principal ── */
h1 { color: #DA2F37 !important; font-weight: 800 !important; }
h2, h3 { color: #1A1A1A !important; font-weight: 700 !important; }
p, li, label { color: #1A1A1A !important; }

/* ── Botones ── */
div[data-testid="stFormSubmitButton"] > button {
    background: #DA2F37 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    letter-spacing: 0.03em;
}
div[data-testid="stFormSubmitButton"] > button:hover {
    background: #B02028 !important;
}

/* ── Multiselect y sliders ── */
div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: #DA2F37 !important;
    color: white !important;
}
div[data-testid="stSlider"] div[role="slider"] { background: #DA2F37 !important; }

/* ── Expander ── */
details { background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); padding: 0.5rem; }

/* ── Divider ── */
hr { border-color: #E5E7EB !important; }

/* ── Captions ── */
div[data-testid="stCaptionContainer"] { color: #6B7280 !important; }

/* ── Header strip con logo ACA ── */
.aca-header {
    background: linear-gradient(135deg, #DA2F37 60%, #B02028 100%);
    color: white;
    padding: 1.2rem 2rem;
    border-radius: 14px;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    box-shadow: 0 4px 16px rgba(204,0,0,0.25);
}
.aca-header h1 { color: white !important; margin: 0; font-size: 1.8rem; }
.aca-header .subtitle { color: rgba(255,255,255,0.85); font-size: 0.95rem; margin-top: 0.2rem; }
.aca-logo { font-size: 2.8rem; }
.aca-badge {
    background: #F5C200;
    color: #1A1A1A;
    font-weight: 800;
    font-size: 0.75rem;
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 0.05em;
    margin-left: auto;
}
</style>
""", unsafe_allow_html=True)

# ── Constantes ────────────────────────────────────────────────────────────────

SOURCE_LABELS = {
    "mercadolibre":    "MercadoLibre",
    "fravega":         "Fravega",
    "norauto":         "Norauto",
    "bateriasdeautos": "Baterías de Autos",
    "easy":            "Easy",
}
SOURCES = list(SOURCE_LABELS.keys())

DELTA_COMPETITIVE = 5    # % — verde: ACA está bien
DELTA_WARNING     = 15   # % — amarillo: ACA está un poco alto

# Ventas ejercicio 2025-2026 (unidades vendidas por ACA, fuente: planilla Excel)
SALES_UNITS: dict[str, int] = {
    "willard_ub730":  1384,
    "willard_ub620":  1256,
    "willard_ub840":   545,
    "willard_ub740":   456,
    "willard_ub450":   292,
    "willard_ub920":    67,
    "willard_ub710":    18,
    "willard_ub325":    11,
    "willard_ub980":     8,
    "willard_ub930":     8,
    "willard_ub1300":    7,
    "willard_ub425":     4,
    "willard_ub670":     2,
}


def fmt_ars(v):
    if pd.isna(v) or v is None:
        return "—"
    return f"${v:,.0f}".replace(",", ".")


def delta_emoji(pct):
    if pct is None or pd.isna(pct):
        return "—"
    if pct <= DELTA_COMPETITIVE:
        return f"{pct:+.1f}%"
    if pct <= DELTA_WARNING:
        return f"{pct:+.1f}%"
    return f"{pct:+.1f}%"


# ── Supabase ──────────────────────────────────────────────────────────────────

@st.cache_resource
def get_supabase():
    # Lee de Streamlit Cloud secrets si está deployado, sino del .env local
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (KeyError, FileNotFoundError):
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        st.error("Faltan SUPABASE_URL o SUPABASE_KEY")
        st.stop()
    return create_client(url, key)


# ── Carga de datos ────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_catalog() -> pd.DataFrame:
    sb = get_supabase()
    data = (
        sb.table("catalog")
        .select("id,brand,model_code,capacity_ah,cca,type,category,polarity")
        .execute().data
    )
    return pd.DataFrame(data)


@st.cache_data(ttl=300)
def load_equivalences() -> pd.DataFrame:
    sb = get_supabase()
    data = sb.table("catalog_equivalences").select("model_id,equivalent_model_id").execute().data
    return pd.DataFrame(data)


@st.cache_data(ttl=300)
def load_listings() -> pd.DataFrame:
    sb = get_supabase()
    data = (
        sb.table("listings")
        .select("catalog_model_id,source,price,url,free_shipping,installments_qty,installment_rate,scraped_at,seller_name")
        .not_.is_("catalog_model_id", "null")
        .in_("source", SOURCES)
        .order("scraped_at", desc=True)
        .limit(5000)
        .execute().data
    )
    df = pd.DataFrame(data)
    if not df.empty:
        df["scraped_at"] = pd.to_datetime(df["scraped_at"], utc=True)
    return df


@st.cache_data(ttl=60)
def load_aca_prices() -> pd.DataFrame:
    sb = get_supabase()
    try:
        data = sb.table("aca_prices").select("*").execute().data
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame(columns=["catalog_model_id", "price_member", "price_non_member", "updated_at"])


@st.cache_data(ttl=300)
def load_last_run() -> str:
    sb = get_supabase()
    data = (
        sb.table("scrape_runs")
        .select("finished_at")
        .eq("status", "success")
        .order("finished_at", desc=True)
        .limit(1)
        .execute().data
    )
    if data:
        return pd.to_datetime(data[0]["finished_at"]).strftime("%d/%m/%Y %H:%M")
    return "—"


# ── Construcción de tabla comparativa ────────────────────────────────────────

def build_pivot(catalog: pd.DataFrame, listings: pd.DataFrame, aca: pd.DataFrame, equiv: pd.DataFrame) -> pd.DataFrame:
    if listings.empty or catalog.empty:
        return pd.DataFrame()

    # Precio mínimo más reciente por modelo × fuente
    latest = (
        listings
        .sort_values("scraped_at", ascending=False)
        .groupby(["catalog_model_id", "source"])
        .agg(price=("price", "min"), url=("url", "first"))
        .reset_index()
    )

    pivot = latest.pivot(index="catalog_model_id", columns="source", values="price")
    pivot.columns = [SOURCE_LABELS.get(c, c) for c in pivot.columns]
    pivot = pivot.reset_index().rename(columns={"catalog_model_id": "id"})

    df = catalog.merge(pivot, on="id", how="left")

    # Precio ACA
    if not aca.empty:
        df = df.merge(
            aca[["catalog_model_id", "price_member", "price_non_member"]]
              .rename(columns={"catalog_model_id": "id", "price_member": "ACA Socio"}),
            on="id",
            how="left",
        )
    else:
        df["ACA Socio"] = None
        df["price_non_member"] = None

    # Mínimo de mercado
    src_display = [SOURCE_LABELS[s] for s in SOURCES if SOURCE_LABELS[s] in df.columns]
    df["Mkt Mín"] = df[src_display].min(axis=1)

    # Delta ACA
    df["Δ ACA %"] = (
        (df["ACA Socio"] - df["Mkt Mín"]) / df["Mkt Mín"] * 100
    ).where(df["ACA Socio"].notna() & df["Mkt Mín"].notna())

    # Equivalente
    cat_code = catalog.set_index("id")["model_code"].to_dict()
    equiv_map = {}
    equiv_id_map = {}
    for _, row in equiv.iterrows():
        equiv_map[row["model_id"]]            = cat_code.get(row["equivalent_model_id"], "")
        equiv_map[row["equivalent_model_id"]] = cat_code.get(row["model_id"], "")
        equiv_id_map[row["model_id"]]            = row["equivalent_model_id"]
        equiv_id_map[row["equivalent_model_id"]] = row["model_id"]
    df["Equivalente"] = df["id"].map(equiv_map).fillna("—")

    # Ventas ACA — unidades del modelo propio o del equivalente Willard
    def _sales(row_id):
        direct = SALES_UNITS.get(row_id, 0)
        if direct:
            return direct
        equiv_id = equiv_id_map.get(row_id, "")
        return SALES_UNITS.get(equiv_id, 0)

    df["Ventas"] = df["id"].apply(_sales)

    return df


# ── Planilla de precios ACA (dialog) ─────────────────────────────────────────

@st.dialog("Precios ACA — Planilla completa", width="large")
def aca_price_dialog(catalog: pd.DataFrame, aca: pd.DataFrame, equiv: pd.DataFrame):
    st.caption("Editá los precios directamente en la tabla y hacé clic en Guardar cambios.")

    auto_cat = catalog[catalog["category"] == "auto"].copy()

    # Equivalente legible
    cat_code = catalog.set_index("id")["model_code"].to_dict()
    equiv_map = {}
    for _, row in equiv.iterrows():
        equiv_map[row["model_id"]]            = cat_code.get(row["equivalent_model_id"], "—")
        equiv_map[row["equivalent_model_id"]] = cat_code.get(row["model_id"], "—")

    auto_cat["Equivalente"] = auto_cat["id"].map(equiv_map).fillna("—")

    # Merge precios actuales
    if not aca.empty:
        auto_cat = auto_cat.merge(
            aca[["catalog_model_id", "price_member", "price_non_member"]]
              .rename(columns={"catalog_model_id": "id"}),
            on="id", how="left",
        )
    else:
        auto_cat["price_member"]     = None
        auto_cat["price_non_member"] = None

    # Tabla editable — solo columnas relevantes
    display = auto_cat[[
        "brand", "model_code", "capacity_ah", "cca", "type", "Equivalente",
        "price_member", "price_non_member",
    ]].rename(columns={
        "brand":             "Marca",
        "model_code":        "Modelo",
        "capacity_ah":       "Ah",
        "cca":               "CCA",
        "type":              "Tipo",
        "price_member":      "Precio Socio $",
        "price_non_member":  "Precio No Socio $",
    }).sort_values(["Marca", "Ah"]).reset_index(drop=True)

    display["Tipo"] = display["Tipo"].map({"standard": "Estándar", "agm": "AGM", "efb": "EFB"})

    edited = st.data_editor(
        display,
        use_container_width=True,
        height=480,
        hide_index=True,
        column_config={
            "Marca":            st.column_config.TextColumn(disabled=True, width="small"),
            "Modelo":           st.column_config.TextColumn(disabled=True, width="small"),
            "Ah":               st.column_config.NumberColumn(disabled=True, width="small", format="%.0f Ah"),
            "CCA":              st.column_config.NumberColumn(disabled=True, width="small", format="%d A"),
            "Tipo":             st.column_config.TextColumn(disabled=True, width="small"),
            "Equivalente":      st.column_config.TextColumn(disabled=True, width="small"),
            "Precio Socio $":   st.column_config.NumberColumn(
                min_value=0, step=1000, format="$ %d", width="medium",
                help="Precio de venta al socio ACA"
            ),
            "Precio No Socio $": st.column_config.NumberColumn(
                min_value=0, step=1000, format="$ %d", width="medium",
                help="Próximamente — dejá vacío si no aplica"
            ),
        },
    )

    col_save, col_cancel = st.columns([1, 3])
    with col_save:
        if st.button("Guardar cambios", type="primary", use_container_width=True):
            sb  = get_supabase()
            now = datetime.now(timezone.utc).isoformat()
            # Reconstruir el id de catálogo para cada fila
            id_map = auto_cat.set_index(
                auto_cat["Marca"].values if "Marca" in auto_cat.columns
                else auto_cat["brand"].values
            )
            # Usar el dataframe original para mapear modelo → id
            model_id_map = dict(zip(
                auto_cat["brand"] + "|" + auto_cat["model_code"],
                auto_cat["id"] if "id" in auto_cat.columns else []
            ))
            # Reconstruir desde catalog
            cat_id_map = dict(zip(
                catalog["brand"] + "|" + catalog["model_code"],
                catalog["id"]
            ))

            upserts = []
            for _, row in edited.iterrows():
                key = f"{row['Marca']}|{row['Modelo']}"
                cid = cat_id_map.get(key)
                if not cid:
                    continue
                price_m  = row.get("Precio Socio $")
                price_nm = row.get("Precio No Socio $")
                if pd.notna(price_m) and price_m > 0:
                    upserts.append({
                        "catalog_model_id": cid,
                        "price_member":     float(price_m),
                        "price_non_member": float(price_nm) if pd.notna(price_nm) and price_nm > 0 else None,
                        "updated_at":       now,
                    })

            if upserts:
                sb.table("aca_prices").upsert(upserts, on_conflict="catalog_model_id").execute()
                load_aca_prices.clear()
                st.success(f"{len(upserts)} precios guardados")
                st.rerun()
            else:
                st.warning("No hay precios para guardar. Completá al menos un Precio Socio.")


# ── KPIs ─────────────────────────────────────────────────────────────────────

def show_kpis(df: pd.DataFrame, last_run: str):
    c1, c2, c3, c4 = st.columns(4)

    with_aca = df.dropna(subset=["Δ ACA %"])

    avg_delta = with_aca["Δ ACA %"].mean() if not with_aca.empty else None
    risky     = int((with_aca["Δ ACA %"] > DELTA_WARNING).sum()) if not with_aca.empty else 0
    n_priced  = int(df["Mkt Mín"].notna().sum())
    n_total   = len(df)

    with c1:
        if avg_delta is not None:
            st.metric(
                "Posición ACA vs Mercado",
                f"{avg_delta:+.1f}%",
                delta=f"{'Competitivo' if avg_delta <= DELTA_COMPETITIVE else 'Revisar'}",
                delta_color="off",
                help="Diferencia promedio entre precio ACA y el mínimo del mercado",
            )
        else:
            st.metric("Posición ACA vs Mercado", "Sin precios ACA")

    with c2:
        st.metric(
            "Modelos con precio alto",
            str(risky),
            delta=f"Más de {DELTA_WARNING}% sobre mercado",
            delta_color="off",
            help=f"Modelos donde ACA supera en más de {DELTA_WARNING}% al precio mínimo del mercado",
        )

    with c3:
        st.metric(
            "Modelos con datos",
            f"{n_priced} / {n_total}",
            help="Modelos con al menos un precio encontrado en el mercado",
        )

    with c4:
        st.metric("Última actualización", last_run)


# ── Tabla principal ───────────────────────────────────────────────────────────

def show_top_sellers(df: pd.DataFrame):
    top = (
        df[df["Ventas"] > 0]
        .sort_values("Ventas", ascending=False)
        .head(5)
    )
    if top.empty:
        return

    st.subheader("Modelos más vendidos — Ej. 2025/2026")
    cols = st.columns(len(top))
    medals = ["1°", "2°", "3°", "4°", "5°"]
    for i, (_, row) in enumerate(top.iterrows()):
        with cols[i]:
            pct = row["Ventas"] / top["Ventas"].iloc[0] * 100
            bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            delta_txt = delta_emoji(row.get("Δ ACA %")) if pd.notna(row.get("Δ ACA %")) else "—"
            st.markdown(f"""
<div style="background:white;border-radius:12px;padding:1rem 1.2rem;
            box-shadow:0 2px 12px rgba(0,0,0,0.08);border-left:5px solid #DA2F37;
            font-family:sans-serif;">
  <div style="font-size:0.7rem;font-weight:800;color:#DA2F37;letter-spacing:0.12em;">
    {medals[i]}
  </div>
  <div style="font-size:1.1rem;font-weight:800;color:#1A1A1A;margin:4px 0 2px;">
    {row["brand"]} {row["model_code"]}
  </div>
  <div style="font-size:0.78rem;color:#6B7280;">{int(row["capacity_ah"] or 0)} Ah · {row.get("Equivalente","—")}</div>
  <div style="font-size:1.4rem;font-weight:900;color:#1A1A1A;margin:6px 0 2px;">
    {int(row["Ventas"]):,} u
  </div>
  <div style="font-size:0.7rem;color:#DA2F37;letter-spacing:0.04em;font-family:monospace;">{bar}</div>
  <div style="font-size:0.75rem;color:#6B7280;margin-top:4px;">ACA vs mkt: {delta_txt}</div>
</div>
""", unsafe_allow_html=True)


def show_table(df: pd.DataFrame):
    st.subheader("Comparativo de precios por modelo y canal")

    src_cols   = [SOURCE_LABELS[s] for s in SOURCES if SOURCE_LABELS[s] in df.columns]
    show_cols  = (
        ["Ventas", "brand", "model_code", "capacity_ah", "cca", "type", "Equivalente"]
        + src_cols
        + ["ACA Socio", "Mkt Mín", "Δ ACA %"]
    )
    show_cols  = [c for c in show_cols if c in df.columns]

    # Ordenar: primero por ventas desc, luego por marca/Ah
    display = (
        df[show_cols].copy()
        .sort_values(["Ventas", "brand", "capacity_ah"], ascending=[False, True, True])
        .rename(columns={
            "brand":       "Marca",
            "model_code":  "Modelo",
            "capacity_ah": "Ah",
            "cca":         "CCA",
            "type":        "Tipo",
        })
    )

    # Ranking visual en columna Ventas (solo si tiene ventas)
    def fmt_ventas(v):
        return f"{int(v):,}" if v and v > 0 else "—"
    display["Ventas"] = display["Ventas"].apply(fmt_ventas)

    # Formatear moneda
    for col in src_cols + ["ACA Socio", "Mkt Mín"]:
        if col in display.columns:
            display[col] = display[col].apply(fmt_ars)

    # Formatear delta
    if "Δ ACA %" in display.columns:
        display["Δ ACA %"] = display["Δ ACA %"].apply(delta_emoji)

    # Tipo como etiqueta legible
    if "Tipo" in display.columns:
        display["Tipo"] = display["Tipo"].map({"standard": "Estándar", "agm": "AGM", "efb": "EFB"}).fillna("—")

    st.dataframe(display, use_container_width=True, height=520, hide_index=True)

    st.caption(
        "ACA ≤5% sobre mercado: Competitivo  ·  5–15%: Revisar  ·  >15%: Alto  ·  — Sin datos  ·  Ventas: unidades ej. 2025/2026"
    )


# ── Detalle por canal ─────────────────────────────────────────────────────────

def show_channel_detail(listings: pd.DataFrame, catalog: pd.DataFrame):
    with st.expander("Ver todas las ofertas activas por modelo", expanded=False):
        auto_ids = catalog[catalog["category"] == "auto"]["id"].tolist()
        df       = listings[listings["catalog_model_id"].isin(auto_ids)].copy()

        if df.empty:
            st.info("Sin datos de listings.")
            return

        # Label por modelo
        cat_label = (catalog["brand"] + " " + catalog["model_code"]).to_dict()
        cat_label = dict(zip(catalog["id"], catalog["brand"] + " " + catalog["model_code"]))
        df["Modelo"] = df["catalog_model_id"].map(cat_label)

        # Más reciente por model+source+precio
        df["Fecha"]  = df["scraped_at"].dt.date
        df["Fuente"] = df["source"].map(SOURCE_LABELS)
        df["Precio"] = df["price"].apply(fmt_ars)
        df["Cuotas"] = df.apply(
            lambda r: f"{int(r.installments_qty)}x sin interés"
            if pd.notna(r.installments_qty) and r.installments_qty > 1 and r.installment_rate == 0
            else ("—"),
            axis=1,
        )
        df["Envío gratis"] = df["free_shipping"].map({True: "Sí", False: "—", None: "—"})

        show = df[["Modelo", "Fuente", "Precio", "Cuotas", "Envío gratis", "Fecha"]].drop_duplicates()
        show = show.sort_values(["Modelo", "Fuente"])
        st.dataframe(show, use_container_width=True, height=400, hide_index=True)


# ── Evolución de precios ──────────────────────────────────────────────────────

def show_evolution(listings: pd.DataFrame, catalog: pd.DataFrame):
    st.subheader("Evolución de precios")

    auto     = catalog[catalog["category"] == "auto"].copy()
    auto["label"] = auto["brand"] + " " + auto["model_code"]
    with_data = auto[auto["id"].isin(listings["catalog_model_id"].unique())]

    if with_data.empty:
        st.info("No hay datos históricos suficientes.")
        return

    col_filter, col_src = st.columns([2, 2])

    with col_filter:
        selected_models = st.multiselect(
            "Modelos",
            options=with_data["label"].tolist(),
            default=with_data["label"].tolist()[:4],
        )

    with col_src:
        selected_sources = st.multiselect(
            "Fuentes",
            options=list(SOURCE_LABELS.values()),
            default=list(SOURCE_LABELS.values()),
        )

    if not selected_models or not selected_sources:
        return

    id_map        = dict(zip(with_data["label"], with_data["id"]))
    selected_ids  = [id_map[s] for s in selected_models]
    src_rev_map   = {v: k for k, v in SOURCE_LABELS.items()}
    selected_srcs = [src_rev_map[s] for s in selected_sources]

    filtered = listings[
        listings["catalog_model_id"].isin(selected_ids)
        & listings["source"].isin(selected_srcs)
    ].copy()

    filtered["date"]   = filtered["scraped_at"].dt.date
    filtered["Modelo"] = filtered["catalog_model_id"].map(dict(zip(with_data["id"], with_data["label"])))
    filtered["Fuente"] = filtered["source"].map(SOURCE_LABELS)
    filtered["Serie"]  = filtered["Modelo"] + " · " + filtered["Fuente"]

    daily = (
        filtered.groupby(["date", "Serie"])["price"]
        .min()
        .reset_index()
        .rename(columns={"price": "Precio", "date": "Fecha"})
    )

    if daily.empty:
        st.info("Sin datos para los filtros seleccionados.")
        return

    ACA_PALETTE = [
        "#DA2F37", "#F5C200", "#1A1A1A", "#E87000",
        "#007ACC", "#6B7280", "#2D6A4F", "#9B2226",
    ]

    fig = px.line(
        daily,
        x="Fecha",
        y="Precio",
        color="Serie",
        markers=True,
        template="plotly_white",
        labels={"Precio": "Precio mínimo ($ARS)"},
        color_discrete_sequence=ACA_PALETTE,
    )
    fig.update_layout(
        height=400,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font_size=11),
        margin=dict(l=0, r=0, t=40, b=0),
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
        font=dict(family="sans-serif", color="#1A1A1A"),
    )
    fig.update_traces(line_width=2.5, marker_size=7)
    fig.update_xaxes(gridcolor="#F0F0F0", linecolor="#E5E7EB")
    fig.update_yaxes(gridcolor="#F0F0F0", linecolor="#E5E7EB")
    st.plotly_chart(fig, use_container_width=True)


# ── Análisis Willard vs Moura ─────────────────────────────────────────────────

def show_brand_comparison(df: pd.DataFrame):
    st.subheader("Willard vs Moura — diferencia de precio por par equivalente")

    pairs = df[df["Equivalente"] != "—"].copy()
    if pairs.empty:
        st.info("No hay suficientes datos de equivalencias con precio.")
        return

    src_cols = [SOURCE_LABELS[s] for s in SOURCES if SOURCE_LABELS[s] in df.columns]

    willard = pairs[pairs["brand"].isin(["Willard", "Unibat"])].copy()
    moura   = pairs[pairs["brand"] == "Moura"].copy()

    if willard.empty or moura.empty:
        st.info("Se necesitan datos de ambas marcas para comparar.")
        return

    rows = []
    for _, w in willard.iterrows():
        m_row = moura[moura["model_code"] == w["Equivalente"]]
        if m_row.empty:
            continue
        m = m_row.iloc[0]

        for src in src_cols:
            wp = w.get(src)
            mp = m.get(src)
            if pd.notna(wp) and pd.notna(mp) and wp > 0:
                rows.append({
                    "Par": f"{w['model_code']} / {m['model_code']}",
                    "Fuente": src,
                    "Ah": w["capacity_ah"],
                    "Willard ($)": wp,
                    "Moura ($)": mp,
                    "Dif. %": (mp - wp) / wp * 100,
                })

    if not rows:
        st.info("No hay suficientes precios coincidentes entre pares.")
        return

    cmp_df = pd.DataFrame(rows).sort_values(["Ah", "Fuente"])

    ACA_PALETTE = ["#DA2F37", "#F5C200", "#1A1A1A", "#E87000", "#007ACC", "#6B7280"]

    fig = px.bar(
        cmp_df,
        x="Par",
        y="Dif. %",
        color="Fuente",
        barmode="group",
        template="plotly_white",
        labels={"Dif. %": "Diferencia Moura vs Willard (%)", "Par": "Par equivalente"},
        title="% de diferencia de precio (negativo = Moura más barata)",
        color_discrete_sequence=ACA_PALETTE,
    )
    fig.add_hline(y=0, line_dash="dot", line_color="#DA2F37", line_width=1.5)
    fig.update_layout(
        height=380,
        margin=dict(l=0, r=0, t=40, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="sans-serif", color="#1A1A1A"),
    )
    fig.update_xaxes(gridcolor="#F0F0F0")
    fig.update_yaxes(gridcolor="#F0F0F0")
    st.plotly_chart(fig, use_container_width=True)

    # Tabla resumen
    summary = (
        cmp_df.groupby("Par")
        .agg(Ah=("Ah", "first"), Dif_prom=("Dif. %", "mean"))
        .reset_index()
        .rename(columns={"Dif_prom": "Dif. promedio %"})
        .sort_values("Ah")
    )
    summary["Dif. promedio %"] = summary["Dif. promedio %"].apply(lambda x: f"{x:+.1f}%")
    st.dataframe(summary, hide_index=True, use_container_width=True)


# ── Scraper desde la web ──────────────────────────────────────────────────────

@st.dialog("Correr scraper", width="large")
def run_scraper_dialog():
    st.caption("Scrapea todos los canales y sincroniza con Supabase. Tarda ~30 segundos.")

    if not st.button("Iniciar", type="primary"):
        return

    import sys, asyncio
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))

    from database import init_db, save_run, finish_run, insert_listings
    from matcher import classify_listings
    from supabase_sync import run_sync
    from config import DB_PATH
    import tempfile

    # Usar DB temporal en la nube, DB local si existe
    db_path = DB_PATH if Path(DB_PATH).exists() else tempfile.mktemp(suffix=".db")
    conn = init_db(db_path)

    results = {}
    started_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    status = st.status("Scrapeando...", expanded=True)

    # ── MercadoLibre ─────────────────────────────────────────────────────────
    with status:
        st.write("MercadoLibre...")
    from scraper import mercadolibre
    run_id = save_run(conn, "mercadolibre")
    try:
        ml_listings = asyncio.run(mercadolibre.run_all_searches())
        classify_listings(ml_listings)
        n = insert_listings(conn, run_id, ml_listings)
        finish_run(conn, run_id, "success", n)
        results["MercadoLibre"] = (n, None)
    except Exception as e:
        finish_run(conn, run_id, "error", 0, str(e))
        results["MercadoLibre"] = (0, str(e))

    # ── Scrapers secundarios ──────────────────────────────────────────────────
    from scraper.html_scrapers import (
        scrape_bateriasdeautos, scrape_easy, scrape_fravega, scrape_norauto
    )
    secondary = [
        ("bateriasdeautos", "Baterías de Autos", scrape_bateriasdeautos),
        ("fravega",         "Fravega",           scrape_fravega),
        ("norauto",         "Norauto",           scrape_norauto),
        ("easy",            "Easy",              scrape_easy),
    ]
    for source_key, label, fn in secondary:
        with status:
            st.write(f"{label}...")
        run_id = save_run(conn, source_key)
        try:
            listings = fn()
            classify_listings(listings)
            n = insert_listings(conn, run_id, listings)
            finish_run(conn, run_id, "success", n)
            results[label] = (n, None)
        except Exception as e:
            finish_run(conn, run_id, "error", 0, str(e))
            results[label] = (0, str(e))

    # ── Sync Supabase ─────────────────────────────────────────────────────────
    with status:
        st.write("Sincronizando con Supabase...")
    run_sync(conn, since=started_at.isoformat())
    conn.close()

    status.update(label="Listo", state="complete", expanded=False)

    # Resumen
    total = sum(n for n, _ in results.values())
    st.success(f"{total} registros nuevos guardados")
    for label, (n, err) in results.items():
        if err:
            st.error(f"{label}: error — {err[:80]}")
        else:
            st.write(f"{label}: {n} nuevos")

    # Refrescar caché del dashboard
    load_listings.clear()
    load_last_run.clear()
    st.rerun()


# ── App principal ─────────────────────────────────────────────────────────────

def main():
    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        logo_html = f'<img src="data:image/png;base64,{LOGO_B64}" width="130" style="display:block;margin:0 auto;">' if LOGO_B64 else '<div style="font-size:1.6rem;font-weight:900;color:#DA2F37;">ACA</div>'
        st.markdown(f"""
        <div style="text-align:center; padding: 1rem 0 0.6rem;">
            {logo_html}
            <div style="margin-top:8px;">
                <span style="font-size:0.72rem; color:#DA2F37; font-weight:900; letter-spacing:0.22em; font-family:'Arial Narrow','Arial',sans-serif; text-transform:uppercase;">BATERIABOT</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")

        st.subheader("Filtros")
        brand_filter = st.multiselect(
            "Marca", ["Willard", "Unibat", "Moura"], default=["Willard", "Moura"]
        )
        type_filter = st.multiselect(
            "Tipo",
            ["standard", "agm", "efb"],
            default=["standard", "agm"],
            format_func=lambda x: {"standard": "Estándar", "agm": "AGM", "efb": "EFB"}.get(x, x),
        )
        ah_range = st.slider("Capacidad (Ah)", 30, 200, (30, 130), step=5)

    # ── Carga de datos ────────────────────────────────────────────────────────
    catalog  = load_catalog()
    equiv    = load_equivalences()
    listings = load_listings()
    aca      = load_aca_prices()
    last_run = load_last_run()

    # ── Botones sidebar ───────────────────────────────────────────────────────
    st.sidebar.markdown("---")
    if st.sidebar.button("Cargar precios ACA", use_container_width=True, type="primary"):
        aca_price_dialog(catalog, aca, equiv)
    if st.sidebar.button("Correr scraper ahora", use_container_width=True):
        run_scraper_dialog()

    # ── Filtrar catálogo ──────────────────────────────────────────────────────
    filtered_cat = catalog[
        catalog["brand"].isin(brand_filter)
        & catalog["type"].isin(type_filter)
        & catalog["capacity_ah"].between(ah_range[0], ah_range[1])
    ]

    df = build_pivot(filtered_cat, listings, aca, equiv)

    # ── Header ────────────────────────────────────────────────────────────────
    logo_header = f'<img src="data:image/png;base64,{LOGO_B64}" height="56" style="flex-shrink:0;filter:brightness(0) invert(1);">' if LOGO_B64 else ''
    st.markdown(f"""
    <div class="aca-header">
        {logo_header}
        <div>
            <div style="font-size:0.7rem;font-weight:700;letter-spacing:0.2em;color:rgba(255,255,255,0.75);text-transform:uppercase;">Automóvil Club Argentino</div>
            <h1 style="margin:2px 0 0;">Comparativo de Baterías</h1>
            <div class="subtitle">Monitoreo semanal · Willard · Moura · Mercado</div>
        </div>
        <div class="aca-badge">INTERNO</div>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.warning("Sin datos para los filtros seleccionados.")
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    show_kpis(df, last_run)
    st.divider()

    # ── Top vendidos ──────────────────────────────────────────────────────────
    show_top_sellers(df)
    st.divider()

    # ── Tabla comparativa ─────────────────────────────────────────────────────
    show_table(df)
    show_channel_detail(listings, filtered_cat)
    st.divider()

    # ── Evolución histórica ───────────────────────────────────────────────────
    show_evolution(listings, filtered_cat)
    st.divider()

    # ── Willard vs Moura ──────────────────────────────────────────────────────
    show_brand_comparison(df)


if __name__ == "__main__":
    main()
