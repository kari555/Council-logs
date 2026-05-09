"""
Council Raid Dashboard — Streamlit app.
Reads from local JSON cache built by fetch.py.

Run:
    streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Council Raid Dashboard",
    page_icon="⚔️",
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

THEME_LABELS = {
    "gold": "Council",
    "alliance": "Alliance",
    "horde": "Horde",
}


def c() -> dict[str, str]:
    return THEMES.get(st.session_state.get("theme", "gold"), THEMES["gold"])


def sync_query_params() -> None:
    st.query_params["page"] = st.session_state.current_page
    st.query_params["theme"] = st.session_state.theme


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
    bg_position = clr.get("bg_position", "right 2vw center")
    if st.session_state.get("current_page") != "walki" and st.session_state.get("theme") in {"alliance", "horde"}:
        bg_position = "center center"
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
    font-size: 13px;
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
    opacity: {clr.get("bg_opacity", "0")};
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
    max-width: 1400px;
}}

/* ── Sidebar ───────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {clr["bg2"]} 0%, {clr["bg"]} 100%) !important;
    border-right: 1px solid var(--border) !important;
}}
[data-testid="stSidebar"] hr {{
    border-color: var(--border) !important;
    margin: 0.5rem 0;
}}
[data-testid="stSidebar"] p {{
    color: var(--text-dim) !important;
    font-size: 10px !important;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    font-weight: 600;
}}
[data-testid="stSidebar"] h1 {{
    color: var(--gold) !important;
    text-shadow: 0 0 20px rgba(200,155,60,0.4);
    font-size: 1rem !important;
    letter-spacing: 0.5px;
}}

/* ── Selectbox ─────────────────────────────────────────────────────────── */
[data-baseweb="select"] > div:first-child {{
    background-color: var(--bg3) !important;
    border-color: var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    font-size: 12px !important;
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
    font-size: 12px !important;
}}
[role="option"]:hover {{
    background: var(--bg2) !important;
}}

/* ── Tabs ──────────────────────────────────────────────────────────────── */
[data-baseweb="tab-list"] {{
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
}}
[data-baseweb="tab"] {{
    color: var(--text-dim) !important;
    background: transparent !important;
    border-bottom: 2px solid transparent !important;
    padding: 8px 16px !important;
    font-size: 0.82rem !important;
    font-weight: 500;
    transition: color 0.15s;
    white-space: nowrap;
}}
[data-baseweb="tab"]:hover {{
    color: var(--text) !important;
    background: transparent !important;
}}
[aria-selected="true"] {{
    color: var(--gold) !important;
    border-bottom: 2px solid var(--gold) !important;
    background: transparent !important;
    font-weight: 600 !important;
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
    font-size: 0.65rem !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}}

/* ── Multiselect ───────────────────────────────────────────────────────── */
[data-baseweb="tag"] {{
    background: rgba(200,155,60,0.15) !important;
    border: 1px solid var(--gold-dim) !important;
    color: var(--gold) !important;
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
    box-shadow: 0 24px 80px rgba(0,0,0,0.8), 0 0 40px rgba(200,155,60,0.1) !important;
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
    font-size: 0.68rem !important;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}}

/* ── KPI topbar (custom HTML elements) ────────────────────────────────── */
.topbar-boss {{
    font-size: 22px;
    font-weight: 700;
    color: var(--gold);
    text-shadow: 0 0 30px rgba(200,155,60,0.3);
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    padding-bottom: 0;
}}
.result-kill {{
    background: #1a3d25;
    color: #4ade80;
    border: 1px solid #2d6040;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}
.result-wipe {{
    background: #3d1a1a;
    color: #f87171;
    border: 1px solid #6b2828;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 700;
}}
.kpi-row {{
    display: flex;
    gap: 28px;
    padding: 12px 0 14px;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    margin-bottom: 4px;
}}
.kpi {{ display: flex; flex-direction: column; }}
.kpi-label {{
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-dim);
    margin-bottom: 2px;
}}
.kpi-value {{
    font-size: 20px;
    font-weight: 700;
    color: var(--text);
    font-variant-numeric: tabular-nums;
}}
.kpi-value.gold  {{ color: var(--gold); }}
.kpi-value.red   {{ color: var(--red); }}
.kpi-value.green {{ color: var(--green); }}
.kpi-value.dim   {{ font-size: 13px; color: var(--text-dim); }}

.click-hint {{
    font-size: 11px;
    color: var(--text-dim);
    padding: 8px 0 4px;
    opacity: 0.7;
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


@st.cache_data
def load_index() -> list:
    p = CACHE_DIR / "reports_index.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


@st.cache_data
def load_fight(report_code: str, fight_id: int) -> dict | None:
    p = CACHE_DIR / f"fight_{report_code}_{fight_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


@st.cache_data
def load_parses_index() -> pd.DataFrame:
    p = CACHE_DIR / "parses_index.json"
    if not p.exists():
        return pd.DataFrame()
    rows = json.loads(p.read_text(encoding="utf-8"))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


@st.cache_data
def load_attendance() -> pd.DataFrame:
    p = CACHE_DIR / "attendance.json"
    if not p.exists():
        return pd.DataFrame()
    rows = json.loads(p.read_text(encoding="utf-8"))
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


@st.cache_data
def load_player_fight_rows() -> pd.DataFrame:
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


@st.cache_data
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
        return f"✅ Pull #{f['pull']} — Kill ({dur})"
    hp = f["boss_hp"]
    hp_str = f"{hp:.1f}%" if hp is not None else "?"
    return f"❌ Pull #{f['pull']} — Wipe {hp_str} ({dur})"


def render_topbar(meta: dict, deaths_count: int) -> None:
    boss = meta["boss"]
    pull = meta["pull"]
    dur = fmt_duration(meta["duration_s"])
    is_kill = meta.get("kill", meta["result"] == "Kill")
    boss_hp = meta.get("boss_hp")

    if is_kill:
        badge = '<span class="result-kill">KILL</span>'
        hp_class, hp_val = "green", "0.0%"
    else:
        hp_str = f"{boss_hp:.1f}%" if boss_hp is not None else "?"
        badge = f'<span class="result-wipe">WIPE {hp_str}</span>'
        hp_class = "red"
        hp_val = hp_str if boss_hp is not None else "?"

    report_short = meta["report"][:8] + "…"

    st.markdown(f"""
