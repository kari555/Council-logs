"""
Council Raid Dashboard — Streamlit app.
Reads from local JSON cache built by fetch.py.

Run:
    streamlit run app.py
"""

from __future__ import annotations

import json
import hashlib
import hmac
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from insights import build_playground_insights

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Council Raid Dashboard",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
for _k, _v in [
    ("selected_player", None),
    ("open_dialog", False),
    ("perf_chart_nonce", 0),
    ("theme", "gold"),
    ("current_page", "walki"),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Themes — matches design_mockup.html exactly
# ---------------------------------------------------------------------------
THEMES: dict[str, dict[str, str]] = {
    "gold": {
        "bg": "#0d0f14", "bg2": "#161920", "bg3": "#1e2130",
        "border": "#2e3347",
        "gold": "#c89b3c", "gold_light": "#f0c060", "gold_dim": "#7a5e22",
        "text": "#d4cbb8", "text_dim": "#7a8099",
        "red": "#e74c3c", "green": "#2ecc71",
        "bg_asset": "council.png",
        "bg_opacity": "0.22",
        "bg_position": "center center",
        "bg_size": "cover",
        "bg_overlay_opacity": "0.34",
    },
    "alliance": {
        "bg": "#07111f", "bg2": "#0d1b2f", "bg3": "#142844",
        "border": "#28466f",
        "gold": "#d6b25e", "gold_light": "#f2d27a", "gold_dim": "#7f6534",
        "text": "#dbe7f5", "text_dim": "#7f96b5",
        "red": "#d45f68", "green": "#65c7ff",
        "bg_asset": "ally.png",
        "bg_fallback": "assets/bg-alliance.svg",
        "bg_opacity": "0.58",
        "bg_position": "calc(50% + 145px) center",
        "bg_size": "auto min(116vh, 1040px)",
        "bg_overlay_opacity": "0.07",
    },
    "horde": {
        "bg": "#120708", "bg2": "#1b0d0f", "bg3": "#271316",
        "border": "#4a2025",
        "gold": "#c7a15a", "gold_light": "#e0bd72", "gold_dim": "#76512c",
        "text": "#eadfd4", "text_dim": "#9b7c76",
        "red": "#d94343", "green": "#69b86f",
        "bg_asset": "horde.png",
        "bg_fallback": "assets/bg-horde.svg",
        "bg_opacity": "0.30",
        "bg_position": "calc(50% + 145px) center",
        "bg_size": "auto min(96vh, 900px)",
        "bg_overlay_opacity": "0.10",
    },
}

def c() -> dict[str, str]:
    return THEMES["gold"]


def sync_query_params() -> None:
    st.query_params["page"] = st.session_state.current_page


def _asset_data_uri(path: str) -> str:
    if not path:
        return "none"
    asset_path = Path(path)
    if not asset_path.exists():
        return "none"
    suffix = asset_path.suffix.lower()
    if suffix == ".svg":
        svg = asset_path.read_text(encoding="utf-8")
        return f'url("data:image/svg+xml,{quote(svg)}")'
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        import base64

        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }[suffix]
        data = base64.b64encode(asset_path.read_bytes()).decode("ascii")
        return f'url("data:{mime};base64,{data}")'
    return "none"


def _theme_background_uri(clr: dict[str, str]) -> str:
    primary = _asset_data_uri(clr.get("bg_asset", ""))
    if primary != "none":
        return primary
    return _asset_data_uri(clr.get("bg_fallback", ""))


def plot_style() -> dict:
    clr = c()
    return dict(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=clr["text"],
    )