<div class="topbar-boss">
    <span>⚔️ {boss}</span>
    {badge}
</div>
<div class="kpi-row">
    <div class="kpi">
        <div class="kpi-label">Pull</div>
        <div class="kpi-value gold">#{pull}</div>
    </div>
    <div class="kpi">
        <div class="kpi-label">Czas walki</div>
        <div class="kpi-value">{dur}</div>
    </div>
    <div class="kpi">
        <div class="kpi-label">Boss HP</div>
        <div class="kpi-value {hp_class}">{hp_val}</div>
    </div>
    <div class="kpi">
        <div class="kpi-label">Zgony</div>
        <div class="kpi-value">{deaths_count}</div>
    </div>
    <div class="kpi">
        <div class="kpi-label">Raport</div>
        <div class="kpi-value dim">{report_short}</div>
    </div>
</div>
<div class="click-hint">💡 Kliknij gracza na wykresie aby otworzyć jego profil</div>
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
        st.caption("📍 Timeline")

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
        st.caption("🛡️ Defensives")
        if not p_def.empty:
            disp = [col for col in ["Ability", "Count"] if col in p_def.columns]
            st.dataframe(p_def[disp].sort_values("Count", ascending=False),
                         hide_index=True, use_container_width=True)
        else:
            st.info("Brak danych.")

    with col_c:
        st.caption("🧪 Consumables")
        if not p_cons.empty and cat_cols:
            st.dataframe(p_cons[cat_cols], hide_index=True, use_container_width=True)
        else:
            st.info("Brak danych.")

    if not p_dead.empty:
        st.caption("💀 Zgony")
        disp = [col for col in ["Death Time", "Killing Blow"] if col in p_dead.columns]
        st.dataframe(p_dead[disp], hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Player profile dialog
# ---------------------------------------------------------------------------
@st.dialog("👤 Profil gracza", width="large")
def player_profile_dialog(index: list, player_name: str):
    st.subheader(player_name)

    dates = unique_dates(index)
    dc1, dc2, dc3, dc4 = st.columns([2, 3, 2, 3])

    _d = st.session_state.get("dlg_date_sel",
                               st.session_state.get("dlg_date", dates[0]))
    _d_idx = dates.index(_d) if _d in dates else 0
    with dc1:
        dlg_date = st.selectbox("📅 Noc", dates, index=_d_idx, key="dlg_date_sel")

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
        dlg_boss = st.selectbox("👹 Boss", boss_names, index=_b_idx, key="dlg_boss_sel")

    boss_fights = sorted(
        [f for f in night["fights"] if f["boss"] == dlg_boss],
        key=lambda f: f["pull"],
    )
    _p = min(st.session_state.get("dlg_pull_sel",
                                   st.session_state.get("dlg_pull_idx", 0)),
             len(boss_fights) - 1)
    with dc4:
        dlg_pull = st.selectbox("🗡️ Pull", range(len(boss_fights)),
                                 format_func=lambda i: pull_label(boss_fights[i]),
                                 index=_p, key="dlg_pull_sel")

    st.divider()

    fight_data = load_fight(night["report_code"], boss_fights[dlg_pull]["fight_id"])
    if fight_data is None:
        st.error("Brak danych dla tego fightu w cache.")
        return

    render_player_profile(fight_data, player_name)


# ---------------------------------------------------------------------------
# Page navigation
# ---------------------------------------------------------------------------
PAGES = [
    ("walki",      "⚔️ Walki"),
    ("attendance", "📅 Attendance"),
    ("gracze", "👤 Gracze"),
    ("parsy",      "📈 Parsy"),
]


def render_nav_bar() -> None:
    clr = c()
    current = st.session_state.current_page
    theme = st.session_state.theme

    items_html = ""
    for key, label in PAGES:
        active = ' class="nav-active"' if key == current else ""
        player_param = ""
        if key == "gracze" and current == "gracze" and st.query_params.get("player"):
            player_param = f'&player={quote(str(st.query_params.get("player")))}'
        items_html += f'<a href="?page={key}&theme={theme}{player_param}" target="_self"{active}>{label}</a>'

    theme_html = ""
    for key, label in THEME_LABELS.items():
        active = " theme-active" if key == theme else ""
        player_param = ""
        if current == "gracze" and st.query_params.get("player"):
            player_param = f'&player={quote(str(st.query_params.get("player")))}'
        theme_html += (
            f'<a class="theme-pill{active}" href="?page={current}&theme={key}{player_param}" '
            f'target="_self">{label}</a>'
        )

    st.markdown(f"""
<style>
#prz-nav {{
    position: fixed !important;
    top: 0 !important; left: 0 !important; right: 0 !important;
    height: 48px !important;
    display: flex !important; align-items: stretch !important;
    background: linear-gradient(180deg, #1c1f2b 0%, {clr["bg2"]} 100%) !important;
    border-bottom: 1px solid {clr["border"]} !important;
    z-index: 999999 !important;
    font-family: "Source Sans Pro", "Segoe UI", system-ui, sans-serif;
    box-sizing: border-box;
}}
#prz-nav .nav-logo {{
    display: flex; align-items: center;
    padding: 0 20px; border-right: 1px solid {clr["border"]};
    font-weight: 700; font-size: 14px;
    color: {clr["gold"]}; white-space: nowrap; flex-shrink: 0;
}}
#prz-nav a {{
    display: flex; align-items: center; justify-content: center;
    padding: 0 28px; font-size: 12.5px; font-weight: 500;
    color: {clr["text_dim"]}; text-decoration: none;
    border-bottom: 2px solid transparent;
    transition: color 0.15s, border-color 0.15s;
    white-space: nowrap;
}}
#prz-nav a:hover {{ color: {clr["text"]}; border-bottom-color: {clr["border"]}; }}
#prz-nav a.nav-active {{
    color: {clr["gold"]} !important;
    border-bottom-color: {clr["gold"]} !important;
    font-weight: 700 !important;
}}
.theme-switcher {{
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 0 14px;
    border-left: 1px solid {clr["border"]};
}}
#prz-nav .theme-switcher a.theme-pill {{
    height: 28px;
    padding: 0 10px;
    border: 1px solid transparent;
    border-radius: 5px;
    color: {clr["text_dim"]};
    font-size: 11.5px;
    font-weight: 700;
    line-height: 26px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
#prz-nav .theme-switcher a.theme-pill:hover {{
    color: {clr["text"]} !important;
    border-color: {clr["border"]};
    background: {clr["bg3"]};
}}
#prz-nav .theme-switcher a.theme-active {{
    color: {clr["gold"]} !important;
    border-color: {clr["gold_dim"]};
    background: color-mix(in srgb, {clr["gold"]} 14%, transparent);
}}
.main .block-container {{ padding-top: 60px !important; }}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 60px !important; }}
</style>
<div id="prz-nav">
    <div class="nav-logo">⚔️ Council</div>
    {items_html}
    <div class="theme-switcher">{theme_html}</div>
</div>
""", unsafe_allow_html=True)


def render_theme_picker() -> None:
    return None


def _secret_value(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def refresh_wcl_cache(reports: int = 20, force: bool = False) -> None:
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
            wcl, code, consumable_config, defensive_config, force=force
        )
        update_index(code, report_info, fights_meta)
    fetch_attendance(wcl)


def render_admin_panel() -> None:
    admin_password = _secret_value("ADMIN_PASSWORD")
    with st.expander("Admin"):
        if not admin_password:
            st.caption("Ustaw `ADMIN_PASSWORD` w Streamlit Secrets, żeby włączyć odświeżanie danych.")
            return

        password = st.text_input("Hasło admina", type="password", key="admin_password")
        if password != admin_password:
            st.caption("Panel odświeżania pojawi się po wpisaniu hasła.")
            return

        col_a, col_b, col_c = st.columns([1, 1, 2])
        reports = col_a.number_input("Raporty", min_value=1, max_value=50, value=20, step=1)
        force = col_b.checkbox("Force", value=False)
        if col_c.button("Odśwież dane z WCL", type="primary"):
            with st.spinner("Pobieram dane z Warcraft Logs. To może potrwać kilka minut..."):
                try:
                    refresh_wcl_cache(reports=int(reports), force=force)
                    st.cache_data.clear()
                    st.success("Dane odświeżone. Przeładowuję widok.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Nie udało się odświeżyć danych: {exc}")


def render_pull_list(boss_fights: list, boss_name: str) -> int:
    """Sidebar pull selector as a radio list. Returns selected index."""
    return st.sidebar.radio(
        "🗡️ Pull",
        range(len(boss_fights)),
        format_func=lambda i: pull_label(boss_fights[i]),
        key=f"pull_radio_{boss_name}",
    )


# ---------------------------------------------------------------------------
# Sync URL query param → session state (enables <a href> nav links)
# ---------------------------------------------------------------------------
_valid_pages = {k for k, _ in PAGES}
_page_param = st.query_params.get("page", "walki")
if _page_param in _valid_pages and _page_param != st.session_state.current_page:
    st.session_state.current_page = _page_param
_theme_param = st.query_params.get("theme", st.session_state.theme)
if _theme_param in THEMES and _theme_param != st.session_state.theme:
    st.session_state.theme = _theme_param
elif st.query_params.get("theme") not in THEMES:
    st.query_params["theme"] = st.session_state.theme
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
render_theme_picker()
render_admin_panel()

index = load_index()

if not index:
    st.markdown(f"<h1 style='color:{c()['gold']}'>Brak danych</h1>", unsafe_allow_html=True)
    st.info("Uruchom najpierw skrypt pobierający:\n\n```\npython fetch.py\n```")
    st.stop()

# ---------------------------------------------------------------------------
# Hide sidebar on non-walki pages
# ---------------------------------------------------------------------------
if st.session_state.current_page != "walki":
    st.markdown("""<style>
[data-testid="stSidebar"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
.main .block-container { padding-left: 2rem !important; max-width: 100% !important; }
</style>""", unsafe_allow_html=True)

# ===========================================================================
# PAGE: walki
# ===========================================================================
if st.session_state.current_page == "walki":

    st.sidebar.title("⚔️ Council")
    st.sidebar.caption("Raid Dashboard")

    dates = unique_dates(index)
    selected_date = st.sidebar.selectbox("📅 Noc raidowa", dates)
    reports = reports_for_date(index, selected_date)
    if len(reports) > 1:
        selected_report_code = st.sidebar.selectbox(
            "📄 Raport / grupa",
            [r["report_code"] for r in reports],
            format_func=lambda code: report_label(next(r for r in reports if r["report_code"] == code)),
        )
        night = next(e for e in reports if e["report_code"] == selected_report_code)
    else:
        night = reports[0]

    boss_names = sorted(set(f["boss"] for f in night["fights"]))
    selected_boss = st.sidebar.selectbox("👹 Boss", boss_names)

    boss_fights = sorted(
        [f for f in night["fights"] if f["boss"] == selected_boss],
        key=lambda f: f["pull"],
    )
    selected_pull_idx = render_pull_list(boss_fights, selected_boss)
    selected_fight_meta = boss_fights[selected_pull_idx]

    fight_data = load_fight(night["report_code"], selected_fight_meta["fight_id"])
    if fight_data is None:
        st.error(f"Brak danych dla tego fightu. Uruchom `python fetch.py --code {night['report_code']}`")
        st.stop()

    meta = fight_data["meta"]

    # ── Header ───────────────────────────────────────────────────────────
    deaths_count = len(fight_data.get("deaths", []))
    render_topbar(meta, deaths_count)

    # ── Tabs (7 — Attendance i Parsy przeniesione na osobne strony) ───────
    (tab_perf, tab_timeline, tab_deaths,
     tab_interrupts, tab_dispels, tab_consumables, tab_defensives) = st.tabs([
        "📊 Performance", "⏱️ Timeline", "💀 Deaths",
        "⚡ Interrupts", "🧹 Dispels", "🧪 Consumables", "🛡️ Defensives",
    ])


    # ── Performance ──────────────────────────────────────────────────────
    with tab_perf:
        df_perf = pd.DataFrame(fight_data["performance"])
        if df_perf.empty:
            st.info("Brak danych.")
        else:
            col_dps, col_hps = st.columns(2)
            for col_ui, data_type, label in [
                (col_dps, "DPS", "⚔️ DPS"),
                (col_hps, "HPS", "💚 HPS"),
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
.att-header {{
    border-bottom: 1px solid {clr["border"]};
    padding-bottom: 10px; margin-bottom: 18px;
}}
.att-header h2 {{
    color: {clr["gold"]}; margin: 0 0 2px; font-size: 1.4rem;
}}
.att-header p {{ color: {clr["text_dim"]}; font-size: 0.78rem; margin: 0; }}
.stat-cards {{ display: flex; gap: 12px; margin-bottom: 20px; }}
.stat-card {{
    flex: 1; background: {clr["bg2"]};
    border: 1px solid {clr["border"]}; border-radius: 6px;
    padding: 14px 18px;
}}
.stat-card .sc-label {{
    font-size: 10px; text-transform: uppercase; letter-spacing: 1px;
    color: {clr["text_dim"]}; margin-bottom: 6px;
}}
.stat-card .sc-value {{
    font-size: 1.6rem; font-weight: 700; color: {clr["gold"]}; line-height: 1;
}}
.sc-green {{ color: {clr["green"]} !important; }}
.hm-wrap {{
    background: {clr["bg2"]}; border: 1px solid {clr["border"]};
    border-radius: 6px; overflow: hidden; margin-bottom: 20px;
}}
.hm-header {{
    padding: 10px 14px; border-bottom: 1px solid {clr["border"]};
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1px; color: {clr["text_dim"]};
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
        gap: 10px; margin-bottom: 16px;
    }}
    .session-card {{
        background: {clr["bg2"]}; border: 1px solid {clr["border"]};
        border-radius: 6px; padding: 12px 14px;
    }}
    .session-card.active {{ border-color: {clr["gold_dim"]}; }}
    .session-card .date {{ color: {clr["gold"]}; font-weight: 700; font-size: 13px; }}
    .session-card .code {{ color: {clr["text_dim"]}; font-size: 11px; margin-top: 2px; }}
    .session-card .count {{ color: {clr["text"]}; font-size: 20px; font-weight: 800; margin-top: 8px; }}
    .session-card .guests {{ color: {clr["red"]}; font-size: 12px; font-weight: 700; margin-top: 4px; }}
    .mini-roster {{
        display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 6px; margin-top: 8px;
    }}
    .roster-pill {{
        background: {clr["bg3"]}; border: 1px solid {clr["border"]};
        border-radius: 4px; padding: 6px 8px; font-size: 12px;
        display: flex; justify-content: space-between; gap: 8px;
    }}
    .roster-pill .cls {{ color: {clr["text_dim"]}; font-size: 10px; }}
    .compact-matrix {{
        display: grid; grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
        gap: 6px;
    }}
    .player-strip {{
        background: {clr["bg2"]}; border: 1px solid {clr["border"]};
        border-radius: 4px; padding: 7px 8px;
    }}
    .player-strip .name {{
        font-size: 12px; font-weight: 700; overflow: hidden;
        white-space: nowrap; text-overflow: ellipsis;
    }}
    .player-strip .dots {{ display: flex; gap: 3px; margin-top: 6px; }}
    .dot {{ width: 11px; height: 11px; border-radius: 2px; }}
    .dot.on {{ background: {clr["gold"]}; border: 1px solid {clr["gold_light"]}; }}
    .dot.off {{ background: #1a1d26; border: 1px solid {clr["border"]}; }}
    .att-wrap {{
        background: {clr["bg2"]}; border: 1px solid {clr["border"]};
        border-radius: 6px; overflow: hidden;
}}
.att-tbl {{ width: 100%; border-collapse: collapse; font-size: 12px; table-layout: fixed; }}
.att-tbl thead {{ position: sticky; top: 0; z-index: 1; background: {clr["bg2"]}; }}
.att-tbl th {{
    padding: 9px 14px; text-align: left;
    font-size: 10px; text-transform: uppercase; letter-spacing: 1px;
    color: {clr["text_dim"]}; border-bottom: 1px solid {clr["border"]};
}}
.att-tbl td {{ padding: 9px 14px; border-bottom: 1px solid {clr["border"]}33; }}
.att-tbl tr:hover td {{ background: {clr["bg3"]}; }}
.att-pct {{ font-weight: 700; }}
.pct-high {{ color: {clr["green"]}; }}
.pct-mid  {{ color: {clr["gold"]}; }}
.pct-low  {{ color: {clr["red"]}; }}
</style>
<div class="att-header">
  <h2>📅 Attendance</h2>
  <p>Frekwencja — dane z całej historii raidów gildi</p>
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
<div class="hm-wrap">
  <div class="hm-header">Kompaktowa mapa obecności</div>
  <div style="padding:14px">
    <div class="compact-matrix">{compact_html}</div>
  </div>
</div>
""", unsafe_allow_html=True)

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
  <div class="hm-header">📊 Podsumowanie graczy</div>
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
.players-header {{ margin-bottom: 18px; }}
.players-header .page-title {{
    font-size: 22px; font-weight: 800; color:{clr["gold"]};
    margin-bottom: 4px;
}}
.players-header .page-subtitle {{ color:{clr["text_dim"]}; font-size:12px; }}
.players-shell {{
    display: grid; grid-template-columns: 300px minmax(0, 1fr);
    gap: 14px; align-items: start;
}}
.players-side, .players-card {{
    background:{clr["bg2"]}; border:1px solid {clr["border"]};
    border-radius:6px; padding:14px 16px; margin-bottom:14px;
}}
.players-side {{ position: sticky; top: 62px; max-height: calc(100vh - 78px); overflow-y: auto; }}
.player-side-title {{
    font-size:11px; text-transform:uppercase; letter-spacing:1px;
    color:{clr["text_dim"]}; font-weight:800; margin-bottom:8px;
}}
.player-identity {{
    display:flex; align-items:center; justify-content:space-between; gap:12px;
    border-bottom:1px solid {clr["border"]}; padding-bottom:12px; margin-bottom:12px;
}}
.player-name {{ font-size:24px; color:{clr["text"]}; font-weight:900; }}
.player-sub {{ color:{clr["text_dim"]}; font-size:12px; margin-top:3px; }}
.players-kpis {{ display:grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap:10px; margin-bottom:14px; }}
.player-kpi {{
    background:{clr["bg2"]}; border:1px solid {clr["border"]}; border-radius:6px;
    padding:12px 14px; min-height:76px;
}}
.player-kpi .label {{
    color:{clr["text_dim"]}; font-size:10px; font-weight:800;
    letter-spacing:1px; text-transform:uppercase;
}}
.player-kpi .value {{ color:{clr["gold"]}; font-size:23px; font-weight:900; margin-top:5px; }}
.player-kpi .sub {{ color:{clr["text_dim"]}; font-size:11px; margin-top:2px; }}
.players-card .chart-hdr {{
    color:{clr["text_dim"]}; font-size:11px; font-weight:800;
    text-transform:uppercase; letter-spacing:1px; margin-bottom:10px;
}}
.players-note {{
    color:{clr["text_dim"]}; font-size:12px;
    border:1px solid {clr["border"]}; background:{clr["bg3"]};
    border-radius:6px; padding:10px 12px; margin-bottom:14px;
}}
@media (max-width: 1100px) {{
    .players-shell {{ grid-template-columns: 1fr; }}
    .players-side {{ position: static; max-height:none; }}
    .players-kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}
</style>
<div class="players-header">
  <div class="page-title">👤 Gracze</div>
  <div class="page-subtitle">Profil gracza: trendy, parse’y, output, attendance i sygnały do sprawdzenia</div>
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
        left, right = st.columns([0.26, 0.74], gap="large")

        with left:
            st.markdown('<div class="players-side">', unsafe_allow_html=True)
            st.markdown('<div class="player-side-title">Lista graczy</div>', unsafe_allow_html=True)
            search = st.text_input("Szukaj", value="", key="players_search")
            date_mode = st.selectbox(
                "Zakres",
                ["Ostatnie 30 dni", "Ostatnia noc", "Cała historia"],
                index=0,
                key="players_date_mode",
            )
            if not st.session_state.get("players_defaults_v2_applied") and st.session_state.get("players_fight_type", "Wszystkie") == "Wszystkie":
                st.session_state.players_fight_type = "Kille"
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
                st.markdown("</div>", unsafe_allow_html=True)
                st.stop()
            players_summary["Spec"] = players_summary["Spec"].fillna("")
            players_summary["Class"] = players_summary["Class"].fillna("")

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
                st.markdown("</div>", unsafe_allow_html=True)
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
            st.markdown("</div>", unsafe_allow_html=True)

        with right:
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
  <div class="player-sub">{date_mode} · {fight_filter} · {boss_filter}</div>
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

            if meta["role"] == "Healers" or metric == "HPS":
                st.markdown('<div class="players-note">Healerzy są oceniani głównie po HPS oraz healing parse, nie po Damage Done.</div>', unsafe_allow_html=True)

            t1, t2 = st.columns(2)
            with t1:
                st.markdown('<div class="players-card"><div class="chart-hdr">Trend parse / ilvl parse</div>', unsafe_allow_html=True)
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
                st.markdown(f'<div class="players-card"><div class="chart-hdr">Trend {metric} po pullach</div>', unsafe_allow_html=True)
                if p_fights.empty:
                    st.info("Brak pulli dla aktualnych filtrów.")
                else:
                    st.plotly_chart(_player_line_chart(p_fights, [(metric, metric, clr["green"])], metric), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            c_left, c_right = st.columns([1.15, 0.85])
            with c_left:
                st.markdown('<div class="players-card"><div class="chart-hdr">Boss breakdown</div>', unsafe_allow_html=True)
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
                st.markdown('<div class="players-card"><div class="chart-hdr">Problemy do sprawdzenia</div>', unsafe_allow_html=True)
                issues = profile["issues"]
                if issues.empty:
                    st.success("Brak mocnych sygnałów problemowych w aktualnym zakresie.")
                else:
                    issues_view = issues.copy()
                    if "Date" in issues_view.columns:
                        issues_view["Date"] = pd.to_datetime(issues_view["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
                    st.dataframe(issues_view, hide_index=True, width="stretch", height=380)
                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown('<div class="players-card"><div class="chart-hdr">Porównanie do roli / speca</div>', unsafe_allow_html=True)
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
    font-size: 22px; font-weight: 700; color:{clr["gold"]};
    margin-bottom: 4px; text-shadow: 0 0 30px rgba(200,155,60,0.2);
}}
.parsy-header .page-subtitle {{ color:{clr["text_dim"]}; font-size:12px; margin:0; }}
.parse-note {{
    color:{clr["text_dim"]}; font-size:12px; margin: -6px 0 14px;
}}
.chart-hdr {{
    font-size:11px; font-weight:700; text-transform:uppercase;
    letter-spacing:1px; color:{clr["text_dim"]};
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
    font-size:10px; color:{clr["text_dim"]}; text-transform:uppercase;
    letter-spacing:1px; font-weight:700;
}}
.parse-kpi .value {{
    font-size:25px; color:{clr["gold"]}; font-weight:800; margin-top:6px;
}}
.parse-kpi .sub {{ font-size:11px; color:{clr["text_dim"]}; margin-top:2px; }}
.parse-pct {{
    font-weight:700; padding:2px 7px; border-radius:3px;
    font-size:11px; display:inline-block; min-width:34px; text-align:center;
}}
.parse-legendary {{ background:#332200; color:#ff8000; border:1px solid #ff800040; }}
.parse-epic      {{ background:#1a0a2e; color:#a335ee; border:1px solid #a335ee40; }}
.parse-rare      {{ background:#001a33; color:#0070dd; border:1px solid #0070dd40; }}
.parse-common    {{ background:#1e2130; color:#9d9d9d; border:1px solid #9d9d9d40; }}
</style>
<div class="parsy-header">
  <div class="page-title">📈 Parsy</div>
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