# ---------------------------------------------------------------------------
# CSS injection — uses current theme colors
# ---------------------------------------------------------------------------
def inject_css() -> None:
    clr = c()
    faction_bg = _theme_background_uri(clr)
    page = st.session_state.get("current_page", "walki")
    bg_position = clr.get("bg_position", "right 2vw center")
    if page != "walki" and st.session_state.get("theme") in {"alliance", "horde"}:
        bg_position = "center center"
    bg_opacity = clr.get("bg_opacity", "0")
    if page in {"walki", "gracze", "parsy"}:
        bg_opacity = {"gold": "0.10", "alliance": "0.12", "horde": "0.12"}.get(st.session_state.theme, bg_opacity)
    elif page == "attendance":
        bg_opacity = {"gold": "0.14", "alliance": "0.16", "horde": "0.16"}.get(st.session_state.theme, bg_opacity)
    st.markdown(f"""
<style>
/* ── CSS Variables ─────────────────────────────────────────────────────── */
:root {{
  --bg:         {clr["bg"]};
  --bg2:        {clr["bg2"]};
  --bg3:        {clr["bg3"]};
  --border:     {clr["border"]};
  --gold:       {clr["gold"]};
  --gold-light: {clr["gold_light"]};
  --gold-dim:   {clr["gold_dim"]};
  --text:       {clr["text"]};
  --text-dim:   {clr["text_dim"]};
  --red:        {clr["red"]};
  --green:      {clr["green"]};
  --radius:     6px;
}}

/* ── Global ────────────────────────────────────────────────────────────── */
html, body, [data-testid="stApp"] {{
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-size: 15px;
}}
[data-testid="stAppViewContainer"] {{
    position: relative;
    background: linear-gradient(180deg, var(--bg) 0%, color-mix(in srgb, var(--bg2) 46%, var(--bg)) 100%) !important;
}}
[data-testid="stAppViewContainer"]::before {{
    content: "";
    position: fixed;
    inset: 0;
    background-image: {faction_bg};
    background-repeat: no-repeat;
    background-position: {bg_position};
    background-size: {clr.get("bg_size", "min(82vw, 1120px)")};
    opacity: {bg_opacity};
    pointer-events: none;
    z-index: 0;
}}
[data-testid="stAppViewContainer"]::after {{
    content: "";
    position: fixed;
    inset: 0;
    background: linear-gradient(90deg, var(--bg) 0%, transparent 38%, transparent 74%, var(--bg) 118%);
    opacity: {clr.get("bg_overlay_opacity", "0.16")};
    pointer-events: none;
    z-index: 0;
}}
[data-testid="stAppViewContainer"] > section,
[data-testid="stSidebar"] {{
    position: relative;
    z-index: 1;
}}
[data-testid="stHeader"] {{ display: none !important; }}
[data-testid="stToolbar"] {{ display: none !important; }}
[data-testid="stDecoration"] {{ display: none !important; }}
[data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
}}
:root {{ --header-height: 0rem !important; }}
[data-testid="stAppViewContainer"] > section {{ padding-top: 0 !important; }}
section[data-testid="stMain"] {{ padding-top: 0 !important; margin-top: 0 !important; }}
.main {{ padding-top: 0 !important; }}
.main .block-container {{
    padding-top: 0 !important;
    padding-bottom: 2rem;
    max-width: none;
}}

/* ── Sidebar ───────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: var(--bg2) !important;
    border-right: 1px solid var(--border) !important;
}}
[data-testid="stSidebar"] hr {{
    border-color: var(--border) !important;
    margin: 0.5rem 0;
}}
[data-testid="stSidebar"] p {{
    color: var(--text-dim) !important;
    font-size: 11px !important;
    text-transform: none;
    letter-spacing: 0;
    font-weight: 500;
}}
[data-testid="stSidebar"] h1 {{
    color: var(--text) !important;
    text-shadow: none;
    font-size: 1rem !important;
    letter-spacing: 0;
}}

/* ── Selectbox ─────────────────────────────────────────────────────────── */
[data-baseweb="select"] > div:first-child {{
    background-color: var(--bg3) !important;
    border-color: var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    font-size: 14px !important;
    min-height: 42px !important;
    display: flex !important;
    align-items: center !important;
}}
[data-baseweb="select"] > div:first-child > div {{
    display: flex !important;
    align-items: center !important;
}}
[data-baseweb="select"] [role="button"],
[data-baseweb="select"] span,
[data-baseweb="select"] input {{
    line-height: 1.2 !important;
}}
[data-testid="stTextInput"] input {{
    min-height: 42px !important;
    line-height: 42px !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}}
[data-baseweb="select"] > div:first-child:focus-within {{
    border-color: var(--gold-dim) !important;
}}
[data-baseweb="popover"] {{
    background: var(--bg3) !important;
    border: 1px solid var(--border) !important;
}}
[role="option"] {{
    color: var(--text) !important;
    font-size: 14px !important;
}}
[role="option"]:hover {{
    background: var(--bg2) !important;
}}

/* ── Tabs ──────────────────────────────────────────────────────────────── */
[data-baseweb="tab-list"] {{
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 4px !important;
}}
[data-baseweb="tab"] {{
    color: var(--text-dim) !important;
    background: transparent !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 5px 5px 0 0 !important;
    padding: 12px 20px !important;
    font-size: 1.06rem !important;
    font-weight: 600;
    transition: color 0.15s, background-color 0.15s, border-color 0.15s;
    white-space: nowrap;
}}
[data-baseweb="tab"]:hover {{
    color: var(--text) !important;
    background: color-mix(in srgb, var(--bg3) 42%, transparent) !important;
}}
[aria-selected="true"] {{
    color: var(--text) !important;
    border-bottom: 2px solid var(--gold) !important;
    background: color-mix(in srgb, var(--bg3) 68%, transparent) !important;
    font-weight: 700 !important;
}}

/* ── Metric cards ──────────────────────────────────────────────────────── */
[data-testid="metric-container"] {{
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 10px 14px !important;
}}
[data-testid="stMetricValue"] {{
    color: var(--gold) !important;
    font-size: 1.2rem !important;
    font-weight: 700 !important;
}}
[data-testid="stMetricLabel"] {{
    color: var(--text-dim) !important;
    font-size: 0.82rem !important;
    text-transform: none;
    letter-spacing: 0;
}}

/* ── Multiselect ───────────────────────────────────────────────────────── */
[data-baseweb="tag"] {{
    background: var(--bg3) !important;
    border: 1px solid var(--gold-dim) !important;
    color: var(--text) !important;
}}

/* ── Divider ───────────────────────────────────────────────────────────── */
hr {{ border-color: var(--border) !important; }}

/* ── Dataframe ─────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
}}

/* ── Dialog ────────────────────────────────────────────────────────────── */
[data-testid="stModal"] > div,
div[role="dialog"] {{
    background: var(--bg2) !important;
    border: 1px solid var(--gold-dim) !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.35) !important;
}}

/* ── Alert ─────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {{
    background: var(--bg2) !important;
    border-color: var(--border) !important;
    border-radius: var(--radius) !important;
}}

/* ── Caption ───────────────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] p,
.stCaption {{
    color: var(--gold-dim) !important;
    font-size: 0.82rem !important;
    font-weight: 500;
    letter-spacing: 0;
    text-transform: none;
}}

/* ── KPI topbar (custom HTML elements) ────────────────────────────────── */
.topbar-boss {{
    font-size: 20px;
    font-weight: 700;
    color: var(--text);
    text-shadow: none;
    letter-spacing: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
    padding-bottom: 0;
}}
.result-kill {{
    background: color-mix(in srgb, var(--green) 16%, var(--bg2));
    color: var(--green);
    border: 1px solid color-mix(in srgb, var(--green) 42%, var(--border));
    padding: 8px 12px;
    border-radius: 5px;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0;
}}
.result-wipe {{
    background: color-mix(in srgb, var(--red) 16%, var(--bg2));
    color: var(--red);
    border: 1px solid color-mix(in srgb, var(--red) 42%, var(--border));
    padding: 8px 12px;
    border-radius: 5px;
    font-size: 14px;
    font-weight: 700;
}}
.kpi.result-card {{
    background: color-mix(in srgb, var(--red) 12%, var(--bg2));
    border-color: color-mix(in srgb, var(--red) 38%, var(--border));
}}
.kpi.result-card.kill {{
    background: color-mix(in srgb, var(--green) 12%, var(--bg2));
    border-color: color-mix(in srgb, var(--green) 38%, var(--border));
}}
.kpi.result-card .kpi-value {{
    color: var(--red);
}}
.kpi.result-card.kill .kpi-value {{
    color: var(--green);
}}
.kpi-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: stretch;
    margin-bottom: 10px;
}}
.kpi-row.primary {{
    margin-bottom: 8px;
}}
.kpi-row.details {{
    gap: 6px;
    margin-bottom: 12px;
}}
.kpi {{
    display: flex; flex-direction: column;
    padding: 10px 12px;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg2) 76%, transparent);
    border-radius: 5px;
    min-width: fit-content;
    max-width: 260px;
    flex: 0 0 auto;
}}
.kpi-row.primary .kpi {{
    min-height: 68px;
}}
.kpi-row.details .kpi {{
    padding: 8px 10px;
    background: color-mix(in srgb, var(--bg2) 58%, transparent);
}}
.kpi-row.details .kpi-label {{
    font-size: 11px;
}}
.kpi-row.details .kpi-value {{
    font-size: 16px;
    font-weight: 700;
}}
.kpi-label {{
    font-size: 12px;
    text-transform: none;
    letter-spacing: 0;
    color: var(--text-dim);
    margin-bottom: 5px;
    font-weight: 600;
    white-space: nowrap;
}}
.kpi-value {{
    font-size: 21px;
    font-weight: 750;
    color: var(--text);
    font-variant-numeric: tabular-nums;
    line-height: 1.15;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.kpi-wide {{
    max-width: none;
}}
.kpi-ilvl-low {{
    border-color: color-mix(in srgb, var(--red) 34%, var(--border));
    background: color-mix(in srgb, var(--red) 8%, var(--bg2));
}}
.kpi-ilvl-high {{
    border-color: color-mix(in srgb, var(--green) 34%, var(--border));
    background: color-mix(in srgb, var(--green) 8%, var(--bg2));
}}
.kpi-value.gold  {{ color: var(--gold); }}
.kpi-value.red   {{ color: var(--red); }}
.kpi-value.green {{ color: var(--green); }}
.kpi-value.dim   {{ font-size: 18px; color: var(--text); }}
.kpi-ilvl-low .kpi-value {{ color: var(--red); }}
.kpi-ilvl-high .kpi-value {{ color: var(--green); }}
@media (max-width: 1100px) {{
    .kpi {{ flex: 1 1 140px; }}
    .kpi-wide {{ min-width: 0; }}
}}

.click-hint {{
    font-size: 13px;
    color: var(--text-dim);
    padding: 2px 0 8px;
    opacity: 0.85;
}}

/* scrollbar */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: var(--bg2); }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--gold-dim); }}


/* ── Pull radio (sidebar list) ───────────────────────────────────────── */
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {{
    gap: 2px;
    flex-direction: column;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] label {{
    padding: 5px 8px !important;
    border-radius: var(--radius) !important;
    border: 1px solid transparent !important;
    cursor: pointer;
    transition: background 0.12s;
    margin: 0 !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{
    background: {clr["bg3"]} !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {{
    background: {clr["bg3"]} !important;
    border-color: {clr["gold_dim"]} !important;
    color: {clr["gold"]} !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {{
    font-size: 11px !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    color: inherit !important;
    font-weight: inherit !important;
}}

/* ── Main pull selector ───────────────────────────────────────────────── */
section[data-testid="stMain"] [data-testid="stRadio"] [role="radiogroup"] {{
    gap: 6px;
    align-items: stretch;
    flex-wrap: wrap;
}}
section[data-testid="stMain"] [data-testid="stRadio"] label {{
    background: color-mix(in srgb, var(--bg2) 72%, transparent);
    border: 1px solid var(--border);
    border-radius: 5px;
    padding: 8px 11px !important;
    margin: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
section[data-testid="stMain"] [data-testid="stRadio"] label:has(input:checked) {{
    border-color: var(--gold-dim);
    background: color-mix(in srgb, var(--bg3) 82%, transparent);
}}
section[data-testid="stMain"] [data-testid="stRadio"] label > div:first-child {{
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}}
section[data-testid="stMain"] [data-testid="stRadio"] label > div:last-child {{
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
}}
section[data-testid="stMain"] [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {{
    font-size: 14px !important;
    color: var(--text) !important;
    line-height: 1.2;
    text-align: center !important;
    margin: 0 !important;
}}
.pull-nav-row {{
    display: grid;
    grid-template-columns: minmax(110px, 0.6fr) minmax(260px, 2fr) minmax(110px, 0.6fr);
    gap: 8px;
    align-items: end;
    margin-bottom: 12px;
}}
@media (max-width: 760px) {{
    .pull-nav-row {{ grid-template-columns: 1fr; }}
}}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Timeline event colours / symbols
# ---------------------------------------------------------------------------
EVENT_COLORS = {
    "Fight Start":          "#2ecc71",
    "Fight End":            "#7f8c8d",
    "Death":                "#e74c3c",
    "Combat Res":           "#f1c40f",
    "Combat Pot":           "#9b59b6",
    "Health Pot":           "#e91e8c",
    "Healthstone":          "#27ae60",
    "Mana Pot":             "#3498db",
    "Defensive (Personal)": "#e67e22",
    "Defensive (External)": "#1abc9c",
}
EVENT_SYMBOLS = {
    "Fight Start":          "triangle-right",
    "Fight End":            "triangle-left",
    "Death":                "x",
    "Combat Res":           "star",
    "Combat Pot":           "diamond",
    "Health Pot":           "circle",
    "Healthstone":          "circle-dot",
    "Mana Pot":             "diamond-wide",
    "Defensive (Personal)": "triangle-up",
    "Defensive (External)": "star-triangle-up",
}

CLASS_COLORS = {
    "DeathKnight":  "#C41E3A",
    "DemonHunter":  "#A330C9",
    "Druid":        "#FF7C0A",
    "Evoker":       "#33937F",
    "Hunter":       "#AAD372",
    "Mage":         "#3FC7EB",
    "Monk":         "#00FF98",
    "Paladin":      "#F48CBA",
    "Priest":       "#FFFFFF",
    "Rogue":        "#FFF468",
    "Shaman":       "#0070DD",
    "Warlock":      "#8788EE",
    "Warrior":      "#C69B3A",
}

DAMAGE_PALETTE = [
    "#e74c3c", "#e67e22", "#f1c40f", "#9b59b6", "#3498db",
    "#1abc9c", "#e91e8c", "#ff7675", "#fdcb6e", "#74b9ff",
    "#a29bfe", "#55efc4", "#fd79a8", "#ffeaa7", "#636e72",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
CACHE_DIR = Path("cache")


def _file_mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0


@st.cache_data
def _load_json_cached(path_str: str, mtime: float):
    path = Path(path_str)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_index() -> list:
    p = CACHE_DIR / "reports_index.json"
    return _load_json_cached(str(p), _file_mtime(p)) or []


def load_fight(report_code: str, fight_id: int) -> dict | None:
    p = CACHE_DIR / f"fight_{report_code}_{fight_id}.json"
    return _load_json_cached(str(p), _file_mtime(p))


def load_parses_index() -> pd.DataFrame:
    p = CACHE_DIR / "parses_index.json"
    rows = _load_json_cached(str(p), _file_mtime(p))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def load_attendance() -> pd.DataFrame:
    p = CACHE_DIR / "attendance.json"
    rows = _load_json_cached(str(p), _file_mtime(p))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _safe_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _date_filtered(df: pd.DataFrame, mode: str, date_col: str = "Date") -> pd.DataFrame:
    if df.empty or date_col not in df.columns:
        return df
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    max_date = out[date_col].dropna().max()
    if pd.isna(max_date):
        return out
    if mode == "Ostatnia noc":
        return out[out[date_col].dt.strftime("%Y-%m-%d") == max_date.strftime("%Y-%m-%d")]
    if mode == "Ostatnie 30 dni":
        return out[out[date_col] >= max_date - pd.Timedelta(days=30)]
    return out


def _fight_cache_signature() -> tuple:
    index_path = CACHE_DIR / "reports_index.json"
    fight_mtimes = tuple(
        (path.name, path.stat().st_mtime)
        for path in sorted(CACHE_DIR.glob("fight_*.json"))
    )
    return (_file_mtime(index_path), fight_mtimes)


def load_player_fight_rows() -> pd.DataFrame:
    return _load_player_fight_rows_cached(_fight_cache_signature())


@st.cache_data
def _load_player_fight_rows_cached(cache_signature: tuple) -> pd.DataFrame:
    rows = []
    for report in load_index():
        report_code = report.get("report_code")
        for fight in report.get("fights", []):
            fight_data = load_fight(report_code, fight.get("fight_id"))
            if not fight_data:
                continue
            meta = fight_data.get("meta", {})
            df_perf = pd.DataFrame(fight_data.get("performance", []))
            if df_perf.empty or "Player" not in df_perf.columns:
                continue

            df_dead = pd.DataFrame(fight_data.get("deaths", []))
            df_def = pd.DataFrame(fight_data.get("defensives", []))
            df_cons = pd.DataFrame(fight_data.get("consumables", []))
            df_dt = pd.DataFrame(fight_data.get("damage_taken", []))

            _safe_numeric(df_perf, ["Per Second", "Total", "Active %"])
            _safe_numeric(df_def, ["Count"])
            _safe_numeric(df_dt, ["Amount"])

            deaths = df_dead.groupby("Player").size().to_dict() if not df_dead.empty else {}
            defensives = (
                df_def.groupby("Player")["Count"].sum().to_dict()
                if not df_def.empty and "Count" in df_def.columns else {}
            )
            damage_taken = (
                df_dt.groupby("Player")["Amount"].sum().to_dict()
                if not df_dt.empty and "Amount" in df_dt.columns else {}
            )

            consumables = {}
            if not df_cons.empty:
                skip = {"Report", "Date", "Boss", "Pull #", "Result", "Boss HP %", "Duration (s)", "Player", "Class"}
                cons_cols = [col for col in df_cons.columns if col not in skip]
                if cons_cols:
                    _safe_numeric(df_cons, cons_cols)
                    consumables = df_cons.set_index("Player")[cons_cols].sum(axis=1).to_dict()

            for player, p_rows in df_perf.groupby("Player"):
                dps_row = p_rows[p_rows["Type"] == "DPS"]
                hps_row = p_rows[p_rows["Type"] == "HPS"]
                base = p_rows.iloc[0]
                dps = float(dps_row["Per Second"].iloc[0]) if not dps_row.empty and pd.notna(dps_row["Per Second"].iloc[0]) else 0.0
                hps = float(hps_row["Per Second"].iloc[0]) if not hps_row.empty and pd.notna(hps_row["Per Second"].iloc[0]) else 0.0
                active_src = dps_row if not dps_row.empty else hps_row
                active = (
                    float(active_src["Active %"].iloc[0])
                    if not active_src.empty and "Active %" in active_src.columns and pd.notna(active_src["Active %"].iloc[0])
                    else np.nan
                )
                rows.append({
                    "Report": meta.get("report", report_code),
                    "Date": meta.get("date", report.get("date")),
                    "Boss": meta.get("boss", fight.get("boss")),
                    "Pull #": meta.get("pull", fight.get("pull")),
                    "Fight ID": meta.get("fight_id", fight.get("fight_id")),
                    "Result": meta.get("result", fight.get("result")),
                    "Boss HP %": meta.get("boss_hp", fight.get("boss_hp")),
                    "Duration (s)": meta.get("duration_s", fight.get("duration_s")),
                    "Player": player,
                    "Class": base.get("Class", ""),
                    "Spec": base.get("Spec", ""),
                    "DPS": dps,
                    "HPS": hps,
                    "Active %": active,
                    "Deaths": int(deaths.get(player, 0)),
                    "Defensives": int(defensives.get(player, 0) or 0),
                    "Consumables": int(consumables.get(player, 0) or 0),
                    "Damage Taken": float(damage_taken.get(player, 0) or 0),
                    "Kill": bool(meta.get("kill", meta.get("result") == "Kill")),
                })

    df = pd.DataFrame(rows)
    if not df.empty:
        if "Class" in df.columns:
            df = df[df["Class"].isin(CLASS_COLORS)].copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        for col in ["DPS", "HPS", "Active %", "Deaths", "Defensives", "Consumables", "Damage Taken", "Pull #", "Duration (s)"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_player_profile_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fights = load_player_fight_rows()
    parses = load_parses_index()
    attendance = load_attendance()

    if not parses.empty:
        parses = parses.copy()
        for col in ("Parse %", "ilvl Parse %", "Item Level", "ilvl Bracket", "Median Parse %", "Amount"):
            if col in parses.columns:
                parses[col] = pd.to_numeric(parses[col], errors="coerce")
        if "Metric" not in parses.columns:
            role_series = parses["Role"] if "Role" in parses.columns else pd.Series("", index=parses.index)
            parses["Metric"] = np.where(role_series.eq("Healers"), "Healing", "Damage")
        parses["Date"] = pd.to_datetime(parses["Date"], errors="coerce")
        parses = parses[parses["Result"] == "Kill"].copy()

    if not attendance.empty:
        attendance = attendance.copy()
        attendance["Presence"] = pd.to_numeric(attendance["Presence"], errors="coerce").fillna(0)
        attendance["Present"] = (attendance["Presence"] > 0).astype(int)
        attendance["Night"] = attendance["Date"].astype(str).str[:10]
        attendance["Date"] = pd.to_datetime(attendance["Date"], errors="coerce")

    return fights, parses, attendance


def build_player_profile_data(player: str, date_mode: str, boss_filter: str, fight_filter: str) -> dict:
    fights, parses, attendance = load_player_profile_sources()
    fights_f = _date_filtered(fights, date_mode)
    parses_f = _date_filtered(parses, date_mode)
    attendance_f = _date_filtered(attendance, date_mode)

    if boss_filter != "Wszystkie":
        if not fights_f.empty and "Boss" in fights_f.columns:
            fights_f = fights_f[fights_f["Boss"] == boss_filter]
        if not parses_f.empty and "Boss" in parses_f.columns:
            parses_f = parses_f[parses_f["Boss"] == boss_filter]

    if fight_filter == "Kille" and not fights_f.empty:
        fights_f = fights_f[fights_f["Result"] == "Kill"]
    elif fight_filter == "Wipe’y" and not fights_f.empty:
        fights_f = fights_f[fights_f["Result"] != "Kill"]
        parses_f = parses_f.iloc[0:0].copy()

    p_fights = fights_f[fights_f["Player"] == player].copy() if not fights_f.empty else pd.DataFrame()
    p_parses = parses_f[parses_f["Player"] == player].copy() if not parses_f.empty else pd.DataFrame()
    p_att = attendance_f[attendance_f["Player"] == player].copy() if not attendance_f.empty else pd.DataFrame()

    role = ""
    metric = "DPS"
    if not p_parses.empty and "Role" in p_parses.columns:
        role_vals = p_parses["Role"].dropna().astype(str)
        role = role_vals.mode().iloc[0] if not role_vals.empty else ""
    if role == "Healers" or (not p_parses.empty and p_parses.get("Metric", pd.Series(dtype=str)).eq("Healing").any()):
        metric = "HPS"
    elif not p_fights.empty and p_fights["HPS"].mean() > p_fights["DPS"].mean():
        metric = "HPS"
    output_col = metric

    class_name = ""
    spec_name = ""
    for src in (p_parses, p_fights, p_att):
        if not src.empty:
            if not class_name and "Class" in src.columns:
                vals = src["Class"].dropna().astype(str)
                class_name = vals.mode().iloc[0] if not vals.empty else ""
            if not spec_name and "Spec" in src.columns:
                vals = src["Spec"].dropna().astype(str)
                spec_name = vals.mode().iloc[0] if not vals.empty else ""

    total_nights = attendance_f["Night"].nunique() if not attendance_f.empty and "Night" in attendance_f.columns else 0
    player_nights = (
        p_att.groupby("Night")["Present"].max().sum()
        if not p_att.empty and "Night" in p_att.columns else 0
    )
    attendance_pct = (player_nights / total_nights * 100) if total_nights else np.nan

    avg_parse = p_parses["Parse %"].mean() if not p_parses.empty and "Parse %" in p_parses.columns else np.nan
    best_parse = p_parses["Parse %"].max() if not p_parses.empty and "Parse %" in p_parses.columns else np.nan
    avg_output = p_fights[output_col].mean() if not p_fights.empty and output_col in p_fights.columns else np.nan
    deaths_per_pull = p_fights["Deaths"].mean() if not p_fights.empty else np.nan
    defensives_per_pull = p_fights["Defensives"].mean() if not p_fights.empty else np.nan
    consumables_per_pull = p_fights["Consumables"].mean() if not p_fights.empty else np.nan

    peers = pd.DataFrame()
    if not fights_f.empty:
        peer_src = fights_f.copy()
        if spec_name:
            peer_src = peer_src[peer_src["Spec"] == spec_name]
        elif role == "Healers":
            peer_src = peer_src[peer_src["HPS"] > peer_src["DPS"]]
        if not peer_src.empty:
            peers = peer_src.groupby(["Player", "Class", "Spec"]).agg(
                Pulls=("Player", "count"),
                Avg_Output=(output_col, "mean"),
                Death_Rate=("Deaths", "mean"),
                Avg_Active=("Active %", "mean"),
            ).reset_index()
            if not parses_f.empty and "Parse %" in parses_f.columns:
                parse_peers = parses_f.copy()
                if spec_name and "Spec" in parse_peers.columns:
                    parse_peers = parse_peers[parse_peers["Spec"] == spec_name]
                parse_peers = parse_peers.groupby("Player").agg(Avg_Parse=("Parse %", "mean")).reset_index()
                peers = peers.merge(parse_peers, on="Player", how="left")
            peers["Output Rank"] = peers["Avg_Output"].rank(ascending=False, method="min")
            peers["Parse Rank"] = peers["Avg_Parse"].rank(ascending=False, method="min") if "Avg_Parse" in peers.columns else np.nan
            sort_cols = [col for col in ["Avg_Parse", "Avg_Output"] if col in peers.columns]
            peers = peers.sort_values(sort_cols, ascending=[False] * len(sort_cols), na_position="last")

    boss_summary = pd.DataFrame()
    if not p_fights.empty:
        agg = {
            "Pulls": ("Player", "count"),
            "Kills": ("Kill", "sum"),
            "Avg Output": (output_col, "mean"),
            "Deaths": ("Deaths", "sum"),
            "Deaths / Pull": ("Deaths", "mean"),
            "Def / Pull": ("Defensives", "mean"),
            "Cons / Pull": ("Consumables", "mean"),
        }
        boss_summary = p_fights.groupby("Boss").agg(**agg).reset_index()
        if not p_parses.empty:
            parse_by_boss = p_parses.groupby("Boss").agg(
                **{"Avg Parse": ("Parse %", "mean"), "Best Parse": ("Parse %", "max")}
            ).reset_index()
            boss_summary = boss_summary.merge(parse_by_boss, on="Boss", how="left")
        boss_summary = boss_summary.sort_values("Avg Output", ascending=False)

    issues = []
    if not p_fights.empty:
        recent = p_fights.sort_values("Date", ascending=False).head(80)
        for _, row in recent.iterrows():
            reasons = []
            if row.get("Deaths", 0) > 0:
                reasons.append(f"{int(row['Deaths'])} death")
            if pd.notna(row.get("Active %")) and row.get("Active %") < 80:
                reasons.append(f"active {row['Active %']:.0f}%")
            if row.get("Consumables", 0) <= 0 and row.get("Result") == "Kill":
                reasons.append("brak consumables")
            if row.get("Damage Taken", 0) > 0:
                dmg = row.get("Damage Taken", 0)
                player_avg = recent["Damage Taken"].replace(0, np.nan).mean()
                if pd.notna(player_avg) and dmg > player_avg * 1.8:
                    reasons.append("wysoki damage taken")
            if reasons:
                issues.append({
                    "Date": row.get("Date"),
                    "Boss": row.get("Boss"),
                    "Pull": row.get("Pull #"),
                    "Result": row.get("Result"),
                    "Powód": ", ".join(reasons),
                    "Report": row.get("Report"),
                })
            if len(issues) >= 12:
                break

    return {
        "fights": fights_f,
        "parses": parses_f,
        "attendance": attendance_f,
        "player_fights": p_fights,
        "player_parses": p_parses,
        "player_attendance": p_att,
        "peers": peers,
        "boss_summary": boss_summary,
        "issues": pd.DataFrame(issues),
        "meta": {
            "player": player,
            "class": class_name,
            "spec": spec_name,
            "role": role,
            "metric": metric,
            "attendance_pct": attendance_pct,
            "player_nights": int(player_nights) if pd.notna(player_nights) else 0,
            "total_nights": int(total_nights) if total_nights else 0,
            "avg_parse": avg_parse,
            "best_parse": best_parse,
            "avg_output": avg_output,
            "deaths_per_pull": deaths_per_pull,
            "defensives_per_pull": defensives_per_pull,
            "consumables_per_pull": consumables_per_pull,
            "pulls": len(p_fights),
            "parse_rows": len(p_parses),
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def unique_dates(index: list) -> list[str]:
    """Return report dates in index order without duplicates."""
    return list(dict.fromkeys(e["date"] for e in index))


def reports_for_date(index: list, date: str) -> list:
    return [e for e in index if e["date"] == date]


def report_label(report: dict) -> str:
    title = report.get("title") or "Raid"
    code = report.get("report_code", "")
    fight_count = len(report.get("fights", []))
    return f"{title} | {code} | {fight_count} pulli"


def fmt_duration(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def pull_label(f: dict) -> str:
    dur = fmt_duration(f["duration_s"])
    if f["kill"]:
        return f"Pull #{f['pull']} - Kill ({dur})"
    hp = f["boss_hp"]
    hp_str = f"{hp:.1f}%" if hp is not None else "?"
    return f"Pull #{f['pull']} - Wipe {hp_str} ({dur})"


def compact_pull_label(f: dict) -> str:
    dur = fmt_duration(f["duration_s"])
    if f["kill"]:
        return f"#{f['pull']} Kill {dur}"
    hp = f["boss_hp"]
    hp_str = f"{hp:.1f}%" if hp is not None else "?"
    return f"#{f['pull']} Wipe {hp_str} {dur}"


def _build_spell_damage_series(
    df_damage: pd.DataFrame,
    bucket_seconds: int | None = None,
) -> pd.DataFrame:
    """Aggregate boss spell damage-taken events into a time series."""
    if df_damage.empty:
        return pd.DataFrame(columns=["Ability", "Time", "Damage", "Time Label"])

    work = df_damage.copy()
    work["Amount"] = pd.to_numeric(work["Amount"], errors="coerce").fillna(0)
    work["Event Time (s)"] = pd.to_numeric(work["Event Time (s)"], errors="coerce")
    work = work.dropna(subset=["Ability", "Event Time (s)"])
    if work.empty:
        return pd.DataFrame(columns=["Ability", "Time", "Damage", "Time Label"])

    if bucket_seconds:
        work["Time"] = (np.floor(work["Event Time (s)"] / bucket_seconds) * bucket_seconds).astype(float)
        grouped = (
            work.groupby(["Ability", "Time"], as_index=False)["Amount"]
            .sum()
            .rename(columns={"Amount": "Damage"})
        )
        grouped["Time Label"] = grouped["Time"].apply(lambda value: fmt_duration(int(value)))
    else:
        work["Time"] = work["Event Time (s)"].round(1)
        grouped = (
            work.groupby(["Ability", "Time"], as_index=False)["Amount"]
            .sum()
            .rename(columns={"Amount": "Damage"})
        )
        grouped["Time Label"] = grouped["Time"].apply(lambda value: fmt_duration(float(value)))

    return grouped.sort_values(["Ability", "Time"]).reset_index(drop=True)


def _render_spell_damage_timeline(
    df_damage: pd.DataFrame,
    meta: dict,
    bucket_seconds: int | None = None,
    chart_key_suffix: str = "",
) -> None:
    """Render spell-damage timeline using raw hit timestamps or fixed buckets."""
    series = _build_spell_damage_series(df_damage, bucket_seconds=bucket_seconds)
    if series.empty:
        st.info("Brak danych spell damage dla aktualnych filtrów.")
        return

    mode_label = "1s buckets" if bucket_seconds else "Raw events"
    fig = go.Figure()
    for idx, ability in enumerate(series["Ability"].dropna().unique().tolist()):
        cur = series[series["Ability"] == ability]
        trace_args = dict(
            x=cur["Time"],
            y=cur["Damage"],
            name=ability,
            line=dict(width=2.5, color=DAMAGE_PALETTE[idx % len(DAMAGE_PALETTE)]),
            hovertemplate=(
                f"<b>{ability}</b><br>"
                f"{mode_label}: %{{customdata}}<br>"
                "Damage: %{y:,.0f}<extra></extra>"
            ),
            customdata=cur["Time Label"],
        )
        if bucket_seconds:
            fig.add_trace(go.Scatter(mode="lines", **trace_args))
        else:
            fig.add_trace(go.Scatter(mode="lines+markers", marker=dict(size=6), **trace_args))

    fig.update_layout(
        height=440,
        margin=dict(l=10, r=10, t=20, b=30),
        xaxis=dict(
            title="Czas walki (s)",
            range=[-2, meta["duration_s"] + 5],
            gridcolor=c()["border"],
        ),
        yaxis=dict(
            title="Damage taken",
            tickformat=",.0f",
            gridcolor=c()["border"],
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            title_text="Boss spell",
        ),
        **plot_style(),
    )
    st.plotly_chart(fig, use_container_width=True, key=f"spell_damage_timeline_{chart_key_suffix}")


def _fmt_compact_number(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f}k"
    return f"{value:.0f}"


def render_topbar(fight_data: dict, deaths_count: int) -> None:
    meta = fight_data["meta"]
    boss = meta["boss"]
    pull = meta["pull"]
    dur = fmt_duration(meta["duration_s"])
    is_kill = meta.get("kill", meta["result"] == "Kill")
    boss_hp = meta.get("boss_hp")

    if is_kill:
        hp_val = "0.0%"
    else:
        hp_str = f"{boss_hp:.1f}%" if boss_hp is not None else "?"
        hp_val = hp_str if boss_hp is not None else "?"
    result_label = "KILL" if is_kill else f"WIPE {hp_val}"
    result_class = "result-card kill" if is_kill else "result-card"

    report_code = meta["report"]
    df_perf = pd.DataFrame(fight_data.get("performance", []))
    df_rank = pd.DataFrame(fight_data.get("rankings", []))
    df_def = pd.DataFrame(fight_data.get("defensives", []))
    df_cons = pd.DataFrame(fight_data.get("consumables", []))
    df_int = pd.DataFrame(fight_data.get("interrupts", []))
    df_disp = pd.DataFrame(fight_data.get("dispels", []))

    players = df_perf["Player"].nunique() if not df_perf.empty and "Player" in df_perf.columns else 0
    dps_total = df_perf.loc[df_perf["Type"].eq("DPS"), "Per Second"].sum() if not df_perf.empty and "Type" in df_perf.columns else 0
    hps_total = df_perf.loc[df_perf["Type"].eq("HPS"), "Per Second"].sum() if not df_perf.empty and "Type" in df_perf.columns else 0
    active_avg = (
        df_perf.loc[df_perf["Type"].eq("DPS"), "Active %"].mean()
        if not df_perf.empty and {"Type", "Active %"}.issubset(df_perf.columns)
        else np.nan
    )
    ilvl_by_player = pd.Series(dtype=float)
    for ilvl_col in ("Item Level", "ilvl Bracket"):
        if not df_rank.empty and {"Player", ilvl_col}.issubset(df_rank.columns):
            rank_tmp = df_rank[["Player", ilvl_col]].copy()
            rank_tmp[ilvl_col] = pd.to_numeric(rank_tmp[ilvl_col], errors="coerce")
            rank_tmp = rank_tmp[rank_tmp[ilvl_col] > 0]
            if not rank_tmp.empty:
                ilvl_by_player = rank_tmp.groupby("Player")[ilvl_col].mean()
                break
    avg_ilvl = ilvl_by_player.mean() if not ilvl_by_player.empty else np.nan
    if ilvl_by_player.empty and not df_perf.empty and "Player" in df_perf.columns:
        try:
            parses_idx = load_parses_index()
        except Exception:
            parses_idx = pd.DataFrame()
        if not parses_idx.empty:
            fight_players = set(df_perf["Player"].dropna().astype(str))
            ilvl_col = "ilvl Bracket" if "ilvl Bracket" in parses_idx.columns else "Item Level" if "Item Level" in parses_idx.columns else None
            if ilvl_col and "Player" in parses_idx.columns:
                fallback = parses_idx[parses_idx["Player"].astype(str).isin(fight_players)].copy()
                if "Date" in fallback.columns:
                    fallback["Date"] = pd.to_datetime(fallback["Date"], errors="coerce")
                    fallback = fallback.sort_values("Date")
                fallback[ilvl_col] = pd.to_numeric(fallback[ilvl_col], errors="coerce")
                fallback = fallback[fallback[ilvl_col] > 0]
                if not fallback.empty:
                    ilvl_by_player = fallback.groupby("Player")[ilvl_col].last()
                    avg_ilvl = ilvl_by_player.mean()
    if not ilvl_by_player.empty:
        min_player = str(ilvl_by_player.idxmin())
        max_player = str(ilvl_by_player.idxmax())
        min_ilvl = ilvl_by_player.min()
        max_ilvl = ilvl_by_player.max()
        lowest_ilvl = f"{min_player} - {min_ilvl:.0f}"
        highest_ilvl = f"{max_player} - {max_ilvl:.0f}"
    else:
        lowest_ilvl = "—"
        highest_ilvl = "—"
    defensives_total = pd.to_numeric(df_def.get("Count", pd.Series(dtype=float)), errors="coerce").sum()
    interrupts_total = pd.to_numeric(df_int.get("Count", pd.Series(dtype=float)), errors="coerce").sum()
    dispels_total = pd.to_numeric(df_disp.get("Count", pd.Series(dtype=float)), errors="coerce").sum()
    consumables_total = 0
    if not df_cons.empty:
        skip_cols = {"Report", "Date", "Boss", "Pull #", "Result", "Boss HP %", "Duration (s)", "Player", "Class"}
        cons_cols = [col for col in df_cons.columns if col not in skip_cols]
        if cons_cols:
            consumables_total = pd.to_numeric(df_cons[cons_cols].stack(), errors="coerce").sum()

    metrics = [
        ("Pull", f"#{pull} · {result_label}", "", result_class),
        ("Czas", dur, "", "kpi-main"),
        ("Gracze", str(players or "—"), "", "kpi-main"),
        ("Śr. ilvl", f"{avg_ilvl:.0f}" if not pd.isna(avg_ilvl) else "—", "", "kpi-main"),
        ("Lowest ilvl", lowest_ilvl, "red", "kpi-ilvl-low"),
        ("Highest ilvl", highest_ilvl, "green", "kpi-ilvl-high"),
        ("Zgony", str(deaths_count), "red" if deaths_count else "", "kpi-main"),
        ("DPS", _fmt_compact_number(dps_total), "", ""),
        ("HPS", _fmt_compact_number(hps_total), "", ""),
        ("Active", f"{active_avg:.0f}%" if not pd.isna(active_avg) else "—", "", ""),
        ("Defensives / Consumables", f"{int(defensives_total)} / {int(consumables_total)}", "", ""),
        ("Interrupts / Dispels", f"{int(interrupts_total)} / {int(dispels_total)}", "", ""),
        ("Raport", report_code, "dim", "kpi-wide"),
    ]
    metric_html = "".join(
        f'<div class="kpi {width_class}"><div class="kpi-label">{label}</div><div class="kpi-value {klass}" title="{value}">{value}</div></div>'
        for label, value, klass, width_class in metrics
    )

    st.markdown(f"""
<div class="topbar-boss">
    <span>{boss}</span>
</div>
<div class="kpi-row">{metric_html}</div>
<div class="click-hint">Kliknij gracza na wykresie, żeby otworzyć jego profil.</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Player profile content
# ---------------------------------------------------------------------------
def render_player_profile(fight_data: dict, player_name: str):
    meta    = fight_data["meta"]
    df_perf = pd.DataFrame(fight_data.get("performance", []))
    df_dead = pd.DataFrame(fight_data.get("deaths", []))
    df_cons = pd.DataFrame(fight_data.get("consumables", []))
    df_def  = pd.DataFrame(fight_data.get("defensives", []))
    df_tl   = pd.DataFrame(fight_data.get("timeline", []))
    df_dt   = pd.DataFrame(fight_data.get("damage_taken", []))

    p_perf = df_perf[df_perf["Player"] == player_name] if not df_perf.empty else pd.DataFrame()
    p_dead = df_dead[df_dead["Player"] == player_name] if not df_dead.empty else pd.DataFrame()
    p_cons = df_cons[df_cons["Player"] == player_name] if not df_cons.empty else pd.DataFrame()
    p_def  = df_def[df_def["Player"] == player_name]  if not df_def.empty  else pd.DataFrame()
    p_dt   = df_dt[df_dt["Player"] == player_name]    if not df_dt.empty   else pd.DataFrame()

    if not df_tl.empty:
        p_tl = df_tl[
            (df_tl["Player"] == player_name) |
            (df_tl["Event Type"].isin(["Fight Start", "Fight End"]))
        ]
    else:
        p_tl = pd.DataFrame()

    cls   = p_perf["Class"].values[0] if not p_perf.empty and "Class" in p_perf.columns else "—"
    spec  = p_perf["Spec"].values[0]  if not p_perf.empty and "Spec"  in p_perf.columns else "—"
    color = CLASS_COLORS.get(cls, "#aaaaaa")
    st.markdown(
        f"<span style='color:{color}; font-weight:700; font-size:1rem;'>{cls}</span>"
        f"<span style='color:{c()['text_dim']}; font-size:0.9rem;'> — {spec}</span>",
        unsafe_allow_html=True,
    )

    dps_row = p_perf[p_perf["Type"] == "DPS"] if not p_perf.empty else pd.DataFrame()
    hps_row = p_perf[p_perf["Type"] == "HPS"] if not p_perf.empty else pd.DataFrame()
    dps    = dps_row["Per Second"].values[0]  if not dps_row.empty else 0
    hps    = hps_row["Per Second"].values[0]  if not hps_row.empty else 0
    active = dps_row["Active %"].values[0]    if not dps_row.empty and "Active %" in dps_row.columns else 0
    deaths = len(p_dead)
    skip   = {"Report","Date","Boss","Pull #","Result","Boss HP %","Duration (s)","Player","Class"}
    cat_cols   = [c_ for c_ in df_cons.columns if c_ not in skip] if not df_cons.empty else []
    total_cons = int(p_cons[cat_cols].sum().sum()) if not p_cons.empty and cat_cols else 0
    total_def  = int(p_def["Count"].sum()) if not p_def.empty and "Count" in p_def.columns else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("DPS",         f"{dps:,.0f}")
    c2.metric("HPS",         f"{hps:,.0f}")
    c3.metric("Active %",    f"{active:.1f}%")
    c4.metric("Zgony",       deaths)
    c5.metric("Consumables", total_cons)
    c6.metric("Def CDs",     total_def)

    has_events = not p_tl.empty and "Event Time (s)" in p_tl.columns
    has_damage = not p_dt.empty and "Event Time (s)" in p_dt.columns
    xrange = [-2, meta["duration_s"] + 5]

    if has_events or has_damage:
        st.caption("Timeline")

        if has_events and has_damage:
            fig = make_subplots(
                rows=2, cols=1,
                row_heights=[0.25, 0.75],
                shared_xaxes=True,
                vertical_spacing=0.06,
                subplot_titles=["Eventy (defensives / poty / zgony)",
                                "Przyjęte obrażenia (avoidable)"],
            )
            ev_row, dt_row, h = 1, 2, 500
        elif has_events:
            fig = go.Figure()
            ev_row, dt_row, h = None, None, 180
        else:
            fig = go.Figure()
            ev_row, dt_row, h = None, None, 300

        if has_events:
            for etype in p_tl["Event Type"].unique():
                df_ev  = p_tl[p_tl["Event Type"] == etype]
                color  = EVENT_COLORS.get(etype, "#cccccc")
                symbol = EVENT_SYMBOLS.get(etype, "circle")
                size   = 14 if etype == "Death" else 10
                cd     = [
                    f"<b>{r['Event Type']}</b><br>t = {r['Event Time (s)']:.1f}s"
                    + (f"<br>{r.get('Detail','')}" if r.get("Detail") else "")
                    for _, r in df_ev.iterrows()
                ]
                trace = go.Scatter(
                    x=df_ev["Event Time (s)"].tolist(), y=[0] * len(df_ev),
                    mode="markers", name=etype,
                    marker=dict(color=color, symbol=symbol, size=size,
                                line=dict(color="rgba(0,0,0,0.4)", width=1)),
                    hovertemplate="%{customdata}<extra></extra>",
                    customdata=cd, legendgroup="events",
                )
                if ev_row:
                    fig.add_trace(trace, row=ev_row, col=1)
                else:
                    fig.add_trace(trace)

        if has_damage:
            abilities = (
                p_dt.groupby("Ability")["Amount"].sum()
                .sort_values(ascending=False).index.tolist()
            )
            ab_color = {ab: DAMAGE_PALETTE[i % len(DAMAGE_PALETTE)]
                        for i, ab in enumerate(abilities)}
            for ab in abilities:
                df_ab = p_dt[p_dt["Ability"] == ab].sort_values("Event Time (s)")
                trace = go.Scatter(
                    x=df_ab["Event Time (s)"].tolist(),
                    y=(df_ab["Amount"] / 1000).tolist(),
                    mode="markers", name=ab,
                    marker=dict(color=ab_color[ab], size=9, opacity=0.85,
                                line=dict(color="rgba(0,0,0,0.3)", width=1)),
                    hovertemplate=(
                        f"<b>{ab}</b><br>"
                        "t = %{x:.1f}s<br>%{customdata:,.0f} dmg<extra></extra>"
                    ),
                    customdata=df_ab["Amount"].tolist(),
                    legendgroup="damage",
                )
                if dt_row:
                    fig.add_trace(trace, row=dt_row, col=1)
                else:
                    fig.add_trace(trace)

        fig.add_vline(x=meta["duration_s"], line_dash="dash", line_color="#555",
                      annotation_text="End", annotation_position="top right",
                      row="all", col="all")

        grid_color = c()["border"]
        base = dict(
            height=h, margin=dict(l=0, r=10, t=45, b=30),
            **plot_style(),
            legend=dict(orientation="v", x=1.01, y=1, xanchor="left",
                        groupclick="toggleitem", bgcolor="rgba(0,0,0,0)"),
        )
        if has_events and has_damage:
            fig.update_layout(**base)
            fig.update_xaxes(range=xrange)
            fig.update_xaxes(title_text="Czas walki (s)", row=2, col=1)
            fig.update_yaxes(visible=False, row=1, col=1)
            fig.update_yaxes(title_text="Damage (k)", row=2, col=1,
                             gridcolor=grid_color, zerolinecolor=grid_color)
        elif has_events:
            fig.update_layout(**base,
                              xaxis=dict(title="Czas walki (s)", range=xrange),
                              yaxis=dict(visible=False))
        else:
            fig.update_layout(**base,
                              xaxis=dict(title="Czas walki (s)", range=xrange),
                              yaxis=dict(title="Damage (k)",
                                         gridcolor=grid_color, zerolinecolor=grid_color))
        st.plotly_chart(fig, use_container_width=True, key=f"tl_{player_name}_{meta['fight_id']}")

    col_d, col_c = st.columns(2)
    with col_d:
        st.caption("Defensives")
        if not p_def.empty:
            disp = [col for col in ["Ability", "Count"] if col in p_def.columns]
            st.dataframe(p_def[disp].sort_values("Count", ascending=False),
                         hide_index=True, use_container_width=True)
        else:
            st.info("Brak danych.")

    with col_c:
        st.caption("Consumables")
        if not p_cons.empty and cat_cols:
            st.dataframe(p_cons[cat_cols], hide_index=True, use_container_width=True)
        else:
            st.info("Brak danych.")

    if not p_dead.empty:
        st.caption("Zgony")
        disp = [col for col in ["Death Time", "Killing Blow"] if col in p_dead.columns]
        st.dataframe(p_dead[disp], hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Player profile dialog
# ---------------------------------------------------------------------------
@st.dialog("Profil gracza", width="large")
def player_profile_dialog(index: list, player_name: str):
    st.subheader(player_name)

    dates = unique_dates(index)
    dc1, dc2, dc3, dc4 = st.columns([2, 3, 2, 3])

    _d = st.session_state.get("dlg_date_sel",
                               st.session_state.get("dlg_date", dates[0]))
    _d_idx = dates.index(_d) if _d in dates else 0
    with dc1:
        dlg_date = st.selectbox("Noc", dates, index=_d_idx, key="dlg_date_sel")

    reports = reports_for_date(index, dlg_date)
    _r = st.session_state.get("dlg_report_sel",
                               st.session_state.get("dlg_report", reports[0]["report_code"]))
    report_codes = [r["report_code"] for r in reports]
    _r_idx = report_codes.index(_r) if _r in report_codes else 0
    with dc2:
        selected_report_code = st.selectbox(
            "📄 Raport",
            report_codes,
            index=_r_idx,
            format_func=lambda code: report_label(next(r for r in reports if r["report_code"] == code)),
            key="dlg_report_sel",
            disabled=len(reports) == 1,
        )

    night = next(e for e in reports if e["report_code"] == selected_report_code)
    boss_names = sorted(set(f["boss"] for f in night["fights"]))

    _b = st.session_state.get("dlg_boss_sel",
                               st.session_state.get("dlg_boss", boss_names[0]))
    _b_idx = boss_names.index(_b) if _b in boss_names else 0
    with dc3:
        dlg_boss = st.selectbox("Boss", boss_names, index=_b_idx, key="dlg_boss_sel")

    boss_fights = sorted(
        [f for f in night["fights"] if f["boss"] == dlg_boss],
        key=lambda f: f["pull"],
    )
    _p = min(st.session_state.get("dlg_pull_sel",
                                   st.session_state.get("dlg_pull_idx", 0)),
             len(boss_fights) - 1)
    with dc4:
        dlg_pull = st.selectbox("Pull", range(len(boss_fights)),
                                 format_func=lambda i: pull_label(boss_fights[i]),
                                 index=_p, key="dlg_pull_sel")

    st.divider()

    fight_data = load_fight(night["report_code"], boss_fights[dlg_pull]["fight_id"])
    if fight_data is None:
        st.error("Brak danych dla tego fightu w cache.")
        return

    render_player_profile(fight_data, player_name)


def _all_cache_frames_signature() -> tuple:
    return _fight_cache_signature()


def load_playground_frames() -> dict[str, pd.DataFrame]:
    return _load_playground_frames_cached(_all_cache_frames_signature())


@st.cache_data
def _load_playground_frames_cached(cache_signature: tuple) -> dict[str, pd.DataFrame]:
    buckets = {
        "fights": [],
        "performance": [],
        "targets": [],
        "deaths": [],
        "defensives": [],
        "consumables": [],
        "damage_taken": [],
        "interrupts": [],
        "dispels": [],
        "rankings": [],
        "boss_rankings": [],
        "defensive_events": [],
        "consumable_events": [],
        "enemy_casts": [],
        "player_details": [],
    }
    for report in load_index():
        report_code = report.get("report_code")
        for fight in report.get("fights", []):
            fight_data = load_fight(report_code, fight.get("fight_id"))
            if not fight_data:
                continue
            meta = fight_data.get("meta", {})
            base = {
                "Report": meta.get("report", report_code),
                "Date": meta.get("date", report.get("date")),
                "Boss": meta.get("boss", fight.get("boss")),
                "Pull #": meta.get("pull", fight.get("pull")),
                "Fight ID": meta.get("fight_id", fight.get("fight_id")),
                "Result": meta.get("result", fight.get("result")),
                "Kill": bool(meta.get("kill", meta.get("result") == "Kill")),
                "Duration (s)": meta.get("duration_s", fight.get("duration_s")),
                "Boss HP %": meta.get("boss_hp", fight.get("boss_hp")),
            }
            buckets["fights"].append(base)
            section_keys = {
                "targets": "target_damage",
            }
            for section in buckets:
                if section == "fights":
                    continue
                data_key = section_keys.get(section, section)
                for row in fight_data.get(data_key, []):
                    merged = {**base, **row}
                    if "Kill" not in merged:
                        merged["Kill"] = base["Kill"]
                    buckets[section].append(merged)

    frames = {name: pd.DataFrame(rows) for name, rows in buckets.items()}
    for df in frames.values():
        if df.empty:
            continue
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        if "Result" in df.columns and "Kill" not in df.columns:
            df["Kill"] = df["Result"].eq("Kill")
    numeric_cols = {
        "performance": ["Total", "Per Second", "Active %", "Duration (s)", "Pull #"],
        "targets": ["Damage", "Player Total", "% Player Damage", "Duration (s)", "Pull #"],
        "deaths": ["Death Time (s)", "Duration (s)", "Pull #"],
        "defensives": ["Count", "Duration (s)", "Pull #"],
        "consumables": ["Duration (s)", "Pull #"],
        "damage_taken": ["Amount", "Event Time (s)", "Duration (s)", "Pull #"],
        "interrupts": ["Count", "Duration (s)", "Pull #"],
        "dispels": ["Count", "Duration (s)", "Pull #"],
        "rankings": ["Parse %", "Median Parse %", "Amount", "Item Level", "ilvl Parse %", "ilvl Bracket"],
        "boss_rankings": ["Parse %", "Median Parse %", "Amount", "Item Level", "ilvl Parse %", "ilvl Bracket"],
        "defensive_events": ["Event Time (s)", "Duration (s)", "Pull #"],
        "consumable_events": ["Event Time (s)", "Duration (s)", "Pull #"],
        "enemy_casts": ["Event Time (s)", "Duration (s)", "Pull #"],
        "player_details": ["Item Level", "Duration (s)", "Pull #"],
        "fights": ["Duration (s)", "Pull #", "Boss HP %"],
    }
    for name, cols in numeric_cols.items():
        if name in frames and not frames[name].empty:
            _safe_numeric(frames[name], cols)
    return frames


def _filter_playground_frames(
    frames: dict[str, pd.DataFrame],
    date_mode: str,
    boss_filter: str,
    fight_filter: str,
    player_filter: str,
    pull_filter: int | None = None,
) -> dict[str, pd.DataFrame]:
    out = {}
    for name, df in frames.items():
        cur = _date_filtered(df, date_mode) if not df.empty else df.copy()
        if boss_filter != "Wszystkie" and not cur.empty and "Boss" in cur.columns:
            cur = cur[cur["Boss"] == boss_filter]
        if fight_filter == "Kille" and not cur.empty and "Kill" in cur.columns:
            cur = cur[cur["Kill"] == True]
        elif fight_filter == "Wipe’y" and not cur.empty and "Kill" in cur.columns:
            cur = cur[cur["Kill"] == False]
        if pull_filter is not None and not cur.empty and "Fight ID" in cur.columns:
            cur = cur[cur["Fight ID"] == pull_filter]
        if player_filter != "Wszyscy" and not cur.empty and "Player" in cur.columns:
            cur = cur[cur["Player"] == player_filter]
        out[name] = cur.copy()
    return out


def _playground_pull_options(
    fights_all: pd.DataFrame,
    date_mode: str,
    boss_filter: str,
    fight_filter: str,
) -> tuple[list[str], dict[str, int | None]]:
    if fights_all.empty:
        return ["Wszystkie"], {"Wszystkie": None}
    cur = _date_filtered(fights_all, date_mode)
    if boss_filter != "Wszystkie" and "Boss" in cur.columns:
        cur = cur[cur["Boss"] == boss_filter]
    if fight_filter == "Kille" and "Kill" in cur.columns:
        cur = cur[cur["Kill"] == True]
    elif fight_filter == "Wipe’y" and "Kill" in cur.columns:
        cur = cur[cur["Kill"] == False]
    if cur.empty:
        return ["Wszystkie"], {"Wszystkie": None}

    cur = cur.sort_values(["Date", "Boss", "Pull #", "Fight ID"], ascending=[False, True, True, True])
    labels = ["Wszystkie"]
    values = {"Wszystkie": None}
    for _, row in cur.iterrows():
        fight_id = row.get("Fight ID")
        if pd.isna(fight_id):
            continue
        label = (
            f"{row.get('Date').strftime('%Y-%m-%d') if hasattr(row.get('Date'), 'strftime') else row.get('Date')} · "
            f"{row.get('Boss')} · #{int(row.get('Pull #', 0))} · {row.get('Result')} · {row.get('Report')}"
        )
        labels.append(label)
        values[label] = int(fight_id)
    return labels, values


def _plot_bar(df: pd.DataFrame, x: str, y: str, title: str = "", color: str | None = None, height: int = 420):
    fig = go.Figure(go.Bar(
        x=df[x],
        y=df[y],
        orientation="h",
        marker_color=color or c()["gold"],
        hovertemplate="<b>%{y}</b><br>%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=10, t=26 if title else 10, b=30),
        title=dict(text=title, font_color=c()["text_dim"]) if title else None,
        xaxis=dict(gridcolor=c()["border"]),
        yaxis=dict(autorange="reversed"),
        **plot_style(),
    )
    return fig


# ---------------------------------------------------------------------------
# Page navigation
# ---------------------------------------------------------------------------
PAGES = [
    ("walki", "Fights"),
    ("attendance", "Attendance"),
    ("parsy", "Parses"),
    ("gracze", "Players"),
    ("playground", "Playground"),
    ("admin", "Admin"),
]


def render_nav_bar() -> None:
    clr = c()
    current = st.session_state.current_page

    items_html = ""
    for key, label in PAGES:
        active = ' class="nav-active"' if key == current else ""
        player_param = ""
        if key == "gracze" and current == "gracze" and st.query_params.get("player"):
            player_param = f'&player={quote(str(st.query_params.get("player")))}'
        items_html += f'<a href="?page={key}{player_param}" target="_self"{active}>{label}</a>'

    st.markdown(f"""
<style>
#prz-nav {{
    position: fixed !important;
    top: 0 !important; left: 0 !important; right: 0 !important;
    height: 46px !important;
    display: flex !important; align-items: stretch !important;
    background: color-mix(in srgb, {clr["bg2"]} 94%, #000 6%) !important;
    border-bottom: 1px solid {clr["border"]} !important;
    z-index: 999999 !important;
    font-family: ui-sans-serif, system-ui, sans-serif;
    box-sizing: border-box;
}}
#prz-nav .nav-logo {{
    display: flex; align-items: center;
    padding: 0 18px; border-right: 1px solid {clr["border"]};
    font-weight: 700; font-size: 15px;
    color: {clr["text"]}; white-space: nowrap; flex-shrink: 0;
}}
#prz-nav a {{
    display: flex; align-items: center; justify-content: center;
    padding: 0 20px; font-size: 15px; font-weight: 500;
    color: {clr["text_dim"]}; text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: color 0.15s, background-color 0.15s, border-color 0.15s;
    white-space: nowrap;
}}
#prz-nav a:hover {{ color: {clr["text"]}; background: color-mix(in srgb, {clr["bg3"]} 58%, transparent); }}
#prz-nav a.nav-active {{
    color: {clr["text"]} !important;
    border-bottom-color: {clr["gold"]} !important;
    background: color-mix(in srgb, {clr["bg3"]} 54%, transparent);
    font-weight: 650 !important;
}}
.main .block-container {{ padding-top: 58px !important; }}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 58px !important; }}
</style>
<div id="prz-nav">
    <div class="nav-logo">Council</div>
    {items_html}
</div>
""", unsafe_allow_html=True)


def _secret_value(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _secret_section(name: str):
    try:
        return st.secrets.get(name, {})
    except Exception:
        return {}


def auth_users() -> dict:
    auth = _secret_section("auth")
    users = auth.get("users", {}) if hasattr(auth, "get") else {}
    if users:
        return users

    legacy_password = _secret_value("ADMIN_PASSWORD")
    if legacy_password:
        return {
            "admin": {
                "password_hash": _sha256(legacy_password),
                "role": "admin",
            }
        }
    return {}


def verify_user(username: str, password: str) -> dict | None:
    user = auth_users().get(username)
    if not user:
        return None
    expected = str(user.get("password_hash", "")).lower().replace("sha256:", "")
    if expected and hmac.compare_digest(_sha256(password), expected):
        return {"username": username, "role": user.get("role", "viewer")}
    return None


def require_admin_login() -> dict | None:
    if st.session_state.get("auth_user"):
        return st.session_state.auth_user

    st.markdown('<div class="player-side-title">Admin login</div>', unsafe_allow_html=True)
    if not auth_users():
        st.info(
            "Brak skonfigurowanych kont. Dodaj `[auth.users.<login>]` w Streamlit Secrets "
            "albo tymczasowo ustaw `ADMIN_PASSWORD`."
        )
        return None

    with st.form("admin_login_form"):
        username = st.text_input("Login")
        password = st.text_input("Hasło", type="password")
        submitted = st.form_submit_button("Zaloguj")
    if submitted:
        user = verify_user(username.strip(), password)
        if user:
            st.session_state.auth_user = user
            st.rerun()
        st.error("Nieprawidłowy login albo hasło.")
    return None


def refresh_wcl_cache(reports: int = 20, force: bool = False,
                      with_playground_data: bool = False) -> None:
    from fetch import (
        build_config,
        fetch_attendance,
        fetch_report,
        pick_best_reports,
        update_index,
    )
    from wcl_client import WCLClient

    wcl = WCLClient()
    consumable_config, defensive_config = build_config()
    report_codes = pick_best_reports(wcl, limit=reports)
    for code in report_codes:
        report_raw = wcl.get_report_fights(code)
        report_info = {
            "code": code,
            "title": report_raw.get("title", ""),
            "startTime": report_raw["startTime"],
        }
        fights_meta = fetch_report(
            wcl, code, consumable_config, defensive_config, force=force,
            with_playground_data=with_playground_data,
        )
        update_index(code, report_info, fights_meta)
    fetch_attendance(wcl)


def render_admin_controls() -> None:
    user = require_admin_login()
    if not user:
        return
    if user.get("role") != "admin":
        st.warning("To konto nie ma uprawnień admina.")
        if st.button("Wyloguj", key="admin_logout_viewer"):
            st.session_state.pop("auth_user", None)
            st.rerun()
        return

    st.markdown(
        f'<div class="player-identity"><div><div class="player-name">Admin</div>'
        f'<div class="player-sub">Zalogowano jako {user["username"]}</div></div></div>',
        unsafe_allow_html=True,
    )
    col_a, col_b, col_c, col_d, col_e = st.columns([1, 1, 1.4, 1.6, 1])
    reports = col_a.number_input("Raporty", min_value=1, max_value=50, value=20, step=1)
    force = col_b.checkbox("Force", value=False)
    playground_data = col_c.checkbox("Playground data", value=False)
    if col_d.button("Odśwież dane z WCL", type="primary", use_container_width=True):
        with st.spinner("Pobieram dane z Warcraft Logs. To może potrwać kilka minut..."):
            try:
                refresh_wcl_cache(
                    reports=int(reports),
                    force=force,
                    with_playground_data=playground_data,
                )
                st.cache_data.clear()
                st.success("Dane odświeżone. Przeładowuję widok.")
                st.rerun()
            except Exception as exc:
                st.error(f"Nie udało się odświeżyć danych: {exc}")
    if col_e.button("Wyloguj", use_container_width=True):
        st.session_state.pop("auth_user", None)
        st.rerun()


# ---------------------------------------------------------------------------
# Sync URL query param → session state (enables <a href> nav links)
# ---------------------------------------------------------------------------
_valid_pages = {k for k, _ in PAGES}
_page_param = st.query_params.get("page", "walki")
if _page_param in _valid_pages and _page_param != st.session_state.current_page:
    st.session_state.current_page = _page_param
st.session_state.theme = "gold"
if st.query_params.get("theme") is not None:
    del st.query_params["theme"]
if st.session_state.current_page != "gracze" and st.query_params.get("player"):
    del st.query_params["player"]

# ---------------------------------------------------------------------------
# CSS injection (at render time, uses current theme)
# ---------------------------------------------------------------------------
inject_css()

# ---------------------------------------------------------------------------
# Nav bar + index load (both needed on every page)
# ---------------------------------------------------------------------------
render_nav_bar()

index = load_index()

if not index:
    st.markdown(f"<h1 style='color:{c()['gold']}'>Brak danych</h1>", unsafe_allow_html=True)
    st.info("Uruchom najpierw skrypt pobierający:\n\n```\npython fetch.py\n```")
    st.stop()

# ---------------------------------------------------------------------------
# Hide native sidebar; page controls live in the main layout
# ---------------------------------------------------------------------------
st.markdown("""<style>
[data-testid="stSidebar"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
.main .block-container { padding-left: 2rem !important; max-width: 100% !important; }
</style>""", unsafe_allow_html=True)

# ===========================================================================
# PAGE: walki
# ===========================================================================
if st.session_state.current_page == "walki":

    dates = unique_dates(index)
    st.markdown('<div class="player-side-title">Filtry</div>', unsafe_allow_html=True)
    f_date, f_report, f_boss = st.columns([1, 1.8, 1.4])
    with f_date:
        selected_date = st.selectbox("Noc raidowa", dates, key="walki_date")
    reports = reports_for_date(index, selected_date)
    if len(reports) > 1:
        with f_report:
            selected_report_code = st.selectbox(
                "Raport / grupa",
                [r["report_code"] for r in reports],
                format_func=lambda code: report_label(next(r for r in reports if r["report_code"] == code)),
                key=f"walki_report_{selected_date}",
            )
        night = next(e for e in reports if e["report_code"] == selected_report_code)
    else:
        night = reports[0]
        with f_report:
            st.selectbox(
                "Raport / grupa",
                [night["report_code"]],
                format_func=lambda code: report_label(night),
                disabled=True,
                key=f"walki_report_single_{selected_date}",
            )

    boss_names = sorted(set(f["boss"] for f in night["fights"]))
    with f_boss:
        selected_boss = st.selectbox("Boss", boss_names, key=f"walki_boss_{night['report_code']}")

    boss_fights = sorted(
        [f for f in night["fights"] if f["boss"] == selected_boss],
        key=lambda f: f["pull"],
    )
    pull_key = f"walki_pull_select_{night['report_code']}_{selected_boss}"
    if pull_key not in st.session_state or st.session_state[pull_key] >= len(boss_fights):
        st.session_state[pull_key] = 0

    prev_col, select_col, next_col = st.columns([0.7, 2.6, 0.7], vertical_alignment="bottom")
    with prev_col:
        if st.button("Previous", disabled=st.session_state[pull_key] <= 0, use_container_width=True, key=f"{pull_key}_prev"):
            st.session_state[pull_key] = max(0, st.session_state[pull_key] - 1)
            st.rerun()
    with select_col:
        selected_pull_idx = st.selectbox(
            "Pull",
            range(len(boss_fights)),
            format_func=lambda i: compact_pull_label(boss_fights[i]),
            key=pull_key,
        )
    with next_col:
        if st.button("Next", disabled=st.session_state[pull_key] >= len(boss_fights) - 1, use_container_width=True, key=f"{pull_key}_next"):
            st.session_state[pull_key] = min(len(boss_fights) - 1, st.session_state[pull_key] + 1)
            st.rerun()
    selected_fight_meta = boss_fights[selected_pull_idx]

    fight_data = load_fight(night["report_code"], selected_fight_meta["fight_id"])
    if fight_data is None:
        st.error(f"Brak danych dla tego fightu. Uruchom `python fetch.py --code {night['report_code']}`")
        st.stop()

    meta = fight_data["meta"]

    # ── Header ───────────────────────────────────────────────────────────
    deaths_count = len(fight_data.get("deaths", []))
    render_topbar(fight_data, deaths_count)

    # ── Tabs (Attendance i Parsy przeniesione na osobne strony) ───────────
    (tab_perf, tab_targets, tab_timeline, tab_deaths,
     tab_interrupts, tab_dispels, tab_consumables, tab_defensives) = st.tabs([
        "Performance", "Targets", "Timeline", "Deaths",
        "Interrupts", "Dispels", "Consumables", "Defensives",
    ])


    # ── Performance ──────────────────────────────────────────────────────
    with tab_perf:
        df_perf = pd.DataFrame(fight_data["performance"])
        if df_perf.empty:
            st.info("Brak danych.")
        else:
            col_dps, col_hps = st.columns(2)
            for col_ui, data_type, label in [
                (col_dps, "DPS", "DPS"),
                (col_hps, "HPS", "HPS"),
            ]:
                df = df_perf[df_perf["Type"] == data_type].copy()
                df = df.sort_values("Per Second", ascending=True)
                with col_ui:
                    st.subheader(label)
                    if df.empty:
                        st.info("Brak danych.")
                        continue
                    fig = go.Figure()
                    for _, row in df.iterrows():
                        bar_clr = CLASS_COLORS.get(row.get("Class", ""), "#aaaaaa")
                        fig.add_trace(go.Bar(
                            x=[row["Per Second"]], y=[row["Player"]],
                            orientation="h", name=row.get("Class", ""),
                            marker_color=bar_clr,
                            hovertemplate=(
                                f"<b>{row['Player']}</b>"
                                f" ({row.get('Class','')} {row.get('Spec','')})<br>"
                                f"{data_type}: <b>{row['Per Second']:,.0f}</b><br>"
                                f"Total: {row['Total']:,.0f}<br>"
                                f"Active: {row.get('Active %', 0):.1f}%"
                                "<extra></extra>"
                            ),
                            showlegend=False,
                        ))
                    fig.update_layout(
                        height=600,
                        margin=dict(l=0, r=20, t=10, b=10),
                        xaxis=dict(title=data_type, tickformat=",.0f",
                                   gridcolor=c()["border"]),
                        yaxis=dict(title=""),
                        bargap=0.2,
                        **plot_style(),
                    )
                    event = st.plotly_chart(
                        fig, use_container_width=True,
                        key=(
                            f"perf_{data_type}_{meta['report']}_{meta['fight_id']}_"
                            f"{st.session_state.perf_chart_nonce}"
                        ),
                        on_select="rerun",
                        selection_mode="points",
                    )
                    if event.selection.points:
                        clicked = event.selection.points[0].get("y")
                        if clicked:
                            st.session_state.selected_player = clicked
                            st.session_state.open_dialog = True
                            st.session_state.dlg_date     = selected_date
                            st.session_state.dlg_report   = night["report_code"]
                            st.session_state.dlg_boss     = selected_boss
                            st.session_state.dlg_pull_idx = selected_pull_idx
                            st.session_state.pop("dlg_date_sel", None)
                            st.session_state.pop("dlg_report_sel", None)
                            st.session_state.pop("dlg_boss_sel", None)
                            st.session_state.pop("dlg_pull_sel", None)
                            st.session_state.perf_chart_nonce += 1
                            st.rerun()
                    display_df = df.sort_values("Per Second", ascending=False)[
                        ["Player", "Class", "Spec", "Per Second", "Total", "Active %"]].copy()
                    display_df["Per Second"] = display_df["Per Second"].apply(lambda x: f"{x:,.0f}")
                    display_df["Total"]      = display_df["Total"].apply(lambda x: f"{x:,.0f}")
                    display_df["Active %"]   = display_df["Active %"].apply(lambda x: f"{x:.1f}%")
                    display_df.columns = ["Gracz", "Klasa", "Spec", data_type, "Total", "Active %"]
                    st.dataframe(display_df, hide_index=True, use_container_width=True)

    # ── Targets ──────────────────────────────────────────────────────────
    with tab_targets:
        df_targets = pd.DataFrame(fight_data.get("target_damage", []))
        if df_targets.empty:
            st.info("Brak target breakdown w cache. Odśwież dane z WCL, żeby zapisać podział damage po targetach.")
        else:
            df_targets = df_targets.copy()
            df_targets["Damage"] = pd.to_numeric(df_targets["Damage"], errors="coerce").fillna(0)
            df_targets["Player Total"] = pd.to_numeric(df_targets.get("Player Total", 0), errors="coerce").fillna(0)
            df_targets["% Player Damage"] = pd.to_numeric(
                df_targets.get("% Player Damage", 0), errors="coerce"
            ).fillna(0)
            targets = sorted(df_targets["Target"].dropna().unique())
            c_target, c_sort = st.columns([1.4, 1])
            with c_target:
                selected_target = st.selectbox("Target", ["All"] + targets, key=f"targets_target_{meta['report']}_{meta['fight_id']}")
            with c_sort:
                sort_options = ["Total damage"] + targets
                sort_mode = st.selectbox("Sort", sort_options, key=f"targets_sort_{meta['report']}_{meta['fight_id']}")

            df_view = df_targets.copy()
            if selected_target != "All":
                df_view = df_view[df_view["Target"] == selected_target]

            if df_view.empty:
                st.info("Brak danych dla wybranego targetu.")
            else:
                by_player = (
                    df_view.pivot_table(
                        index=["Player", "Class"],
                        columns="Target",
                        values="Damage",
                        aggfunc="sum",
                        fill_value=0,
                    )
                    .reset_index()
                    .rename_axis(None, axis=1)
                )
                target_cols = [target for target in targets if target in by_player.columns]
                if selected_target != "All":
                    target_cols = [selected_target] if selected_target in by_player.columns else []
                by_player["Total"] = by_player[target_cols].sum(axis=1) if target_cols else 0

                if sort_mode != "Total damage" and sort_mode in by_player.columns:
                    by_player = by_player.sort_values(sort_mode, ascending=True)
                else:
                    by_player = by_player.sort_values("Total", ascending=True)

                target_totals = df_view.groupby("Target")["Damage"].sum().sort_values(ascending=False)
                total_damage = target_totals.sum()
                top_target = target_totals.index[0] if not target_totals.empty else "—"
                top_share = target_totals.iloc[0] / total_damage * 100 if total_damage else 0
                metric_cols = st.columns(3)
                metric_cols[0].metric("Total damage", _fmt_compact_number(total_damage))
                metric_cols[1].metric("Targets", str(len(target_totals)))
                metric_cols[2].metric("Top target", f"{top_target} · {top_share:.1f}%" if total_damage else "—")

                fig = go.Figure()
                ordered_targets = [target for target in target_totals.index if target in target_cols]
                for idx, target in enumerate(ordered_targets):
                    target_type = df_view.loc[df_view["Target"].eq(target), "Target Type"].dropna()
                    color = c()["gold"] if not target_type.empty and target_type.iloc[0] == "Boss" else DAMAGE_PALETTE[idx % len(DAMAGE_PALETTE)]
                    fig.add_trace(go.Bar(
                        x=by_player[target],
                        y=by_player["Player"],
                        orientation="h",
                        name=target,
                        marker_color=color,
                        hovertemplate=f"<b>%{{y}}</b><br>{target}: %{{x:,.0f}}<extra></extra>",
                    ))
                fig.update_layout(
                    barmode="stack",
                    height=max(360, 48 + 30 * len(by_player)),
                    margin=dict(l=0, r=10, t=10, b=30),
                    xaxis=dict(title="Damage", tickformat=",.0f", gridcolor=c()["border"]),
                    yaxis=dict(title="", autorange="reversed"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text="Target"),
                    **plot_style(),
                )
                st.plotly_chart(fig, use_container_width=True)

                target_table = df_view.sort_values("Damage", ascending=False)[[
                    "Player", "Class", "Target", "Target Type", "Damage",
                    "% Player Damage",
                ]].copy()
                target_table["Damage"] = target_table["Damage"].apply(lambda value: f"{value:,.0f}")
                target_table["% Player Damage"] = target_table["% Player Damage"].apply(lambda value: f"{value:.1f}%")
                target_table.columns = ["Player", "Class", "Target", "Type", "Damage", "% of player damage"]
                st.dataframe(target_table, hide_index=True, use_container_width=True)

    # ── Timeline ─────────────────────────────────────────────────────────
    with tab_timeline:
        df_tl = pd.DataFrame(fight_data["timeline"])
        if df_tl.empty:
            st.info("Brak danych.")
        else:
            all_event_types = sorted(df_tl["Event Type"].unique())
            default_types   = [t_ for t_ in all_event_types if t_ not in ("Fight Start", "Fight End")]
            selected_types  = st.multiselect("Typy eventów", all_event_types, default=default_types)
            df_filtered = df_tl[df_tl["Event Type"].isin(selected_types + ["Fight Start", "Fight End"])]
            players      = df_tl[df_tl["Player"] != ""]["Player"].dropna().unique()
            player_order = sorted(players)
            p_to_idx     = {p: i for i, p in enumerate(player_order)}
            fig = go.Figure()
            shown = set()
            for etype in all_event_types + ["Fight Start", "Fight End"]:
                df_ev = df_filtered[df_filtered["Event Type"] == etype]
                if df_ev.empty:
                    continue
                color  = EVENT_COLORS.get(etype, "#cccccc")
                symbol = EVENT_SYMBOLS.get(etype, "circle")
                y_vals, htexts = [], []
                for _, row in df_ev.iterrows():
                    pl = row.get("Player", "")
                    y_vals.append(p_to_idx.get(pl, -1) if pl else -0.5)
                    detail = row.get("Detail", "")
                    htexts.append(
                        f"<b>{row['Event Type']}</b><br>"
                        f"{pl} ({row.get('Class','')})<br>"
                        f"t = {row['Event Time (s)']:.1f}s ({row['Event Time']})<br>"
                        f"{detail}"
                    )
                fig.add_trace(go.Scatter(
                    x=df_ev["Event Time (s)"].tolist(), y=y_vals,
                    mode="markers", name=etype,
                    marker=dict(color=color, symbol=symbol,
                                size=14 if etype == "Death" else 10,
                                line=dict(color="rgba(0,0,0,0.4)", width=1)),
                    hovertemplate="%{customdata}<extra></extra>",
                    customdata=htexts,
                    legendgroup=etype, showlegend=etype not in shown,
                ))
                shown.add(etype)
            fig.add_vline(x=meta["duration_s"], line_dash="dash", line_color=c()["border"],
                          annotation_text="End", annotation_position="top")
            fig.update_layout(
                height=max(350, 80 + 40 * len(player_order)),
                margin=dict(l=10, r=10, t=30, b=30),
                xaxis=dict(title="Czas walki (s)", range=[-2, meta["duration_s"] + 5],
                           gridcolor=c()["border"]),
                yaxis=dict(title="", tickvals=list(range(len(player_order))),
                           ticktext=player_order, autorange="reversed",
                           gridcolor=c()["border"]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                **plot_style(),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Boss spell damage")
        st.caption(
            "Dwa warianty tego samego widoku: surowe eventy per hit oraz agregacja do bucketów 1s. "
            "Filtr graczy sumuje damage tylko dla wybranych targetów."
        )

        df_spell_damage = pd.DataFrame(fight_data.get("damage_taken", []))
        df_enemy_casts = pd.DataFrame(fight_data.get("enemy_casts", []))
        if df_spell_damage.empty:
            st.info("Brak spell damage w cache dla tego pulla.")
        else:
            df_spell_damage = df_spell_damage.copy()
            df_spell_damage["Amount"] = pd.to_numeric(df_spell_damage["Amount"], errors="coerce").fillna(0)
            df_spell_damage["Event Time (s)"] = pd.to_numeric(df_spell_damage["Event Time (s)"], errors="coerce")
            df_spell_damage = df_spell_damage.dropna(subset=["Ability", "Player", "Event Time (s)"])
            df_spell_damage = df_spell_damage[df_spell_damage["Amount"] > 0]

            enemy_spell_set: set[str] = set()
            if not df_enemy_casts.empty and "Ability" in df_enemy_casts.columns:
                enemy_spell_set = {
                    str(value)
                    for value in df_enemy_casts["Ability"].dropna().astype(str).tolist()
                    if str(value).strip()
                }
            if enemy_spell_set:
                df_spell_damage = df_spell_damage[df_spell_damage["Ability"].isin(enemy_spell_set)]

            spell_options = sorted(df_spell_damage["Ability"].dropna().astype(str).unique().tolist())
            player_options = sorted(df_spell_damage["Player"].dropna().astype(str).unique().tolist())
            all_players_label = "Wszyscy"

            if not spell_options:
                st.info("Brak enemy spell damage po odfiltrowaniu spelli spoza encountera.")
            else:
                filters_left, filters_right = st.columns(2)
                default_spell_count = len(spell_options)
                selected_spells = spell_options
                selected_players = [all_players_label]
                spell_key = f"spell_damage_spells_{meta['report']}_{meta['fight_id']}"
                player_key = f"spell_damage_players_{meta['report']}_{meta['fight_id']}"
                with filters_left:
                    with st.popover(f"Boss spells · {default_spell_count}/{default_spell_count}", use_container_width=True):
                        selected_spells = st.multiselect(
                            "Boss spells",
                            spell_options,
                            default=spell_options,
                            key=spell_key,
                            label_visibility="collapsed",
                        )
                with filters_right:
                    with st.popover(f"Players hit · {all_players_label}", use_container_width=True):
                        selected_players = st.multiselect(
                            "Players hit",
                            [all_players_label] + player_options,
                            default=[all_players_label],
                            key=player_key,
                            label_visibility="collapsed",
                            help="Wszyscy = suma damage dla całego raidu. Wybranie konkretnych graczy sumuje tylko ich damage taken.",
                        )

                if all_players_label in selected_players and len(selected_players) > 1:
                    selected_players = [player for player in selected_players if player != all_players_label]
                    st.session_state[player_key] = selected_players
                if not selected_players:
                    selected_players = [all_players_label]
                    st.session_state[player_key] = selected_players

                spell_summary = (
                    "Wszystkie spelle"
                    if len(selected_spells) == len(spell_options)
                    else f"{len(selected_spells)} z {len(spell_options)} spelli"
                )
                if all_players_label in selected_players:
                    player_summary = "Wszyscy gracze"
                else:
                    player_summary = ", ".join(selected_players[:3])
                    if len(selected_players) > 3:
                        player_summary += f" +{len(selected_players) - 3}"
                st.caption(f"{spell_summary} · {player_summary}")

                df_spell_filtered = df_spell_damage.copy()
                if selected_spells:
                    df_spell_filtered = df_spell_filtered[df_spell_filtered["Ability"].isin(selected_spells)]
                if all_players_label not in selected_players:
                    df_spell_filtered = df_spell_filtered[df_spell_filtered["Player"].isin(selected_players)]

                if df_spell_filtered.empty:
                    st.info("Brak spell damage dla wybranych filtrów.")
                else:
                    metrics = st.columns(4)
                    total_spell_damage = df_spell_filtered["Amount"].sum()
                    metrics[0].metric("Spell hits", f"{len(df_spell_filtered):,}")
                    metrics[1].metric("Total damage", _fmt_compact_number(total_spell_damage))
                    metrics[2].metric("Spells", str(df_spell_filtered["Ability"].nunique()))
                    metrics[3].metric("Players", str(df_spell_filtered["Player"].nunique()))

                    raw_tab, bucket_tab = st.tabs(["Raw events", "1s buckets"])
                    with raw_tab:
                        _render_spell_damage_timeline(
                            df_spell_filtered,
                            meta,
                            bucket_seconds=None,
                            chart_key_suffix=f"raw_{meta['report']}_{meta['fight_id']}",
                        )
                    with bucket_tab:
                        _render_spell_damage_timeline(
                            df_spell_filtered,
                            meta,
                            bucket_seconds=1,
                            chart_key_suffix=f"bucket_{meta['report']}_{meta['fight_id']}",
                        )

    # ── Deaths ───────────────────────────────────────────────────────────
    with tab_deaths:
        df_deaths = pd.DataFrame(fight_data["deaths"])
        if df_deaths.empty:
            st.info("Nikt nie umarł w tej walce! 🎉")
        else:
            st.metric("Łączna liczba śmierci", len(df_deaths))
            players_dead     = df_deaths["Player"].unique()
            player_death_idx = {p: i for i, p in enumerate(sorted(players_dead))}
            fig = go.Figure()
            for _, row in df_deaths.iterrows():
                fig.add_trace(go.Scatter(
                    x=[row["Death Time (s)"]],
                    y=[player_death_idx.get(row["Player"], 0)],
                    mode="markers",
                    marker=dict(color="#e74c3c", symbol="x", size=14,
                                line=dict(color="darkred", width=2)),
                    name=row["Player"], showlegend=False,
                    hovertemplate=(
                        f"<b>{row['Player']}</b> ({row.get('Class','')})<br>"
                        f"Czas: {row['Death Time']} ({row['Death Time (s)']:.1f}s)<br>"
                        f"Zabił: {row['Killing Blow']}"
                        "<extra></extra>"
                    ),
                ))
            fig.update_layout(
                height=max(200, 60 + 35 * len(players_dead)),
                margin=dict(l=10, r=10, t=20, b=30),
                xaxis=dict(title="Czas walki (s)", range=[-2, meta["duration_s"] + 5],
                           gridcolor=c()["border"]),
                yaxis=dict(tickvals=list(player_death_idx.values()),
                           ticktext=list(player_death_idx.keys()),
                           autorange="reversed", gridcolor=c()["border"]),
                **plot_style(),
            )
            st.plotly_chart(fig, use_container_width=True)
            display_cols = ["Player", "Class", "Death Time", "Killing Blow"]
            available    = [col for col in display_cols if col in df_deaths.columns]
            sort_col     = "Death Time (s)" if "Death Time (s)" in df_deaths.columns else available[0]
            st.dataframe(df_deaths.sort_values(sort_col)[available],
                         hide_index=True, use_container_width=True)

    # ── Interrupts ───────────────────────────────────────────────────────
    with tab_interrupts:
        df_int = pd.DataFrame(fight_data["interrupts"])
        if df_int.empty:
            st.info("Brak interruptów.")
        else:
            df_int = df_int.sort_values("Count", ascending=False)
            st.metric("Łączna liczba interruptów", df_int["Count"].sum())
            fig = go.Figure(go.Bar(
                x=df_int["Count"], y=df_int["Player"], orientation="h",
                marker_color=[CLASS_COLORS.get(col, "#aaaaaa") for col in df_int.get("Class", [])],
                hovertemplate="<b>%{y}</b><br>Interrupts: %{x}<extra></extra>",
            ))
            fig.update_layout(
                height=max(200, 50 + 30 * len(df_int)),
                margin=dict(l=0, r=10, t=10, b=10),
                xaxis=dict(title="Liczba interruptów", gridcolor=c()["border"]),
                yaxis=dict(autorange="reversed"),
                **plot_style(),
            )
            st.plotly_chart(fig, use_container_width=True)
            cols = [col for col in ["Player", "Class", "Count"] if col in df_int.columns]
            st.dataframe(df_int[cols], hide_index=True, use_container_width=True)

    # ── Dispels ──────────────────────────────────────────────────────────
    with tab_dispels:
        df_disp = pd.DataFrame(fight_data["dispels"])
        if df_disp.empty:
            st.info("Brak dispelli.")
        else:
            df_disp = df_disp.sort_values("Count", ascending=False)
            st.metric("Łączna liczba dispelli", df_disp["Count"].sum())
            fig = go.Figure(go.Bar(
                x=df_disp["Count"], y=df_disp["Player"], orientation="h",
                marker_color=[CLASS_COLORS.get(col, "#aaaaaa") for col in df_disp.get("Class", [])],
                hovertemplate="<b>%{y}</b><br>Dispels: %{x}<extra></extra>",
            ))
            fig.update_layout(
                height=max(200, 50 + 30 * len(df_disp)),
                margin=dict(l=0, r=10, t=10, b=10),
                xaxis=dict(title="Liczba dispelli", gridcolor=c()["border"]),
                yaxis=dict(autorange="reversed"),
                **plot_style(),
            )
            st.plotly_chart(fig, use_container_width=True)
            cols = [col for col in ["Player", "Class", "Count"] if col in df_disp.columns]
            st.dataframe(df_disp[cols], hide_index=True, use_container_width=True)

    # ── Consumables ──────────────────────────────────────────────────────
    with tab_consumables:
        df_cons = pd.DataFrame(fight_data["consumables"])
        if df_cons.empty:
            st.info("Brak danych o consumablach.")
        else:
            skip_cols     = {"Report","Date","Boss","Pull #","Result","Boss HP %","Duration (s)","Player","Class"}
            category_cols = [col for col in df_cons.columns if col not in skip_cols]
            available     = [col for col in ["Player","Class"] + category_cols if col in df_cons.columns]
            df_show       = df_cons[available].copy()

            def highlight_zero(val):
                return "color: #555555" if val == 0 else ""

            st.dataframe(
                df_show.style.map(highlight_zero, subset=category_cols),
                hide_index=True, use_container_width=True,
            )
            st.caption("Suma po kategoriach:")
            totals = {col: df_cons[col].sum() for col in category_cols if col in df_cons.columns}
            cols_ui = st.columns(len(totals))
            for col_ui, (name, total) in zip(cols_ui, totals.items()):
                col_ui.metric(name, total)

    # ── Defensives ───────────────────────────────────────────────────────
    with tab_defensives:
        df_def = pd.DataFrame(fight_data["defensives"])
        if df_def.empty:
            st.info("Brak użyć defensywnych cooldownów.")
        else:
            st.dataframe(
                df_def[["Player","Class","Ability","Count"]].sort_values(
                    ["Player","Count"], ascending=[True, False]),
                hide_index=True, use_container_width=True,
            )
            df_agg = (df_def.groupby("Ability")["Count"].sum()
                      .reset_index().sort_values("Count", ascending=True))
            fig = go.Figure(go.Bar(
                x=df_agg["Count"], y=df_agg["Ability"], orientation="h",
                marker_color=c()["green"],
                hovertemplate="<b>%{y}</b><br>Użycia: %{x}<extra></extra>",
            ))
            fig.update_layout(
                height=max(200, 50 + 25 * len(df_agg)),
                margin=dict(l=0, r=10, t=20, b=10),
                xaxis=dict(title="Liczba użyć", gridcolor=c()["border"]),
                title=dict(text="Użycia per ability (wszyscy gracze)", font_color=c()["text_dim"]),
                **plot_style(),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Dialog trigger ────────────────────────────────────────────────────
    if st.session_state.open_dialog and st.session_state.selected_player:
        st.session_state.open_dialog = False
        player_profile_dialog(index, st.session_state.selected_player)


# ===========================================================================
# PAGE: playground
# ===========================================================================
elif st.session_state.current_page == "playground":
    clr = c()
    st.markdown(f"""
<style>
.play-header {{ margin:0 0 14px; }}
.play-title {{ color:{clr["text"]}; font-size:22px; font-weight:750; }}
.play-sub {{ color:{clr["text_dim"]}; font-size:14px; margin-top:4px; }}
.play-grid {{
    display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap:8px; margin:12px 0;
}}
.play-card {{
    border:1px solid {clr["border"]}; border-radius:6px;
    background: color-mix(in srgb, {clr["bg2"]} 74%, transparent);
    padding:11px 12px;
}}
.play-card .label {{ color:{clr["text_dim"]}; font-size:13px; font-weight:600; }}
.play-card .value {{ color:{clr["text"]}; font-size:24px; font-weight:750; margin-top:4px; }}
.play-section {{
    border:1px solid {clr["border"]}; border-radius:6px;
    background: color-mix(in srgb, {clr["bg2"]} 70%, transparent);
    padding:12px 14px; margin:12px 0;
}}
.play-section .chart-hdr {{ color:{clr["text"]}; font-size:16px; font-weight:700; margin-bottom:8px; }}
.play-note {{
    border:1px solid {clr["gold_dim"]}; border-radius:6px;
    background: color-mix(in srgb, {clr["gold"]} 8%, transparent);
    color:{clr["text_dim"]}; padding:10px 12px; font-size:14px; margin:10px 0;
}}
</style>
<div class="play-header">
  <div class="play-title">Playground</div>
  <div class="play-sub">Eksperymentalne raporty performance z obecnego cache WCL.</div>
</div>
""", unsafe_allow_html=True)

    frames_raw = load_playground_frames()
    fights_all = frames_raw.get("fights", pd.DataFrame())
    perf_all = frames_raw.get("performance", pd.DataFrame())
    if fights_all.empty or perf_all.empty:
        st.info("Brak danych do raportów eksperymentalnych.")
        st.stop()

    boss_options = sorted(fights_all["Boss"].dropna().astype(str).unique()) if "Boss" in fights_all.columns else []
    player_options = sorted(perf_all["Player"].dropna().astype(str).unique(), key=str.casefold) if "Player" in perf_all.columns else []

    f1, f2, f3 = st.columns([1, 1.35, 1])
    with f1:
        date_mode = st.selectbox("Zakres", ["Ostatnie 30 dni", "Ostatnia noc", "Cała historia"], key="play_date")
    with f2:
        boss_filter = st.selectbox("Boss", ["Wszystkie"] + boss_options, key="play_boss")
    with f3:
        fight_filter = st.selectbox("Typ walk", ["Wszystkie", "Kille", "Wipe’y"], key="play_fight_type")

    pull_labels, pull_values = _playground_pull_options(
        fights_all, date_mode, boss_filter, fight_filter,
    )
    f4, f5 = st.columns([1.8, 1.2])
    with f4:
        pull_label = st.selectbox("Pull", pull_labels, key="play_pull")
        pull_filter = pull_values.get(pull_label)
    with f5:
        player_filter = st.selectbox("Gracz", ["Wszyscy"] + player_options, key="play_player")

    frames = _filter_playground_frames(
        frames_raw, date_mode, boss_filter, fight_filter, player_filter,
        pull_filter=pull_filter,
    )
    fights = frames["fights"]
    perf = frames["performance"]
    targets = frames["targets"]
    deaths = frames["deaths"]
    defensives = frames["defensives"]
    consumables = frames["consumables"]
    damage_taken = frames["damage_taken"]
    interrupts = frames["interrupts"]
    dispels = frames["dispels"]
    rankings = frames["rankings"]
    boss_rankings = frames["boss_rankings"]
    defensive_events = frames["defensive_events"]
    consumable_events = frames["consumable_events"]
    enemy_casts = frames["enemy_casts"]
    player_details = frames["player_details"]
    insights = build_playground_insights(frames)

    total_pulls = len(fights)
    total_kills = int(fights["Kill"].sum()) if not fights.empty and "Kill" in fights.columns else 0
    total_players = perf["Player"].nunique() if not perf.empty and "Player" in perf.columns else 0
    total_deaths = len(deaths)
    total_taken = damage_taken["Amount"].sum() if not damage_taken.empty and "Amount" in damage_taken.columns else 0
    cards = [
        ("Pulls", total_pulls),
        ("Kills", total_kills),
        ("Players", total_players),
        ("Deaths", total_deaths),
        ("Damage taken", _fmt_compact_number(total_taken)),
    ]
    st.markdown(
        '<div class="play-grid">' +
        ''.join(f'<div class="play-card"><div class="label">{label}</div><div class="value">{value}</div></div>' for label, value in cards) +
        '</div>',
        unsafe_allow_html=True,
    )

    (
        tab_priority,
        tab_deaths,
        tab_def,
        tab_cons,
        tab_active,
        tab_utility,
        tab_gear,
        tab_comp,
    ) = st.tabs([
        "Priority Targets", "Death Quality", "Defensives", "Consumables",
        "Active Time", "Interrupts / Dispels", "Gear / Parses", "Raid Comp",
    ])

    with tab_priority:
        st.markdown(
            '<div class="play-note"><b>Co pokazuje:</b> podział damage gracza na konkretne cele. '
            '<b>Boss Share %</b> ma skalę 0-100%: 100% oznacza, że cały damage z wybranych pulli poszedł w target typu Boss; '
            'niższa wartość oznacza większy udział addów/innych celów. Wykres słupkowy jest stackowany: złoto = boss, czerwony = pozostałe cele. '
            '<b>Target totals</b> pokazuje sumę damage w każdy nazwany cel, więc można sprawdzić kto realnie bił konkretne addy.</div>',
            unsafe_allow_html=True,
        )
        if targets.empty:
            st.info("Brak target damage w cache dla aktualnych filtrów.")
        else:
            per_player, target_totals = insights["target_priority"]
            if per_player.empty:
                st.info("Brak nazwanych targetów dla aktualnych filtrów.")
                st.stop()

            c1, c2 = st.columns([1, 1])
            with c1:
                show = per_player.sort_values("Boss Damage", ascending=True).tail(20)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=show["Boss Damage"], y=show["Player"], orientation="h", name="Boss", marker_color=clr["gold"]))
                fig.add_trace(go.Bar(x=show["Non Boss Damage"], y=show["Player"], orientation="h", name="Other targets", marker_color=clr["red"]))
                fig.update_layout(
                    barmode="stack",
                    height=max(360, 60 + 24 * len(show)),
                    margin=dict(l=0, r=10, t=10, b=30),
                    xaxis=dict(title="Damage", tickformat=",.0f", gridcolor=clr["border"]),
                    yaxis=dict(autorange="reversed"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    **plot_style(),
                )
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.plotly_chart(
                    _plot_bar(target_totals.tail(15), "Damage", "Target", color=clr["gold"], height=420),
                    use_container_width=True,
                )
            st.dataframe(
                per_player.sort_values("Boss Share %", ascending=False),
                hide_index=True,
                width="stretch",
                column_config={
                    "Boss Share %": st.column_config.ProgressColumn("Boss Share", min_value=0, max_value=100, format="%.1f%%"),
                    "Total": st.column_config.NumberColumn(format="%.0f"),
                    "Boss Damage": st.column_config.NumberColumn(format="%.0f"),
                    "Non Boss Damage": st.column_config.NumberColumn(format="%.0f"),
                },
            )
            if boss_rankings.empty:
                st.markdown('<div class="play-note">Boss Damage parse pojawi się po odświeżeniu cache z opcją Playground data. To percentile 0-100 z WCL `playerMetric=bossdps`; wyżej oznacza lepszy boss-only DPS względem rankingów WCL.</div>', unsafe_allow_html=True)

    with tab_deaths:
        st.markdown(
            '<div class="play-note"><b>Co pokazuje:</b> jakość śmierci w pullach. '
            '<b>Deaths</b> to liczba śmierci. <b>Early Death &lt;= 90s</b> oznacza śmierć do 90 sekundy walki; skala jest liczbowa, nie procentowa. '
            '<b>Avg_Time</b> to średni czas śmierci w sekundach od startu pulla. Drugi wykres pokazuje killing blow, czyli ostatnią zdolność przypisaną przez WCL jako zabójczą.</div>',
            unsafe_allow_html=True,
        )
        if deaths.empty:
            st.info("Brak śmierci w aktualnych filtrach.")
        else:
            by_player, by_ability, d = insights["death_quality"]
            c1, c2 = st.columns([1, 1])
            with c1:
                st.plotly_chart(_plot_bar(by_player.sort_values("Deaths", ascending=True).tail(20), "Deaths", "Player", color=clr["red"]), use_container_width=True)
            with c2:
                st.plotly_chart(_plot_bar(by_ability.tail(15), "Deaths", "Killing Blow", color=clr["red"]), use_container_width=True)
            d_view = d[["Date", "Report", "Boss", "Pull #", "Result", "Player", "Class", "Death Time", "Death Time (s)", "Killing Blow", "Early Death"]].sort_values("Death Time (s)").copy()
            d_view["Early Death <= 90s"] = np.where(d_view["Early Death"], "Tak", "Nie")
            d_view = d_view.drop(columns=["Early Death"])
            st.dataframe(
                d_view,
                hide_index=True,
                width="stretch",
                height=420,
                column_config={
                    "Death Time (s)": st.column_config.NumberColumn(format="%.1f"),
                    "Early Death <= 90s": st.column_config.TextColumn(
                        help="Tak = gracz zginął do 90 sekundy pulla. Nie = śmierć później."
                    ),
                },
            )

    with tab_def:
        st.markdown(
            '<div class="play-note"><b>Co pokazuje:</b> użycie defensyw w relacji do liczby pulli i śmierci. '
            '<b>Defensives / Pull</b> = liczba zarejestrowanych defensyw / liczba pulli gracza. '
            '<b>Defensives / Death</b> = liczba defensyw / liczba śmierci. '
            '<b>Defensive Before Death %</b>, jeśli cache ma timestampy eventów, pokazuje procent śmierci poprzedzonych defensywą w ostatnich 15 sekundach; skala 0-100%, wyżej zwykle lepiej.</div>',
            unsafe_allow_html=True,
        )
        if defensives.empty and deaths.empty:
            st.info("Brak danych defensyw i śmierci dla aktualnych filtrów.")
        else:
            def_quality = insights["defensive_quality"]
            st.dataframe(
                def_quality,
                hide_index=True,
                width="stretch",
                height=420,
                column_config={
                    "Defensives / Pull": st.column_config.NumberColumn(format="%.2f"),
                    "Defensives / Death": st.column_config.NumberColumn(format="%.2f"),
                    "Defensive Before Death %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%"),
                },
            )
            if defensive_events.empty:
                st.markdown('<div class="play-note">Kolumna Defensive Before Death % pojawi się po odświeżeniu cache z opcją Playground data.</div>', unsafe_allow_html=True)

    with tab_cons:
        st.markdown(
            '<div class="play-note"><b>Co pokazuje:</b> użycie consumables zdefiniowanych w konfiguracji spell ID. '
            '<b>Compliance %</b> ma skalę 0-100% i oznacza procent pulli, w których gracz użył przynajmniej jednego śledzonego consumable. '
            '<b>Avg_Consumables</b> to średnia liczba użyć na pull. Wynik nie obejmuje flask/food/rune, jeśli ich ID nie ma w konfiguracji.</div>',
            unsafe_allow_html=True,
        )
        if consumables.empty:
            st.info("Brak danych consumables.")
        else:
            compliance = insights["consumable_compliance"]
            if compliance.empty:
                st.info("Brak kolumn consumables w cache.")
            else:
                st.plotly_chart(_plot_bar(compliance.tail(25), "Compliance %", "Player", color=clr["green"]), use_container_width=True)
                st.dataframe(
                    compliance,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Compliance %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
                        "Avg_Consumables": st.column_config.NumberColumn(format="%.2f"),
                    },
                )
                if consumable_events.empty:
                    st.markdown('<div class="play-note">Timestampy konkretnych użyć pojawią się po odświeżeniu cache z opcją Playground data.</div>', unsafe_allow_html=True)

    with tab_active:
        st.markdown(
            '<div class="play-note"><b>Co pokazuje:</b> aktywny czas z tabeli WCL. '
            '<b>Avg Active</b> ma skalę 0-100% i oznacza średni udział czasu, w którym gracz wykonywał akcje liczone przez WCL. '
            '<b>Low_Active</b> to liczba pulli poniżej 80%. Niska wartość może oznaczać downtime, mechanikę albo śmierć, więc wymaga interpretacji z kontekstem walki.</div>',
            unsafe_allow_html=True,
        )
        active = insights["active_time"]
        if active.empty:
            st.info("Brak danych active time.")
        else:
            st.plotly_chart(_plot_bar(active.head(25).sort_values("Avg_Active", ascending=True), "Avg_Active", "Player", color=clr["gold"]), use_container_width=True)
            st.dataframe(
                active,
                hide_index=True,
                width="stretch",
                column_config={
                    "Avg_Active": st.column_config.ProgressColumn("Avg Active", min_value=0, max_value=100, format="%.1f%%"),
                },
            )

    with tab_utility:
        st.markdown(
            '<div class="play-note"><b>Co pokazuje:</b> wykonane utility oraz, po rozszerzonym fetchu, casty przeciwników. '
            '<b>Interrupts</b> i <b>Dispels</b> to liczby wykonanych akcji. '
            '<b>Enemy Casts</b> pokazuje ile razy dana zdolność przeciwnika została rozpoczęta; to baza do późniejszego liczenia missed opportunities i coverage. '
            'Skala wykresu castów jest liczbowa: im większy słupek, tym częściej cast pojawiał się w wybranych pullach.</div>',
            unsafe_allow_html=True,
        )
        utility, cast_summary = insights["utility_coverage"]
        if utility.empty:
            st.info("Brak interruptów/dispelli dla aktualnych filtrów.")
        else:
            st.dataframe(utility, hide_index=True, width="stretch", height=420)
        if not cast_summary.empty:
            st.plotly_chart(_plot_bar(cast_summary.head(20).sort_values("Casts", ascending=True), "Casts", "Ability", color=clr["red"], height=420), use_container_width=True)
        else:
            st.markdown('<div class="play-note">Enemy Casts pojawią się po odświeżeniu cache z opcją Playground data.</div>', unsafe_allow_html=True)

    with tab_gear:
        st.markdown(
            '<div class="play-note"><b>Co pokazuje:</b> parse i gear metadata z WCL. '
            '<b>Avg Parse</b>, <b>Best Parse</b>, <b>Avg ilvl Parse</b> i <b>Boss Damage parse</b> są percentylami 0-100: wyżej oznacza lepszy wynik względem porównywalnych logów WCL. '
            '<b>Avg_Ilvl</b> to średni item level z rankingów WCL. Talenty/trinkety są opisowe i pojawiają się, gdy fetch pobierze `playerDetails`.</div>',
            unsafe_allow_html=True,
        )
        if rankings.empty:
            st.info("Brak rankings/gear dla aktualnych filtrów. Rankingi WCL są dostępne głównie dla killi.")
        else:
            gear = insights["gear_parse_summary"]
            st.dataframe(
                gear,
                hide_index=True,
                width="stretch",
                height=460,
                column_config={
                    "Avg_Parse": st.column_config.ProgressColumn("Avg Parse", min_value=0, max_value=100, format="%.0f"),
                    "Best_Parse": st.column_config.NumberColumn(format="%.0f"),
                    "Avg_Ilvl": st.column_config.NumberColumn(format="%.1f"),
                    "Avg_Ilvl_Parse": st.column_config.ProgressColumn("Avg ilvl Parse", min_value=0, max_value=100, format="%.0f"),
                    "Avg_Boss_Parse": st.column_config.ProgressColumn("Avg Boss Parse", min_value=0, max_value=100, format="%.0f"),
                    "Best_Boss_Parse": st.column_config.NumberColumn(format="%.0f"),
                },
            )
            if boss_rankings.empty or player_details.empty:
                st.markdown('<div class="play-note">Boss Damage parse i playerDetails pojawią się po odświeżeniu cache z opcją Playground data.</div>', unsafe_allow_html=True)

    with tab_comp:
        st.markdown(
            '<div class="play-note"><b>Co pokazuje:</b> strukturę raidu w wybranych pullach. '
            '<b>Class totals</b> zlicza wystąpienia klas w pullach, więc jedna osoba może liczyć się kilka razy, jeśli jest w wielu pullach. '
            '<b>Fight size</b> pokazuje liczbę unikalnych graczy i klas w konkretnym pullu. Role tank/healer/dps pojawiają się, jeśli cache ma `playerDetails`.</div>',
            unsafe_allow_html=True,
        )
        class_totals, fight_size = insights["raid_composition"]
        if class_totals.empty:
            st.info("Brak danych kompozycji.")
        else:
            st.plotly_chart(_plot_bar(class_totals, "Players", "Class", color=clr["gold"]), use_container_width=True)
            st.dataframe(fight_size, hide_index=True, width="stretch", height=420)
            if player_details.empty:
                st.markdown('<div class="play-note">Podział ról pojawi się po odświeżeniu cache z opcją Playground data.</div>', unsafe_allow_html=True)


# ===========================================================================
# PAGE: admin
# ===========================================================================
elif st.session_state.current_page == "admin":
    clr = c()
    st.markdown(f"""
<style>
.admin-header {{ margin: 0 0 14px; }}
.admin-header .page-title {{ font-size: 20px; font-weight: 700; color:{clr["text"]}; }}
</style>
<div class="admin-header">
  <div class="page-title">Admin</div>
</div>
""", unsafe_allow_html=True)
    render_admin_controls()


# ===========================================================================
# PAGE: attendance
# ===========================================================================
elif st.session_state.current_page == "attendance":
    clr = c()

    # WoW class colours
    CLASS_CLR = {
        "DeathKnight": "#C41E3A", "DemonHunter": "#A330C9", "Druid":   "#FF7C0A",
        "Evoker":      "#33937F", "Hunter":      "#AAD372", "Mage":    "#3FC7EB",
        "Monk":        "#00FF98", "Paladin":     "#F48CBA", "Priest":  "#FFFFFF",
        "Rogue":       "#FFF468", "Shaman":      "#0070DD", "Warlock": "#8788EE",
        "Warrior":     "#C69B3A",
    }

    st.markdown(f"""
<style>
.att-header {{ margin: 0 0 14px; }}
.att-header h2 {{
    color: {clr["text"]}; margin: 0; font-size: 20px; font-weight: 700;
}}
.stat-cards {{
    display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
    border: 1px solid {clr["border"]};
    background: color-mix(in srgb, {clr["bg2"]} 78%, transparent);
    border-radius: 6px; overflow: hidden; margin-bottom: 14px;
}}
.stat-card {{
    padding: 10px 12px; border-right: 1px solid {clr["border"]};
}}
.stat-card:last-child {{
    border-right: 0;
}}
.stat-card .sc-label {{
    font-size: 13px; color: {clr["text_dim"]}; margin-bottom: 5px; font-weight: 600;
}}
.stat-card .sc-value {{
    font-size: 24px; font-weight: 750; color: {clr["text"]}; line-height: 1.1;
}}
.sc-green {{ color: {clr["green"]} !important; }}
.hm-wrap {{
    background: color-mix(in srgb, {clr["bg2"]} 72%, transparent);
    border: 1px solid {clr["border"]};
    border-radius: 6px; overflow: hidden; margin: 16px 0 14px;
}}
.attendance-map {{
    margin-top: 12px;
    margin-bottom: 16px;
}}
.hm-header {{
    padding: 10px 12px; border-bottom: 1px solid {clr["border"]};
    font-size: 15px; font-weight: 700; color: {clr["text"]};
}}
    .hm-scroll {{ padding: 14px; overflow-x: auto; overflow-y: auto; max-height: 340px; }}
    .hm-table {{ border-collapse: collapse; font-size: 11px; white-space: nowrap; }}
.hm-table th {{
    color: {clr["text_dim"]}; padding: 3px 5px;
    text-align: center; font-weight: 400;
}}
.hm-table td {{ padding: 2px 4px; text-align: center; }}
.hm-player {{ text-align: right !important; padding-right: 10px !important; font-size: 11px; }}
.hm-cell {{
    width: 20px; height: 20px; border-radius: 3px; display: inline-block;
}}
.hm-absent  {{ background: #1a1d26; border: 1px solid {clr["border"]}; }}
.hm-present {{ background: #7a5e22; border: 1px solid #c89b3c44; }}
    .hm-bright  {{ background: #c89b3c; border: 1px solid #f0c060; }}
    .session-grid {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 8px; margin: 10px 0 12px;
    }}
    .session-card {{
        background: color-mix(in srgb, {clr["bg2"]} 72%, transparent);
        border: 1px solid {clr["border"]};
        border-radius: 5px; padding: 10px 12px;
    }}
    .session-card.active {{ border-color: {clr["gold_dim"]}; background: color-mix(in srgb, {clr["bg3"]} 72%, transparent); }}
    .session-card .date {{ color: {clr["text"]}; font-weight: 700; font-size: 15px; }}
    .session-card .code {{ color: {clr["text_dim"]}; font-size: 13px; margin-top: 2px; }}
    .session-card .count {{ color: {clr["text"]}; font-size: 22px; font-weight: 750; margin-top: 8px; }}
    .session-card .guests {{ color: {clr["red"]}; font-size: 13px; font-weight: 700; margin-top: 4px; }}
    .mini-roster {{
        display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 6px; padding: 10px;
    }}
    .roster-pill {{
        background: {clr["bg3"]}; border: 1px solid {clr["border"]};
        border-radius: 4px; padding: 7px 9px; font-size: 14px;
        display: flex; justify-content: space-between; gap: 8px;
    }}
    .roster-pill .cls {{ color: {clr["text_dim"]}; font-size: 12px; }}
    .compact-matrix {{
        display: grid; grid-template-columns: repeat(auto-fill, minmax(128px, 1fr));
        gap: 6px;
    }}
    .player-strip {{
        background: {clr["bg2"]}; border: 1px solid {clr["border"]};
        border-radius: 4px; padding: 7px 8px;
    }}
    .player-strip .name {{
        font-size: 14px; font-weight: 700; overflow: hidden;
        white-space: nowrap; text-overflow: ellipsis;
    }}
    .player-strip .dots {{ display: flex; gap: 3px; margin-top: 6px; }}
    .dot {{ width: 11px; height: 11px; border-radius: 2px; }}
    .dot.on {{ background: {clr["gold"]}; border: 1px solid {clr["gold_light"]}; }}
    .dot.off {{ background: #1a1d26; border: 1px solid {clr["border"]}; }}
    .att-wrap {{
        background: color-mix(in srgb, {clr["bg2"]} 72%, transparent);
        border: 1px solid {clr["border"]};
        border-radius: 6px; overflow: hidden; margin-bottom: 12px;
}}
.att-tbl {{ width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }}
.att-tbl thead {{ position: sticky; top: 0; z-index: 1; background: {clr["bg2"]}; }}
.att-tbl th {{
    padding: 9px 14px; text-align: left;
    font-size: 13px; color: {clr["text_dim"]}; border-bottom: 1px solid {clr["border"]};
    font-weight: 600;
}}
.att-tbl td {{ padding: 9px 14px; border-bottom: 1px solid {clr["border"]}33; }}
.att-tbl tr:hover td {{ background: {clr["bg3"]}; }}
.att-pct {{ font-weight: 700; }}
.pct-high {{ color: {clr["green"]}; }}
.pct-mid  {{ color: {clr["gold"]}; }}
.pct-low  {{ color: {clr["red"]}; }}
</style>
<div class="att-header">
  <h2>Attendance</h2>
</div>
""", unsafe_allow_html=True)

    df_att = load_attendance()
    if df_att.empty:
        st.info("Brak danych o attendance.\n\nPobierz: `python fetch.py --attendance`")
    else:
        if df_att["Presence"].dtype == object:
            df_att["Presence"] = pd.to_numeric(df_att["Presence"], errors="coerce").fillna(0)
        df_att["Present"] = (df_att["Presence"] > 0).astype(int)
        df_att["Night"] = df_att["Date"].astype(str).str[:10]
        df_att["Session"] = df_att["Date"].astype(str).str[:10] + " | " + df_att["Report"].astype(str)

        nights_sorted = sorted(df_att["Night"].dropna().unique())
        n_nights = len(nights_sorted)
        player_nights = (
            df_att.groupby(["Player", "Night"], as_index=False)
            .agg(Present=("Present", "max"))
        )

        # Player summary with class
        player_class = (
            df_att.groupby("Player")["Class"].first()
            if "Class" in df_att.columns else pd.Series(dtype=str)
        )
        player_summary = (
            player_nights.groupby("Player")
            .agg(Nights_Present=("Present", "sum"))
            .reset_index()
        )
        player_summary["Nights_Total"] = n_nights
        player_summary["Attendance_pct"] = (
            player_summary["Nights_Present"] / n_nights * 100
        ).round(1)
        player_summary["Class"] = player_summary["Player"].map(player_class)
        player_summary = player_summary.sort_values("Attendance_pct", ascending=False)

        avg_att = player_summary["Attendance_pct"].mean()
        avg_color = clr["green"] if avg_att >= 85 else clr["gold"] if avg_att >= 70 else clr["red"]
        low_players = int((player_summary["Attendance_pct"] < 70).sum())

        # ── Stat cards ────────────────────────────────────────────────────
        st.markdown(f"""
<div class="stat-cards">
  <div class="stat-card">
    <div class="sc-label">Gracze</div>
    <div class="sc-value">{len(player_summary)}</div>
  </div>
  <div class="stat-card">
    <div class="sc-label">Noce raidowe</div>
    <div class="sc-value">{n_nights}</div>
  </div>
  <div class="stat-card">
    <div class="sc-label">Śr. frekwencja</div>
    <div class="sc-value" style="color:{avg_color}">{avg_att:.0f}%</div>
  </div>
  <div class="stat-card">
    <div class="sc-label">Poniżej 70%</div>
    <div class="sc-value" style="color:{clr["red"] if low_players else clr["green"]}">{low_players}</div>
  </div>
</div>
""", unsafe_allow_html=True)

        session_counts = (
            df_att.groupby(["Session", "Date", "Report"])
            .agg(Present=("Present", "sum"))
            .reset_index()
            .sort_values(["Date", "Report"], ascending=[False, True])
        )
        guild_members_path = CACHE_DIR / "guild_members.json"
        if guild_members_path.exists():
            guild_members_raw = json.loads(guild_members_path.read_text(encoding="utf-8"))
            guild_members = {member.get("name") for member in guild_members_raw if member.get("name")}
        else:
            guild_members = set(df_att["Player"].dropna())

        guest_counts = {}
        guest_names = {}
        for report in index:
            report_code = report.get("report_code")
            session_key = f'{report.get("date")} | {report_code}'
            participants = {}
            for fight in report.get("fights", []):
                fight_path = CACHE_DIR / f"fight_{report_code}_{fight['fight_id']}.json"
                fight_data = load_fight(report_code, fight["fight_id"]) if fight_path.exists() else None
                if not fight_data:
                    continue
                for perf_row in fight_data.get("performance", []):
                    player = perf_row.get("Player")
                    player_class = perf_row.get("Class")
                    if player and player_class in CLASS_CLR:
                        participants[player] = player_class
            guests = sorted(player for player in participants if player not in guild_members)
            guest_counts[session_key] = len(guests)
            guest_names[session_key] = guests

        night_dates = sorted(df_att["Night"].unique(), reverse=True)
        selected_night = st.selectbox("Noc raidowa", night_dates, key="attendance_night")

        cards_html = ""
        for _, row in session_counts.iterrows():
            active = " active" if str(row["Date"])[:10] == selected_night else ""
            guests = guest_counts.get(row["Session"], 0)
            guest_title = ", ".join(guest_names.get(row["Session"], []))
            guest_html = (
                f'<div class="guests" title="{guest_title}">+ {guests} spoza gildii</div>'
                if guests else ""
            )
            cards_html += (
                f'<div class="session-card{active}">'
                f'<div class="date">{str(row["Date"])[:10]}</div>'
                f'<div class="code">{row["Report"]}</div>'
                f'<div class="count">{int(row["Present"])} obecnych</div>'
                f'{guest_html}'
                f'</div>'
            )
        st.markdown(f'<div class="session-grid">{cards_html}</div>', unsafe_allow_html=True)

        class_map = df_att.groupby("Player")["Class"].first().to_dict()

        # ── Compact matrix ───────────────────────────────────────────────
        pivot = {}
        for _, row in player_nights.iterrows():
            pivot.setdefault(row["Player"], {})[row["Night"]] = int(row["Present"])

        compact_html = ""
        for _, ps_row in player_summary.iterrows():
            player = ps_row["Player"]
            cls    = ps_row["Class"] if pd.notna(ps_row["Class"]) else ""
            color  = CLASS_CLR.get(cls, clr["text"])
            pct    = ps_row["Attendance_pct"]
            player_data = pivot.get(player, {})
            dots = ""
            for night in nights_sorted:
                v = player_data.get(night, 0)
                dot_cls = "on" if v else "off"
                label = "Obecny" if v else "Nieobecny"
                dots += f'<span class="dot {dot_cls}" title="{player} • {night} • {label}"></span>'
            compact_html += (
                f'<div class="player-strip">'
                f'<div class="name" style="color:{color}" title="{player}">{player}</div>'
                f'<div style="font-size:10px;color:{clr["text_dim"]};margin-top:2px">{pct:.0f}% · {int(ps_row["Nights_Present"])}/{n_nights}</div>'
                f'<div class="dots">{dots}</div>'
                f'</div>'
            )

        st.markdown(f"""
<div class="hm-wrap attendance-map">
  <div class="hm-header">Kompaktowa mapa obecności</div>
  <div style="padding:14px">
    <div class="compact-matrix">{compact_html}</div>
  </div>
</div>
""", unsafe_allow_html=True)

        night_df = df_att[df_att["Night"] == selected_night]
        night_sessions = (
            night_df[["Session", "Report"]]
            .drop_duplicates()
            .sort_values("Report")
            .to_dict("records")
        )
        split_cols = st.columns(max(1, len(night_sessions)))
        for col, session in zip(split_cols, night_sessions):
            session_players = sorted(
                night_df[(night_df["Session"] == session["Session"]) & (night_df["Present"] == 1)]["Player"]
            )
            pills = ""
            for player in session_players:
                cls = class_map.get(player, "")
                color = CLASS_CLR.get(cls, clr["text"])
                pills += (
                    f'<div class="roster-pill"><span style="color:{color};font-weight:700">{player}</span>'
                    f'<span class="cls">{cls}</span></div>'
                )
            with col:
                st.markdown(
                    f'<div class="att-wrap"><div class="hm-header">Grupa · {session["Report"]} · {len(session_players)}</div>'
                    f'<div class="mini-roster">{pills}</div></div>',
                    unsafe_allow_html=True,
                )

        # ── Summary table ─────────────────────────────────────────────────
        tbl_rows = ""
        for _, ps_row in player_summary.iterrows():
            player = ps_row["Player"]
            cls    = ps_row["Class"] if pd.notna(ps_row["Class"]) else "—"
            color  = CLASS_CLR.get(cls, clr["text"])
            present = int(ps_row["Nights_Present"])
            total   = int(ps_row["Nights_Total"])
            pct     = ps_row["Attendance_pct"]
            pct_cls = "pct-high" if pct >= 90 else "pct-mid" if pct >= 70 else "pct-low"
            tbl_rows += (
                f'<tr>'
                f'<td style="color:{color};font-weight:600">{player}</td>'
                f'<td style="color:{clr["text_dim"]}">{cls}</td>'
                f'<td>{present}</td>'
                f'<td>{total}</td>'
                f'<td><span class="att-pct {pct_cls}">{pct:.0f}%</span></td>'
                f'</tr>'
            )

        st.markdown(f"""
<div class="att-wrap">
  <div class="hm-header">Podsumowanie graczy</div>
  <div style="max-height:420px;overflow-y:auto">
    <table class="att-tbl">
      <thead><tr>
        <th>Gracz</th><th>Klasa</th><th>Noce obecny</th><th>Noce razem</th><th>Frekwencja %</th>
      </tr></thead>
      <tbody>{tbl_rows}</tbody>
    </table>
  </div>
</div>
""", unsafe_allow_html=True)


# ===========================================================================
# PAGE: gracze
# ===========================================================================
elif st.session_state.current_page == "gracze":
    clr = c()

    def _fmt_value(value, suffix: str = "", digits: int = 0) -> str:
        if pd.isna(value):
            return "—"
        if digits:
            return f"{float(value):,.{digits}f}{suffix}"
        return f"{float(value):,.0f}{suffix}"

    def _player_line_chart(df_src: pd.DataFrame, y_cols: list[tuple[str, str, str | None]], title_y: str = "") -> go.Figure:
        fig = go.Figure()
        if not df_src.empty:
            df_plot = df_src.sort_values("Date")
            for col, label, color in y_cols:
                if col not in df_plot.columns:
                    continue
                series = df_plot[["Date", col, "Boss", "Pull #", "Result"]].dropna(subset=[col])
                if series.empty:
                    continue
                fig.add_trace(go.Scatter(
                    x=series["Date"],
                    y=series[col],
                    mode="lines+markers",
                    name=label,
                    line=dict(color=color or clr["gold"], width=2),
                    marker=dict(size=7),
                    customdata=series[["Boss", "Pull #", "Result"]],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Pull #%{customdata[1]} · %{customdata[2]}<br>"
                        "%{x|%Y-%m-%d}<br>"
                        f"{label}: %{{y:,.0f}}<extra></extra>"
                    ),
                ))
        fig.update_layout(
            height=300,
            margin=dict(l=36, r=12, t=8, b=36),
            xaxis=dict(tickformat="%d-%m", gridcolor=clr["border"]),
            yaxis=dict(title=title_y, gridcolor=clr["border"], zerolinecolor=clr["border"]),
            legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)"),
            font_color=clr["text"],
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        return fig

    st.markdown(f"""
<style>
.players-header {{ margin: 0 0 14px; }}
.players-header .page-title {{ font-size: 20px; font-weight: 700; color:{clr["text"]}; }}
.player-side-title {{
    font-size:15px; color:{clr["text"]}; font-weight:700; margin:0 0 10px;
}}
.player-identity {{
    display:grid; grid-template-columns: minmax(220px, 1fr) auto; align-items:center; gap:16px;
    border:1px solid {clr["border"]};
    border-left:3px solid {clr["gold_dim"]};
    background: color-mix(in srgb, {clr["bg2"]} 78%, transparent);
    border-radius:6px;
    padding:14px 16px;
    margin-bottom:12px;
}}
.player-name {{ font-size:24px; color:{clr["text"]}; font-weight:750; line-height:1.15; }}
.player-sub {{ color:{clr["text_dim"]}; font-size:14px; margin-top:3px; }}
.player-context {{
    color:{clr["text_dim"]}; font-size:14px; text-align:right;
    max-width:520px; line-height:1.35;
}}
.players-kpis {{
    display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    border:1px solid {clr["border"]};
    background: color-mix(in srgb, {clr["bg2"]} 78%, transparent);
    border-radius:6px; overflow:hidden; margin-bottom:12px;
}}
.player-kpi {{
    padding:12px 14px; min-height:76px;
    border-right:1px solid {clr["border"]};
    border-bottom:1px solid {clr["border"]};
}}
.player-kpi .label {{
    color:{clr["text_dim"]}; font-size:13px; font-weight:600;
}}
.player-kpi .value {{ color:{clr["text"]}; font-size:24px; font-weight:750; margin-top:4px; }}
.player-kpi .sub {{ color:{clr["text_dim"]}; font-size:13px; margin-top:2px; }}
.players-section {{
    border:1px solid {clr["border"]};
    background: color-mix(in srgb, {clr["bg2"]} 72%, transparent);
    border-radius:6px;
    padding:12px 14px;
    margin-bottom:12px;
}}
.players-section .chart-hdr {{
    color:{clr["text"]}; font-size:16px; font-weight:700; margin-bottom:8px;
}}
@media (max-width: 1100px) {{
    .player-identity {{ grid-template-columns: 1fr; }}
    .player-context {{ text-align:left; }}
}}
</style>
<div class="players-header">
  <div class="page-title">Players</div>
</div>
""", unsafe_allow_html=True)

    fights_all, parses_all, attendance_all = load_player_profile_sources()
    player_source_frames = []
    for src in (fights_all, parses_all, attendance_all):
        if not src.empty and {"Player", "Class"}.issubset(src.columns):
            player_source_frames.append(src[src["Class"].isin(CLASS_COLORS)][["Player", "Class"]])
    if player_source_frames:
        all_players = sorted(
            pd.concat(player_source_frames, ignore_index=True)["Player"].dropna().astype(str).unique(),
            key=str.casefold,
        )
    else:
        all_players = []

    if not all_players:
        st.info("Brak danych graczy w cache.")
    else:
        st.markdown('<div class="player-side-title">Filtry</div>', unsafe_allow_html=True)
        f_search, f_date, f_type = st.columns([1.4, 1, 1])
        with f_search:
            search = st.text_input("Szukaj", value="", key="players_search")
        with f_date:
            date_mode = st.selectbox(
                "Zakres",
                ["Ostatnie 30 dni", "Ostatnia noc", "Cała historia"],
                index=0,
                key="players_date_mode",
            )
        if not st.session_state.get("players_defaults_v2_applied") and st.session_state.get("players_fight_type", "Wszystkie") == "Wszystkie":
            st.session_state.players_fight_type = "Kille"
        with f_type:
            fight_filter = st.selectbox(
                "Typ walk",
                ["Wszystkie", "Kille", "Wipe’y"],
                index=1,
                key="players_fight_type",
            )

        fights_scope = _date_filtered(fights_all, date_mode)
        parses_scope = _date_filtered(parses_all, date_mode)
        boss_options = sorted(set(
            ([] if fights_scope.empty else fights_scope["Boss"].dropna().astype(str).tolist()) +
            ([] if parses_scope.empty else parses_scope["Boss"].dropna().astype(str).tolist())
        ))
        if (
            not st.session_state.get("players_defaults_v2_applied")
            and boss_options
            and st.session_state.get("players_boss", "Wszystkie") == "Wszystkie"
        ):
            st.session_state.players_boss = boss_options[0]
        f_boss, f_sort, f_player = st.columns([1.4, 1, 1.6])
        with f_boss:
            boss_filter = st.selectbox("Boss", ["Wszystkie"] + boss_options, index=1 if boss_options else 0, key="players_boss")

        summary_rows = []
        attendance_scope = _date_filtered(attendance_all, date_mode)
        for player in all_players:
            pf = fights_scope[fights_scope["Player"] == player] if not fights_scope.empty else pd.DataFrame()
            pp = parses_scope[parses_scope["Player"] == player] if not parses_scope.empty else pd.DataFrame()
            pa = attendance_scope[attendance_scope["Player"] == player] if not attendance_scope.empty else pd.DataFrame()
            cls = ""
            spec = ""
            for src in (pp, pf, pa):
                if not src.empty:
                    if not cls and "Class" in src.columns:
                        vals = src["Class"].dropna().astype(str)
                        cls = vals.mode().iloc[0] if not vals.empty else ""
                    if not spec and "Spec" in src.columns:
                        vals = src["Spec"].dropna().astype(str)
                        spec = vals.mode().iloc[0] if not vals.empty else ""
            total_nights = attendance_scope["Night"].nunique() if not attendance_scope.empty and "Night" in attendance_scope.columns else 0
            present = pa.groupby("Night")["Present"].max().sum() if not pa.empty and "Night" in pa.columns else 0
            avg_parse = pp["Parse %"].mean() if not pp.empty and "Parse %" in pp.columns else np.nan
            latest = pf["Date"].max() if not pf.empty and "Date" in pf.columns else pd.NaT
            if cls in CLASS_COLORS:
                summary_rows.append({
                    "Player": player,
                    "Class": cls,
                    "Spec": spec,
                    "Attendance": present / total_nights * 100 if total_nights else np.nan,
                    "Avg Parse": avg_parse,
                    "Latest": latest,
                })
        players_summary = pd.DataFrame(summary_rows)
        if players_summary.empty:
            st.warning("Brak prawdziwych graczy dla aktualnych danych.")
            st.stop()
        players_summary["Spec"] = players_summary["Spec"].fillna("")
        players_summary["Class"] = players_summary["Class"].fillna("")

        with f_sort:
            sort_mode = st.selectbox(
                "Sortuj",
                ["Alfabetycznie", "Avg parse", "Attendance", "Ostatnia aktywność"],
                key="players_sort",
            )
        filtered_players = players_summary.copy()
        if search:
            filtered_players = filtered_players[
                filtered_players["Player"].str.contains(search, case=False, na=False)
            ]
        if sort_mode == "Avg parse":
            filtered_players = filtered_players.sort_values("Avg Parse", ascending=False, na_position="last")
        elif sort_mode == "Attendance":
            filtered_players = filtered_players.sort_values("Attendance", ascending=False, na_position="last")
        elif sort_mode == "Ostatnia aktywność":
            filtered_players = filtered_players.sort_values("Latest", ascending=False, na_position="last")
        else:
            filtered_players = filtered_players.sort_values("Player", key=lambda s: s.str.casefold())

        if filtered_players.empty:
            st.warning("Brak graczy dla tej wyszukiwarki.")
            st.stop()

        player_options = filtered_players["Player"].tolist()
        player_param = st.query_params.get("player", "")
        current_player = st.session_state.get("players_current")
        if player_param in player_options:
            default_player = player_param
        elif (
            not st.session_state.get("players_defaults_v2_applied")
            and not player_param
            and player_options
        ):
            default_player = player_options[0]
        elif current_player in player_options:
            default_player = current_player
        else:
            default_player = player_options[0]

        with f_player:
            selected_player = st.selectbox(
                "Gracz",
                player_options,
                index=player_options.index(default_player),
                key="players_selected",
                format_func=lambda name: (
                    f"{name} · "
                    f"{filtered_players.loc[filtered_players['Player'].eq(name), 'Class'].iloc[0]}"
                    f"{(' · ' + str(filtered_players.loc[filtered_players['Player'].eq(name), 'Spec'].iloc[0])) if str(filtered_players.loc[filtered_players['Player'].eq(name), 'Spec'].iloc[0]) else ''}"
                ),
            )
        st.session_state.players_current = selected_player
        st.session_state.players_defaults_v2_applied = True
        st.query_params["player"] = selected_player

        selected_row = filtered_players[filtered_players["Player"] == selected_player].iloc[0]
        st.caption(
            f"{len(player_options)} graczy w filtrze · "
            f"{selected_row['Class']} {selected_row['Spec'] or ''} · "
            f"Att {_fmt_value(selected_row['Attendance'], '%')} · "
            f"Avg parse {_fmt_value(selected_row['Avg Parse'])}"
        )

        profile = build_player_profile_data(selected_player, date_mode, boss_filter, fight_filter)
        meta = profile["meta"]
        p_fights = profile["player_fights"]
        p_parses = profile["player_parses"]
        color = CLASS_COLORS.get(meta["class"], clr["text"])
        metric = meta["metric"]

        st.markdown(
            f"""
<div class="player-identity">
  <div>
<div class="player-name" style="color:{color}">{selected_player}</div>
<div class="player-sub">{meta["class"] or "—"} · {meta["spec"] or "—"} · {meta["role"] or "rola z logów"}</div>
  </div>
  <div class="player-context">{date_mode} · {fight_filter} · {boss_filter}</div>
</div>
""",
            unsafe_allow_html=True,
        )

        kpis = [
            ("Attendance", _fmt_value(meta["attendance_pct"], "%"), f'{meta["player_nights"]}/{meta["total_nights"]} nocy'),
            ("Avg parse", _fmt_value(meta["avg_parse"]), f'{meta["parse_rows"]} kill wpisów'),
            ("Best parse", _fmt_value(meta["best_parse"]), "najlepszy kill"),
            (f"Avg {metric}", _fmt_value(meta["avg_output"]), f'{meta["pulls"]} pulli'),
            ("Zgony / pull", _fmt_value(meta["deaths_per_pull"], digits=2), "średnio"),
            ("Def / Cons", f'{_fmt_value(meta["defensives_per_pull"], digits=1)} / {_fmt_value(meta["consumables_per_pull"], digits=1)}', "na pull"),
        ]
        kpi_html = "".join(
            f'<div class="player-kpi"><div class="label">{label}</div><div class="value">{value}</div><div class="sub">{sub}</div></div>'
            for label, value, sub in kpis
        )
        st.markdown(f'<div class="players-kpis">{kpi_html}</div>', unsafe_allow_html=True)

        t1, t2 = st.columns(2)
        with t1:
            st.markdown('<div class="players-section"><div class="chart-hdr">Trend parse / ilvl parse</div>', unsafe_allow_html=True)
            if p_parses.empty:
                st.info("Brak parse’ów z killi dla aktualnych filtrów.")
            else:
                parse_chart_rows = p_parses.copy()
                parse_chart_rows["Pull #"] = parse_chart_rows.get("Pull #", "")
                y_cols = [("Parse %", "Parse", None)]
                if "ilvl Parse %" in parse_chart_rows.columns and parse_chart_rows["ilvl Parse %"].gt(0).any():
                    y_cols.append(("ilvl Parse %", "ilvl Parse", clr["gold_light"]))
                st.plotly_chart(_player_line_chart(parse_chart_rows, y_cols, "Parse"), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with t2:
            st.markdown(f'<div class="players-section"><div class="chart-hdr">Trend {metric} po pullach</div>', unsafe_allow_html=True)
            if p_fights.empty:
                st.info("Brak pulli dla aktualnych filtrów.")
            else:
                st.plotly_chart(_player_line_chart(p_fights, [(metric, metric, clr["green"])], metric), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        c_left, c_right = st.columns([1.15, 0.85])
        with c_left:
            st.markdown('<div class="players-section"><div class="chart-hdr">Boss breakdown</div>', unsafe_allow_html=True)
            boss_summary = profile["boss_summary"]
            if boss_summary.empty:
                st.info("Brak danych bossów dla aktualnych filtrów.")
            else:
                display_cols = [
                    "Boss", "Avg Parse", "Best Parse", "Pulls", "Kills",
                    "Avg Output", "Deaths", "Deaths / Pull", "Def / Pull", "Cons / Pull",
                ]
                display_cols = [col for col in display_cols if col in boss_summary.columns]
                st.dataframe(
                    boss_summary[display_cols],
                    hide_index=True,
                    width="stretch",
                    height=380,
                    column_config={
                        "Avg Parse": st.column_config.ProgressColumn("Avg", min_value=0, max_value=100, format="%.0f"),
                        "Best Parse": st.column_config.NumberColumn("Best", format="%.0f"),
                        "Avg Output": st.column_config.NumberColumn(f"Avg {metric}", format="%.0f"),
                        "Deaths / Pull": st.column_config.NumberColumn(format="%.2f"),
                        "Def / Pull": st.column_config.NumberColumn(format="%.1f"),
                        "Cons / Pull": st.column_config.NumberColumn(format="%.1f"),
                    },
                )
            st.markdown("</div>", unsafe_allow_html=True)

        with c_right:
            st.markdown('<div class="players-section"><div class="chart-hdr">Problemy do sprawdzenia</div>', unsafe_allow_html=True)
            issues = profile["issues"]
            if issues.empty:
                st.success("Brak mocnych sygnałów problemowych w aktualnym zakresie.")
            else:
                issues_view = issues.copy()
                if "Date" in issues_view.columns:
                    issues_view["Date"] = pd.to_datetime(issues_view["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
                st.dataframe(issues_view, hide_index=True, width="stretch", height=380)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="players-section"><div class="chart-hdr">Porównanie do roli / speca</div>', unsafe_allow_html=True)
        peers = profile["peers"]
        if peers.empty:
            st.info("Brak porównywalnych graczy dla aktualnych filtrów.")
        else:
            cols = ["Player", "Class", "Spec", "Avg_Parse", "Avg_Output", "Death_Rate", "Avg_Active", "Pulls"]
            cols = [col for col in cols if col in peers.columns]
            peers_view = peers[cols].copy()
            st.dataframe(
                peers_view,
                hide_index=True,
                width="stretch",
                height=360,
                column_config={
                    "Avg_Parse": st.column_config.ProgressColumn("Avg Parse", min_value=0, max_value=100, format="%.0f"),
                    "Avg_Output": st.column_config.NumberColumn(f"Avg {metric}", format="%.0f"),
                    "Death_Rate": st.column_config.NumberColumn("Deaths / Pull", format="%.2f"),
                    "Avg_Active": st.column_config.NumberColumn("Active %", format="%.1f"),
                },
            )
        st.markdown("</div>", unsafe_allow_html=True)


# ===========================================================================
# PAGE: parsy
# ===========================================================================
elif st.session_state.current_page == "parsy":
    clr = c()

    CLASS_CLR_P = {
        "DeathKnight": "#C41E3A", "DemonHunter": "#A330C9", "Druid":   "#FF7C0A",
        "Evoker":      "#33937F", "Hunter":      "#AAD372", "Mage":    "#3FC7EB",
        "Monk":        "#00FF98", "Paladin":     "#F48CBA", "Priest":  "#e0e0e0",
        "Rogue":       "#FFF468", "Shaman":      "#0070DD", "Warlock": "#8788EE",
        "Warrior":     "#C69B3A",
    }

    def _parse_badge(val):
        if pd.isna(val):
            return "—"
        v = int(round(val))
        if v >= 95:   tier = "parse-legendary"
        elif v >= 75: tier = "parse-epic"
        elif v >= 50: tier = "parse-rare"
        else:         tier = "parse-common"
        return f'<span class="parse-pct {tier}">{v}</span>'

    def _fmt_signed(val: float) -> str:
        if pd.isna(val):
            return "—"
        return f"{val:+.0f}"

    def _report_label(code: str) -> str:
        report_meta = {r.get("report_code"): r for r in index}
        meta = report_meta.get(code, {})
        title = meta.get("title") or "Raport"
        return f"{title} | {code}"

    def _line_chart(df_src, player, y_cols):
        fig = go.Figure()
        dp = df_src[df_src["Player"] == player].sort_values("Date")
        p_cls = dp["Class"].iloc[0] if not dp.empty and "Class" in dp.columns else ""
        color = CLASS_CLR_P.get(p_cls, clr["gold"])

        for y_col, label, line_color in y_cols:
            if y_col not in dp.columns:
                continue
            series = dp[["Date", y_col, "Boss"]].dropna()
            if y_col != "Parse %":
                series = series[series[y_col] > 0]
            if series.empty:
                continue
            fig.add_trace(go.Scatter(
                x=series["Date"],
                y=series[y_col],
                mode="lines+markers",
                name=label,
                line=dict(color=line_color or color, width=2),
                marker=dict(size=7),
                customdata=series[["Boss"]],
                hovertemplate="<b>%{customdata[0]}</b><br>%{x|%d-%m %H:%M}<br>"
                              f"{label}: %{{y:.0f}}<extra></extra>",
            ))
        for pct, lclr in [(95, "#ff8000"), (75, "#a335ee"), (50, "#0070dd")]:
            fig.add_hline(y=pct, line_dash="dot", line_color=lclr, opacity=0.3)
        fig.update_layout(
            height=320,
            margin=dict(l=36, r=12, t=10, b=36),
            yaxis=dict(
                title="", range=[0, 100],
                gridcolor=clr["border"], zerolinecolor=clr["border"],
            ),
            xaxis=dict(tickformat="%d-%m", gridcolor=clr["border"]),
            legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color=clr["text"],
        )
        return fig

    # ── CSS ───────────────────────────────────────────────────────────────
    st.markdown(f"""
<style>
.parsy-header {{
    margin-bottom: 18px;
}}
.parsy-header .page-title {{
    font-size: 24px; font-weight: 700; color:{clr["gold"]};
    margin-bottom: 4px; text-shadow: 0 0 30px rgba(200,155,60,0.2);
}}
.parsy-header .page-subtitle {{ color:{clr["text_dim"]}; font-size:14px; margin:0; }}
.parse-note {{
    color:{clr["text_dim"]}; font-size:14px; margin: -6px 0 14px;
}}
.chart-hdr {{
    font-size:14px; font-weight:700; text-transform:none;
    letter-spacing:0; color:{clr["text"]};
    border-bottom:1px solid {clr["border"]}; padding-bottom:8px;
    margin-bottom:10px;
}}
.pcard {{
    background:{clr["bg2"]}; border:1px solid {clr["border"]};
    border-radius:6px; padding:14px 16px; margin-bottom:14px;
}}
.parse-kpi {{
    background:{clr["bg2"]}; border:1px solid {clr["border"]};
    border-radius:6px; padding:12px 14px; min-height:78px;
}}
.parse-kpi .label {{
    font-size:13px; color:{clr["text_dim"]}; text-transform:none;
    letter-spacing:0; font-weight:700;
}}
.parse-kpi .value {{
    font-size:28px; color:{clr["gold"]}; font-weight:800; margin-top:6px;
}}
.parse-kpi .sub {{ font-size:13px; color:{clr["text_dim"]}; margin-top:2px; }}
.parse-pct {{
    font-weight:700; padding:2px 7px; border-radius:3px;
    font-size:13px; display:inline-block; min-width:38px; text-align:center;
}}
.parse-legendary {{ background:#332200; color:#ff8000; border:1px solid #ff800040; }}
.parse-epic      {{ background:#1a0a2e; color:#a335ee; border:1px solid #a335ee40; }}
.parse-rare      {{ background:#001a33; color:#0070dd; border:1px solid #0070dd40; }}
.parse-common    {{ background:#1e2130; color:#9d9d9d; border:1px solid #9d9d9d40; }}
</style>
<div class="parsy-header">
  <div class="page-title">Parses</div>
  <div class="page-subtitle">Oficjalne rankingi Warcraft Logs tylko dla killów</div>
</div>
""", unsafe_allow_html=True)

    df_parses = load_parses_index()
    if df_parses.empty:
        st.info("Brak danych.\n\nPobierz:\n```\npython fetch.py --force\n```")
    else:
        for col in ("Parse %", "ilvl Parse %", "Item Level", "ilvl Bracket", "Median Parse %", "Amount"):
            if col in df_parses.columns:
                df_parses[col] = pd.to_numeric(df_parses[col], errors="coerce")
        if "Metric" not in df_parses.columns:
            role_series = df_parses["Role"] if "Role" in df_parses.columns else pd.Series("", index=df_parses.index)
            df_parses["Metric"] = np.where(role_series.eq("Healers"), "Healing", "Damage")
        df_parses["Date"] = pd.to_datetime(df_parses["Date"], errors="coerce")
        df_parses["Raid Date"] = df_parses["Date"].dt.strftime("%Y-%m-%d")

        df_parses = df_parses[df_parses["Result"] == "Kill"].copy()
        all_dates = sorted(df_parses["Raid Date"].dropna().unique(), reverse=True)
        all_reports = sorted(df_parses["Report"].dropna().unique()) if "Report" in df_parses.columns else []
        all_roles = sorted(df_parses["Role"].dropna().unique()) if "Role" in df_parses.columns else []

        st.markdown(
            '<div class="parse-note">Ten widok pokazuje wyłącznie rankingi z zabitych bossów. '
            'Wipe’y analizuj w zakładce Walki.</div>',
            unsafe_allow_html=True,
        )

        fc1, fc2, fc3, fc4 = st.columns([1.2, 2.4, 1.9, 1.4])
        with fc1:
            sel_date = st.selectbox("Data", ["Wszystkie"] + all_dates, key="parsy_date")
        with fc2:
            report_options = ["Wszystkie"] + all_reports
            sel_report = st.selectbox(
                "Raport / grupa",
                report_options,
                format_func=lambda code: "Wszystkie" if code == "Wszystkie" else _report_label(code),
                key="parsy_report",
            )
        with fc4:
            sel_role = st.selectbox("Rola", ["Wszystkie"] + all_roles, key="parsy_role")

        df_base = df_parses.copy()
        if sel_date != "Wszystkie":
            df_base = df_base[df_base["Raid Date"] == sel_date]
        if sel_report != "Wszystkie" and "Report" in df_base.columns:
            df_base = df_base[df_base["Report"] == sel_report]
        if sel_role != "Wszystkie" and "Role" in df_base.columns:
            df_base = df_base[df_base["Role"] == sel_role]

        available_bosses = sorted(df_base["Boss"].dropna().unique())
        with fc3:
            sel_boss = st.selectbox(
                "Boss",
                ["Wszystkie"] + available_bosses,
                key=f"parsy_boss_{sel_date}_{sel_report}_{sel_role}",
            )

        df_f = df_base.copy()
        if sel_boss != "Wszystkie":
            df_f = df_f[df_f["Boss"] == sel_boss]

        if df_f.empty:
            st.warning(
                "Brak parsów dla wybranych filtrów. "
                "Zakładka Parsy pokazuje tylko oficjalne rankingi Warcraft Logs z killów."
            )
        else:
            df_f = df_f.sort_values("Date")
            ilvl_col = "ilvl Bracket" if "ilvl Bracket" in df_f.columns else "Item Level"

            group_cols = ["Player", "Class", "Spec"]
            if "Role" in df_f.columns:
                group_cols.append("Role")
            if "Metric" in df_f.columns:
                group_cols.append("Metric")
            agg_spec = {
                "Avg Parse": ("Parse %", "mean"),
                "Best": ("Parse %", "max"),
                "Worst": ("Parse %", "min"),
                "Parses": ("Parse %", "count"),
                "Latest": ("Parse %", "last"),
            }
            if ilvl_col in df_f.columns:
                agg_spec["Avg ilvl"] = (ilvl_col, "mean")
            if "ilvl Parse %" in df_f.columns:
                agg_spec["Avg ilvl Parse"] = ("ilvl Parse %", "mean")

            summary = df_f.groupby(group_cols).agg(**agg_spec).reset_index()

            trend_rows = []
            for player, rows in df_f.sort_values("Date").groupby("Player"):
                vals = rows["Parse %"].dropna().tail(2).tolist()
                trend_rows.append({"Player": player, "Trend": vals[-1] - vals[-2] if len(vals) == 2 else np.nan})
            summary = summary.merge(pd.DataFrame(trend_rows), on="Player", how="left")
            summary = summary.sort_values("Avg Parse", ascending=False)

            avg_parse = df_f["Parse %"].mean()
            best_row = df_f.loc[df_f["Parse %"].idxmax()]
            low_count = int((summary["Avg Parse"] < 50).sum())
            legendary_count = int((df_f["Parse %"] >= 95).sum())

            k1, k2, k3, k4 = st.columns(4)
            kpis = [
                ("Śr. parse", f"{avg_parse:.0f}", f"{len(df_f)} wpisów"),
                ("Najlepszy parse", f"{best_row['Parse %']:.0f}", f"{best_row['Player']} · {best_row['Boss']}"),
                ("95+", str(legendary_count), "pojedyncze wyniki"),
                ("Avg < 50", str(low_count), "gracze do sprawdzenia"),
            ]
            for col, (label, value, sub) in zip((k1, k2, k3, k4), kpis):
                col.markdown(
                    f'<div class="parse-kpi"><div class="label">{label}</div>'
                    f'<div class="value">{value}</div><div class="sub">{sub}</div></div>',
                    unsafe_allow_html=True,
                )

            tab_overview, tab_boss, tab_player = st.tabs([
                "Raid Overview", "Boss Breakdown", "Player Detail",
            ])

            with tab_overview:
                c_left, c_right = st.columns([1.2, 1])
                with c_left:
                    st.markdown('<div class="pcard"><div class="chart-hdr">Ranking graczy</div>', unsafe_allow_html=True)
                    top = summary.sort_values("Avg Parse", ascending=True).tail(20)
                    fig = go.Figure(go.Bar(
                        x=top["Avg Parse"],
                        y=top["Player"],
                        orientation="h",
                        marker_color=[
                            CLASS_CLR_P.get(cls, clr["gold"]) for cls in top["Class"]
                        ],
                        customdata=top[["Spec", "Best", "Worst", "Trend"]],
                        hovertemplate=(
                            "<b>%{y}</b><br>%{customdata[0]}<br>"
                            "Avg: %{x:.0f}<br>Best: %{customdata[1]:.0f}<br>"
                            "Worst: %{customdata[2]:.0f}<br>Trend: %{customdata[3]:+.0f}"
                            "<extra></extra>"
                        ),
                    ))
                    for pct, line_color in [(95, "#ff8000"), (75, "#a335ee"), (50, "#0070dd")]:
                        fig.add_vline(x=pct, line_dash="dot", line_color=line_color, opacity=0.35)
                    fig.update_layout(
                        height=max(320, len(top) * 24),
                        margin=dict(l=8, r=12, t=4, b=24),
                        xaxis=dict(range=[0, 100], gridcolor=clr["border"]),
                        yaxis=dict(title=""),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font_color=clr["text"],
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                with c_right:
                    st.markdown('<div class="pcard"><div class="chart-hdr">Szybkie sygnały</div>', unsafe_allow_html=True)
                    top_players = summary.nlargest(5, "Avg Parse")[["Player", "Spec", "Avg Parse", "Best"]].copy()
                    weak_players = summary.nsmallest(5, "Avg Parse")[["Player", "Spec", "Avg Parse", "Worst"]].copy()
                    movers = summary.dropna(subset=["Trend"]).copy()
                    movers = movers.reindex(movers["Trend"].abs().sort_values(ascending=False).index).head(5)

                    st.caption("Top performers")
                    st.dataframe(
                        top_players,
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "Avg Parse": st.column_config.NumberColumn(format="%.0f"),
                            "Best": st.column_config.NumberColumn(format="%.0f"),
                        },
                    )
                    st.caption("Do sprawdzenia")
                    st.dataframe(
                        weak_players,
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "Avg Parse": st.column_config.NumberColumn(format="%.0f"),
                            "Worst": st.column_config.NumberColumn(format="%.0f"),
                        },
                    )
                    if not movers.empty:
                        st.caption("Największe zmiany")
                        movers_view = movers[["Player", "Spec", "Trend", "Latest"]].copy()
                        movers_view["Trend"] = movers_view["Trend"].apply(_fmt_signed)
                        st.dataframe(movers_view, hide_index=True, width="stretch")
                    st.markdown('</div>', unsafe_allow_html=True)

                table_cols = ["Player", "Class", "Spec"]
                if "Role" in summary.columns:
                    table_cols.append("Role")
                if "Metric" in summary.columns:
                    table_cols.append("Metric")
                table_cols += ["Avg Parse", "Best", "Worst", "Latest", "Trend", "Parses"]
                if "Avg ilvl Parse" in summary.columns:
                    table_cols.append("Avg ilvl Parse")
                if "Avg ilvl" in summary.columns:
                    table_cols.append("Avg ilvl")

                st.markdown('<div class="pcard"><div class="chart-hdr">Tabela decyzyjna</div>', unsafe_allow_html=True)
                st.dataframe(
                    summary[table_cols],
                    hide_index=True,
                    width="stretch",
                    height=470,
                    column_config={
                        "Avg Parse": st.column_config.ProgressColumn("Avg", min_value=0, max_value=100, format="%.0f"),
                        "Best": st.column_config.NumberColumn("Best", format="%.0f"),
                        "Worst": st.column_config.NumberColumn("Worst", format="%.0f"),
                        "Latest": st.column_config.NumberColumn("Latest", format="%.0f"),
                        "Trend": st.column_config.NumberColumn("Trend", format="%+.0f"),
                        "Avg ilvl Parse": st.column_config.ProgressColumn("ilvl Parse", min_value=0, max_value=100, format="%.0f"),
                        "Avg ilvl": st.column_config.NumberColumn("ilvl", format="%.0f"),
                    },
                )
                st.markdown('</div>', unsafe_allow_html=True)

            with tab_boss:
                boss_summary = (
                    df_f.groupby(["Boss", "Player", "Class", "Spec"])
                    .agg(
                        **{
                            "Avg Parse": ("Parse %", "mean"),
                            "Best": ("Parse %", "max"),
                            "Parses": ("Parse %", "count"),
                        }
                    )
                    .reset_index()
                )
                if boss_summary.empty:
                    st.info("Brak danych bossów dla tych filtrów.")
                else:
                    pivot = boss_summary.pivot_table(
                        index="Player",
                        columns="Boss",
                        values="Avg Parse",
                        aggfunc="mean",
                    )
                    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]
                    fig = go.Figure(data=go.Heatmap(
                        z=pivot.values,
                        x=pivot.columns,
                        y=pivot.index,
                        zmin=0,
                        zmax=100,
                        colorscale=[
                            [0.0, "#3a2020"],
                            [0.5, "#1d4773"],
                            [0.75, "#5f2d84"],
                            [0.95, "#8a4f08"],
                            [1.0, "#b56c0a"],
                        ],
                        colorbar=dict(title="Avg"),
                        hovertemplate="<b>%{y}</b><br>%{x}<br>Avg parse: %{z:.0f}<extra></extra>",
                    ))
                    fig.update_layout(
                        height=max(380, len(pivot) * 24),
                        margin=dict(l=8, r=8, t=10, b=80),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font_color=clr["text"],
                        xaxis=dict(tickangle=-30),
                    )
                    st.markdown('<div class="pcard"><div class="chart-hdr">Heatmapa bossów</div>', unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown('<div class="pcard"><div class="chart-hdr">Tabela boss x player</div>', unsafe_allow_html=True)
                    st.dataframe(
                        boss_summary.sort_values(["Boss", "Avg Parse"], ascending=[True, False]),
                        hide_index=True,
                        width="stretch",
                        height=460,
                        column_config={
                            "Avg Parse": st.column_config.ProgressColumn("Avg", min_value=0, max_value=100, format="%.0f"),
                            "Best": st.column_config.NumberColumn(format="%.0f"),
                        },
                    )
                    st.markdown('</div>', unsafe_allow_html=True)

            with tab_player:
                players = summary["Player"].tolist()
                selected_player = st.selectbox("Gracz", players, index=0, key="parsy_player_detail")
                if selected_player:
                    player_rows = df_f[df_f["Player"] == selected_player].sort_values("Date")
                    player_summary = summary[summary["Player"] == selected_player].iloc[0]
                    pc1, pc2, pc3, pc4 = st.columns(4)
                    player_kpis = [
                        ("Avg", f"{player_summary['Avg Parse']:.0f}", "średni parse"),
                        ("Best", f"{player_summary['Best']:.0f}", "najlepszy wynik"),
                        ("Latest", f"{player_summary['Latest']:.0f}", "ostatni wpis"),
                        ("Trend", _fmt_signed(player_summary["Trend"]), "ostatnie 2 wpisy"),
                    ]
                    for col, (label, value, sub) in zip((pc1, pc2, pc3, pc4), player_kpis):
                        col.markdown(
                            f'<div class="parse-kpi"><div class="label">{label}</div>'
                            f'<div class="value">{value}</div><div class="sub">{sub}</div></div>',
                            unsafe_allow_html=True,
                        )

                    st.markdown('<div class="pcard"><div class="chart-hdr">Trend gracza</div>', unsafe_allow_html=True)
                    y_cols = [("Parse %", "Parse", None)]
                    if "ilvl Parse %" in player_rows.columns and player_rows["ilvl Parse %"].gt(0).any():
                        y_cols.append(("ilvl Parse %", "ilvl Parse", clr["gold_light"]))
                    st.plotly_chart(_line_chart(player_rows, selected_player, y_cols), use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                    by_boss = (
                        player_rows.groupby("Boss")
                        .agg(
                            **{
                                "Avg Parse": ("Parse %", "mean"),
                                "Best": ("Parse %", "max"),
                                "Worst": ("Parse %", "min"),
                                "Parses": ("Parse %", "count"),
                            }
                        )
                        .reset_index()
                        .sort_values("Avg Parse", ascending=False)
                    )
                    st.markdown('<div class="pcard"><div class="chart-hdr">Bossy gracza</div>', unsafe_allow_html=True)
                    st.dataframe(
                        by_boss,
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "Avg Parse": st.column_config.ProgressColumn("Avg", min_value=0, max_value=100, format="%.0f"),
                            "Best": st.column_config.NumberColumn(format="%.0f"),
                            "Worst": st.column_config.NumberColumn(format="%.0f"),
                        },
                    )
                    st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(f"Cache: `{CACHE_DIR.absolute()}` • Dane z Warcraft Logs API v2")
