"""
data.py — Makroinvestor Web: datahentning, scoring og simulation
"""

import os, re
from datetime import datetime

import openpyxl

_DEFAULT_EXCEL = os.path.join(os.path.dirname(__file__), "data.xlsx")
EXCEL_PATH = os.environ.get("MAKRO_EXCEL", _DEFAULT_EXCEL)

# ── Konstanter ────────────────────────────────────────────────────────────────

KVARTALER_HIST = ["Q1 2024","Q2 2024","Q3 2024","Q4 2024",
                  "Q1 2025","Q2 2025","Q3 2025","Q4 2025"]
KVARTALER_PROJ = ["Q1 2026","Q2 2026"]
ALLE_KVARTALER = KVARTALER_HIST + KVARTALER_PROJ

# Optimeret indikatorliste — Baltic Dry og Currency fjernet (Asien-bias, ikke konjunkturel)
# Tilføjet: Yield Curve (10Y-2Y), NFP, Retail Sales, Wage Growth, Energy (olie YoY%)
# CPI → Core CPI (ex. food+energy) — mere pengepolitisk relevant
INDIKATORER = [
    "PMI", "Yield Curve", "Retail Sales", "NFP",
    "Core CPI", "BNP", "Wage Growth",
    "Energy", "10 YR", "VIX", "Unemployment",
]
INDIKATOR_VAEGTER = {
    "PMI": 3, "Yield Curve": 3,
    "Retail Sales": 2, "NFP": 2, "Core CPI": 2, "BNP": 2, "Wage Growth": 2,
    "Energy": 1, "10 YR": 1, "VIX": 1, "Unemployment": 1,
}
# Kategorisering: ledende vs. lagging (til UI-visning)
INDIKATOR_TYPE = {
    "PMI": "ledende", "Yield Curve": "ledende",
    "Retail Sales": "ledende", "NFP": "ledende",
    "Core CPI": "samtidig", "BNP": "lagging", "Wage Growth": "samtidig",
    "Energy": "ledende", "10 YR": "lagging", "VIX": "ledende", "Unemployment": "lagging",
}

SEKTOR_MAP = {
    "communications services":    "Communications Services",
    "communication services":     "Communications Services",
    "communications sercives":    "Communications Services",
    "communications\xa0services": "Communications Services",
    "consumer discretionary":     "Consumer Discretionary",
    "consumer\xa0discretionary":  "Consumer Discretionary",
    "information technology":     "Information Technology",
    "infomation technology":      "Information Technology",
    "real estate":                "Real Estate",
    "real\xa0estate":             "Real Estate",
    "health care":                "Health Care",
    "health\xa0care":             "Health Care",
    "consumer staples":           "Consumer Staples",
    "consumer\xa0staples":        "Consumer Staples",
    "financials":                 "Financials",
    "industrials":                "Industrials",
    "materials":                  "Materials",
    "energy":                     "Energy",
    "utilities":                  "Utilities",
}

SEKTOR_RÆKKEFØLGE = [
    "Information Technology","Communications Services","Industrials","Financials",
    "Consumer Discretionary","Energy","Health Care","Real Estate",
    "Consumer Staples","Materials","Utilities",
]

SEKTOR_IKONER = {
    "Information Technology":  "💻",
    "Communications Services": "📡",
    "Industrials":             "⚙️",
    "Financials":              "🏦",
    "Consumer Discretionary":  "🛍️",
    "Energy":                  "⚡",
    "Health Care":             "🏥",
    "Real Estate":             "🏗️",
    "Materials":               "🔩",
    "Utilities":               "💡",
    "Consumer Staples":        "🛒",
}

FASE_META = {
    "Early":     ("Tidlig opsving", "Økonomi i bedring. Bred opgang, cykliske sektorer outperformer.", "🌱", "#4ade80"),
    "Mid":       ("Midt-cyklus",    "Solid vækst, moderat inflation. Bred eksponering fordelagtig.",   "🚀", "#60a5fa"),
    "Late":      ("Sent cyklus",    "Stram pengepolitik, stigende inflation. Defensivt & energi.",     "🌇", "#facc15"),
    "Recession": ("Recession",      "Negativ vækst. Obligationer, guld og defensive sektorer.",        "⚠️", "#f87171"),
}

# Standard makro-inputs (Q2 2026 estimater) — kun Europa og USA
DEFAULT_MAKRO = {
    "Europa": {
        "PMI":          {"vaerdi": 52.3, "enhed": "",   "label": "PMI Eurozone Composite"},
        "Yield Curve":  {"vaerdi": 0.40, "enhed": "%",  "label": "Yield Curve (10Y-2Y)"},
        "Retail Sales": {"vaerdi": 0.2,  "enhed": "%",  "label": "Retail Sales (MoM %)"},
        "NFP":          {"vaerdi": 80.0, "enhed": "k",  "label": "Beskæftigelsesvækst (t/md)"},
        "Core CPI":     {"vaerdi": 2.1,  "enhed": "%",  "label": "Kerninflation (ex. energi/fødevarer)"},
        "BNP":          {"vaerdi": 1.3,  "enhed": "%",  "label": "BNP vækst (YoY %)"},
        "Wage Growth":  {"vaerdi": 3.0,  "enhed": "%",  "label": "Lønvækst (YoY %)"},
        "Energy":       {"vaerdi": 3.0,  "enhed": "%",  "label": "Energipriser olie (YoY %)"},
        "10 YR":        {"vaerdi": 2.95, "enhed": "%",  "label": "10-årig statsrente"},
        "VIX":          {"vaerdi": 17.0, "enhed": "",   "label": "VIX (volatilitetsindeks)"},
        "Unemployment": {"vaerdi": 6.2,  "enhed": "%",  "label": "Arbejdsløshed (%)"},
    },
    "USA": {
        "PMI":          {"vaerdi": 52.5, "enhed": "",   "label": "PMI Composite"},
        "Yield Curve":  {"vaerdi": 0.20, "enhed": "%",  "label": "Yield Curve (10Y-2Y)"},
        "Retail Sales": {"vaerdi": 0.3,  "enhed": "%",  "label": "Retail Sales (MoM %)"},
        "NFP":          {"vaerdi": 185,  "enhed": "k",  "label": "Non-Farm Payrolls (t/md)"},
        "Core CPI":     {"vaerdi": 2.8,  "enhed": "%",  "label": "Kerninflation (ex. energi/fødevarer)"},
        "BNP":          {"vaerdi": 1.8,  "enhed": "%",  "label": "BNP vækst (YoY %)"},
        "Wage Growth":  {"vaerdi": 4.1,  "enhed": "%",  "label": "Lønvækst / Avg. Hourly Earnings"},
        "Energy":       {"vaerdi": 3.0,  "enhed": "%",  "label": "Energipriser olie (YoY %)"},
        "10 YR":        {"vaerdi": 4.25, "enhed": "%",  "label": "10-årig Treasury rente"},
        "VIX":          {"vaerdi": 17.0, "enhed": "",   "label": "VIX (volatilitetsindeks)"},
        "Unemployment": {"vaerdi": 4.4,  "enhed": "%",  "label": "Arbejdsløshed (%)"},
    },
}

# ── Hjælpefunktioner ──────────────────────────────────────────────────────────

def norm(s):
    if not s:
        return ""
    return SEKTOR_MAP.get(str(s).strip().lower(), str(s).strip())

def indlaes_wb():
    return openpyxl.load_workbook(EXCEL_PATH, data_only=True)

# ── Faseklassificering ────────────────────────────────────────────────────────

def fase_pmi(v):
    """PMI Manufacturing/Composite — ledende, stærkeste enkelt-indikator."""
    if v is None: return None
    if v >= 54:   return "Mid"
    if v >= 50:   return "Early"
    if v >= 47:   return "Late"
    return "Recession"

def fase_yield_curve(v):
    """
    10Y-2Y spread i % — bedste recession-predictor (12-18 mdr. lead).
    Negativ kurve → Late/Recession. Stejl kurve → Early/Mid (CB har lettet).
    """
    if v is None: return None
    if v > 1.5:   return "Early"   # Meget stejl: CB har sænket aggressivt
    if v > 0.3:   return "Mid"     # Normal positiv hældning
    if v > -0.3:  return "Late"    # Flad til svagt inverteret
    return "Recession"             # Dybt inverteret

def fase_retail_sales(v):
    """Retail Sales MoM % — direkte mål for forbrugsdrevet vækst."""
    if v is None: return None
    if v < 0:     return "Recession"
    if v < 0.15:  return "Late"
    if v < 0.4:   return "Early"
    return "Mid"

def fase_nfp(v, region="USA"):
    """NFP/beskæftigelsesvækst i tusinde/md — region-justeret (USA og Europa)."""
    if v is None: return None
    if region == "USA":
        if v > 220:  return "Mid"
        if v > 100:  return "Early"
        if v > 30:   return "Late"
        return "Recession"
    else:  # Europa (Eurozone månedlig beskæftigelse)
        if v > 150:  return "Mid"
        if v > 50:   return "Early"
        if v > 0:    return "Late"
        return "Recession"

def fase_core_cpi(v):
    """
    Kerninflation (ex. fødevarer og energi) YoY %.
    Drivende for pengepolitik — mere stabil end headline CPI.
    """
    if v is None: return None
    if v < 1.5:   return "Recession"  # Deflationspres
    if v < 2.5:   return "Early"      # Under mål — ekspansiv pengepolitik
    if v < 3.5:   return "Mid"        # Kontrolleret inflation
    return "Late"                      # Over mål — stramning nødvendig

def fase_bnp(v):
    """BNP vækst YoY % — lagging, bekræfter fasen snarere end trigger."""
    if v is None: return None
    if v < 0:     return "Recession"
    if v < 1.0:   return "Early"
    if v < 2.5:   return "Mid"
    return "Late"

def fase_wage_growth(v):
    """
    Lønvækst YoY % (Avg. Hourly Earnings/tilsvarende).
    Høj lønvækst = Late-signal (inflationspres + margin squeeze).
    """
    if v is None: return None
    if v < 2.0:   return "Recession"
    if v < 3.5:   return "Early"
    if v < 4.5:   return "Mid"
    return "Late"

def fase_energy(v):
    """
    Oliepris YoY % (WTI/Brent). Kraftig stigning = stagflationsrisiko.
    Kollaps = Recession-signal (efterspørgselsdrevet fald).
    """
    if v is None: return None
    if v < -25:   return "Recession"
    if v < 10:    return "Early"
    if v < 35:    return "Mid"
    return "Late"

def fase_rente(v, region="USA"):
    """10-årig rente absolut niveau — lagging kontekst for yield curve."""
    if v is None: return None
    if region == "USA":
        if v < 3.0:   return "Early"
        if v < 4.0:   return "Mid"
        if v < 4.75:  return "Late"
        return "Recession"
    else:
        if v < 1.5:   return "Early"
        if v < 2.5:   return "Mid"
        if v < 3.5:   return "Late"
        return "Recession"

def fase_vix(v):
    """VIX — markedsbaseret risiko-sentiment. Høj VIX = Late/Recession."""
    if v is None: return None
    if v < 15:    return "Mid"
    if v < 20:    return "Early"
    if v < 30:    return "Late"
    return "Recession"

def fase_unemployment(v):
    """Arbejdsløshed % — lagging indikator, bekræftelse, ikke trigger."""
    if v is None: return None
    if v > 8:     return "Recession"
    if v > 6:     return "Late"
    if v > 4.5:   return "Mid"
    return "Early"

KLASSIFICERINGER = {
    "PMI":          fase_pmi,
    "Yield Curve":  fase_yield_curve,
    "Retail Sales": fase_retail_sales,
    "NFP":          fase_nfp,          # region-aware — kaldes separat i klassificer_makro
    "Core CPI":     fase_core_cpi,
    "BNP":          fase_bnp,
    "Wage Growth":  fase_wage_growth,
    "Energy":       fase_energy,
    "10 YR":        fase_rente,        # region-aware
    "VIX":          fase_vix,
    "Unemployment": fase_unemployment,
}

# ─────────────────────────────────────────────────────────────────────────────
# SEKTOR_SENSITIVITET — evidensbaseret sektorrotation per indikator per fase
# Scores 1-5: 5 = stærk outperformer, 1 = stærk underperformer
# Baltic Dry og Currency FJERNET (Asien-bias / ikke konjunkturel)
# ─────────────────────────────────────────────────────────────────────────────
SEKTOR_SENSITIVITET = {
    # ── PMI (ledende, vægt 3) ─────────────────────────────────────────────
    # Cykliske sektorer reagerer kraftigt på PMI-bevægelser
    "PMI": {
        "Financials":              {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Real Estate":             {"Early":4,"Mid":3,"Late":2,"Recession":1},
        "Consumer Discretionary":  {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Information Technology":  {"Early":3,"Mid":5,"Late":3,"Recession":1},  # IT topper i Mid
        "Industrials":             {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":4,"Mid":3,"Late":2,"Recession":2},
        "Consumer Staples":        {"Early":2,"Mid":2,"Late":4,"Recession":5},
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":5},
        "Energy":                  {"Early":2,"Mid":3,"Late":5,"Recession":1},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Utilities":               {"Early":2,"Mid":2,"Late":4,"Recession":5},
    },
    # ── Yield Curve 10Y-2Y (ledende, vægt 3) ─────────────────────────────
    # Stejl kurve = bankmargin stiger → Financials outperformer stærkt
    # Inverteret kurve = duration-aktiver (Utilities, Staples) outperformer relativt
    "Yield Curve": {
        "Financials":              {"Early":5,"Mid":4,"Late":2,"Recession":1},  # Netto rentemarginal
        "Real Estate":             {"Early":4,"Mid":3,"Late":1,"Recession":2},  # Refinansiering
        "Consumer Discretionary":  {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Information Technology":  {"Early":4,"Mid":5,"Late":2,"Recession":2},  # Duration-sensitiv
        "Industrials":             {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":4,"Mid":3,"Late":2,"Recession":2},
        "Consumer Staples":        {"Early":2,"Mid":2,"Late":4,"Recession":4},
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":4},
        "Energy":                  {"Early":3,"Mid":3,"Late":4,"Recession":2},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Utilities":               {"Early":2,"Mid":2,"Late":4,"Recession":5},  # Bond-proxy
    },
    # ── Retail Sales MoM% (ledende, vægt 2) ──────────────────────────────
    # Direkte forbrugsmål — Consumer Discretionary reagerer mest
    "Retail Sales": {
        "Financials":              {"Early":3,"Mid":4,"Late":2,"Recession":1},
        "Real Estate":             {"Early":3,"Mid":3,"Late":2,"Recession":1},
        "Consumer Discretionary":  {"Early":5,"Mid":5,"Late":2,"Recession":1},
        "Information Technology":  {"Early":4,"Mid":4,"Late":3,"Recession":1},
        "Industrials":             {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":3,"Mid":3,"Late":2,"Recession":2},
        "Consumer Staples":        {"Early":3,"Mid":3,"Late":4,"Recession":4},  # Recession-defensiv
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":4},
        "Energy":                  {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Utilities":               {"Early":2,"Mid":2,"Late":3,"Recession":4},
    },
    # ── NFP / Beskæftigelsesvækst (ledende, vægt 2) ───────────────────────
    # Jobvækst driver forbrug og forbrugertillid
    "NFP": {
        "Financials":              {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Real Estate":             {"Early":4,"Mid":3,"Late":2,"Recession":1},
        "Consumer Discretionary":  {"Early":5,"Mid":5,"Late":2,"Recession":1},
        "Information Technology":  {"Early":4,"Mid":4,"Late":3,"Recession":1},
        "Industrials":             {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":4,"Mid":3,"Late":2,"Recession":2},
        "Consumer Staples":        {"Early":2,"Mid":2,"Late":3,"Recession":5},
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":5},
        "Energy":                  {"Early":3,"Mid":3,"Late":4,"Recession":2},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Utilities":               {"Early":2,"Mid":2,"Late":3,"Recession":5},
    },
    # ── Core CPI (samtidig, vægt 2) ───────────────────────────────────────
    # Kerninflation driver pengepolitik. Høj core CPI = Late-fase stramning
    "Core CPI": {
        "Financials":              {"Early":4,"Mid":4,"Late":2,"Recession":2},
        "Real Estate":             {"Early":4,"Mid":3,"Late":1,"Recession":2},  # Renter slår RE hårdt
        "Consumer Discretionary":  {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Information Technology":  {"Early":4,"Mid":5,"Late":2,"Recession":1},  # Duration-effekt ved høj CPI
        "Industrials":             {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":3,"Mid":3,"Late":4,"Recession":2},  # Materialpriser stiger
        "Consumer Staples":        {"Early":2,"Mid":2,"Late":4,"Recession":5},
        "Health Care":             {"Early":3,"Mid":3,"Late":3,"Recession":4},
        "Energy":                  {"Early":2,"Mid":3,"Late":5,"Recession":1},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Utilities":               {"Early":2,"Mid":2,"Late":4,"Recession":5},
    },
    # ── BNP vækst (lagging, vægt 2) ───────────────────────────────────────
    "BNP": {
        "Financials":              {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Real Estate":             {"Early":4,"Mid":3,"Late":3,"Recession":1},
        "Consumer Discretionary":  {"Early":5,"Mid":4,"Late":1,"Recession":1},
        "Information Technology":  {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Industrials":             {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":4,"Mid":3,"Late":2,"Recession":2},
        "Consumer Staples":        {"Early":2,"Mid":2,"Late":4,"Recession":5},
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":5},
        "Energy":                  {"Early":2,"Mid":3,"Late":5,"Recession":1},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Utilities":               {"Early":2,"Mid":2,"Late":4,"Recession":5},
    },
    # ── Lønvækst (samtidig, vægt 2) ───────────────────────────────────────
    # Høj lønvækst gavner Consumer Disc. men presser marginer (Late-signal)
    "Wage Growth": {
        "Financials":              {"Early":3,"Mid":4,"Late":2,"Recession":1},
        "Real Estate":             {"Early":3,"Mid":3,"Late":2,"Recession":1},
        "Consumer Discretionary":  {"Early":4,"Mid":5,"Late":2,"Recession":1},  # Købekraft topper i Mid
        "Information Technology":  {"Early":4,"Mid":4,"Late":3,"Recession":1},
        "Industrials":             {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":3,"Mid":3,"Late":3,"Recession":2},
        "Consumer Staples":        {"Early":2,"Mid":2,"Late":3,"Recession":4},
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":4},
        "Energy":                  {"Early":3,"Mid":3,"Late":4,"Recession":2},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Utilities":               {"Early":2,"Mid":2,"Late":3,"Recession":4},
    },
    # ── Energipriser olie YoY% (ledende, vægt 1) ──────────────────────────
    # Kraftig oliestigning = stagflationsrisiko. Energy-sektor outperformer i Mid/Late
    "Energy": {
        "Financials":              {"Early":3,"Mid":3,"Late":2,"Recession":2},
        "Real Estate":             {"Early":3,"Mid":3,"Late":2,"Recession":2},
        "Consumer Discretionary":  {"Early":4,"Mid":3,"Late":1,"Recession":2},  # Energipris presser forbrug
        "Information Technology":  {"Early":3,"Mid":4,"Late":2,"Recession":2},
        "Industrials":             {"Early":4,"Mid":4,"Late":2,"Recession":2},
        "Materials":               {"Early":4,"Mid":4,"Late":3,"Recession":2},
        "Consumer Staples":        {"Early":2,"Mid":2,"Late":3,"Recession":4},
        "Health Care":             {"Early":3,"Mid":3,"Late":3,"Recession":4},
        "Energy":                  {"Early":4,"Mid":5,"Late":5,"Recession":1},  # Direkte priseksponering
        "Communications Services": {"Early":3,"Mid":3,"Late":2,"Recession":2},
        "Utilities":               {"Early":3,"Mid":3,"Late":4,"Recession":3},
    },
    # ── 10-årig rente absolut (lagging, vægt 1) ───────────────────────────
    "10 YR": {
        "Financials":              {"Early":5,"Mid":4,"Late":2,"Recession":2},
        "Real Estate":             {"Early":4,"Mid":3,"Late":1,"Recession":2},
        "Consumer Discretionary":  {"Early":4,"Mid":4,"Late":2,"Recession":2},
        "Information Technology":  {"Early":4,"Mid":5,"Late":2,"Recession":2},
        "Industrials":             {"Early":4,"Mid":4,"Late":2,"Recession":2},
        "Materials":               {"Early":3,"Mid":2,"Late":3,"Recession":2},
        "Consumer Staples":        {"Early":3,"Mid":3,"Late":4,"Recession":4},
        "Health Care":             {"Early":3,"Mid":3,"Late":3,"Recession":4},
        "Energy":                  {"Early":3,"Mid":3,"Late":5,"Recession":2},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Utilities":               {"Early":3,"Mid":3,"Late":4,"Recession":4},
    },
    # ── VIX (ledende, vægt 1) ─────────────────────────────────────────────
    "VIX": {
        "Financials":              {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Real Estate":             {"Early":4,"Mid":3,"Late":2,"Recession":1},
        "Consumer Discretionary":  {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Information Technology":  {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Industrials":             {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":4,"Mid":3,"Late":2,"Recession":2},
        "Consumer Staples":        {"Early":2,"Mid":3,"Late":4,"Recession":5},
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":5},
        "Energy":                  {"Early":2,"Mid":3,"Late":4,"Recession":2},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Utilities":               {"Early":2,"Mid":3,"Late":4,"Recession":5},
    },
    # ── Arbejdsløshed (lagging, vægt 1) ───────────────────────────────────
    "Unemployment": {
        "Financials":              {"Early":4,"Mid":3,"Late":2,"Recession":1},
        "Real Estate":             {"Early":4,"Mid":3,"Late":2,"Recession":1},
        "Consumer Discretionary":  {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Information Technology":  {"Early":4,"Mid":4,"Late":3,"Recession":1},
        "Industrials":             {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":4,"Mid":3,"Late":2,"Recession":2},
        "Consumer Staples":        {"Early":2,"Mid":2,"Late":3,"Recession":5},
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":5},
        "Energy":                  {"Early":2,"Mid":3,"Late":4,"Recession":2},
        "Communications Services": {"Early":3,"Mid":3,"Late":3,"Recession":2},
        "Utilities":               {"Early":2,"Mid":2,"Late":3,"Recession":5},
    },
}

# ── Excel-parsing ─────────────────────────────────────────────────────────────

def hent_makro_analyse(wb):
    """
    Læs Makro analyse-arket: per sektor per region (DK/EU/USA) for Q1+Q2 2026.
    Returnerer: {region: {sektor: {kvartal: {indikator: score, 'total': score}}}}
    """
    ws = wb["Makro analyse"]
    rows = list(ws.iter_rows(values_only=True))
    INDS = ["PMI","BNP","10 YR","CPI","Baltic Dry","VIX","Currency","Unemployment"]

    result = {}
    # DK: rækker 29-40 (0-indeks), EU: 69-80, USA: 109-120
    blokke = [("Europa", 69, 70, 81), ("USA", 109, 110, 121)]

    for region, hdr_idx, data_start, data_end in blokke:
        result[region] = {}
        for row in rows[data_start:data_end]:
            sektor = norm(row[1])
            if not sektor:
                continue
            # Q1 2026: cols 2-9 = indikatorer, col 10 = total
            # Q2 2026: cols 11-18 = indikatorer, col 19 = total
            q1_inds = {INDS[i]: row[2+i] for i in range(8) if isinstance(row[2+i], (int,float))}
            q1_total = row[10] if isinstance(row[10], (int,float)) else None
            q2_inds = {INDS[i]: row[11+i] for i in range(8) if isinstance(row[11+i], (int,float))}
            q2_total = row[19] if isinstance(row[19], (int,float)) else None

            result[region][sektor] = {
                "Q1 2026": {**q1_inds, "total": q1_total},
                "Q2 2026": {**q2_inds, "total": q2_total},
            }
    return result


def hent_historisk_bnp(wb):
    """
    Læs historiske BNP-baserede scores Q1 2024–Q4 2025.
    Returnerer: {sektor: {kvartal: {region: score}}}
    """
    ws = wb["BNP"]
    rows = list(ws.iter_rows(values_only=True))
    result = {}
    cur_sektor = None
    kv_cols = None

    for row in rows[81:]:
        if row[1] and isinstance(row[2], str) and row[2].startswith("Q"):
            cur_sektor = norm(str(row[1]))
            kv_cols = [row[i] for i in range(2, 10) if row[i] is not None]
            result.setdefault(cur_sektor, {kv: {} for kv in KVARTALER_HIST})
        elif cur_sektor and row[1] in ("Europa ","USA","Europa"):
            region = row[1].strip()
            for i, kv in enumerate(KVARTALER_HIST):
                val = row[2+i] if len(row) > 2+i else None
                if isinstance(val, (int,float)):
                    result[cur_sektor][kv][region] = val
    return result


def hent_ranglister(wb):
    """Q1+Q2 2026 makroscorer fra Ranglisten DK/EU/USA."""
    dk, eu, usa = {}, {}, {}

    ws = wb["Ranglisten DK"]
    for row in list(ws.iter_rows(values_only=True))[1:12]:
        if row[2] and isinstance(row[4],(int,float)):
            s = norm(row[2])
            dk[s] = {"Q1 2026": row[3], "Q2 2026": row[4]}

    ws = wb["Ranglisten EU"]
    for row in list(ws.iter_rows(values_only=True))[1:12]:
        if row[1] and isinstance(row[4],(int,float)):
            s = norm(row[1])
            eu[s] = {"Q1 2026": row[3], "Q2 2026": row[4]}

    ws = wb["Ranglisten USA"]
    for row in list(ws.iter_rows(values_only=True))[1:12]:
        if row[1] and isinstance(row[5],(int,float)):
            s = norm(row[1])
            usa[s] = {"Q1 2026": row[4], "Q2 2026": row[5]}

    return dk, eu, usa


def hent_fremtid_vaekst(wb):
    ws = wb["Fremtid vækst"]
    rows = list(ws.iter_rows(values_only=True))
    data = {}
    cur = None
    for row in rows:
        if row[1] in ("Danmark","Europa","USA") and row[2] is not None and str(row[2]).startswith("Q"):
            cur = row[1]; data.setdefault(cur, {})
        elif cur and row[1] and row[2] is not None:
            ind = str(row[1])
            try: q1 = float(str(row[2]).replace(" ","")) if row[2] else None
            except: q1 = None
            try: q2 = float(str(row[3]).replace(" ","")) if row[3] else None
            except: q2 = None
            if q1 or q2:
                data[cur][ind] = {"q1": q1, "q2": q2}
    return data


def hent_historisk_makro(wb):
    """PMI, 10yr, CPI, VIX historik som tidsserier."""
    h = {}

    ws = wb["PMI"]
    cur = None
    for row in ws.iter_rows(values_only=True):
        lbl = row[4] if len(row)>4 else None
        if isinstance(lbl,str) and "PMI" in lbl:
            cur = "USA" if "USA" in lbl else ("Europa" if "Euroområdet" in lbl else "Danmark")
            h.setdefault(cur,{}).setdefault("PMI",[])
        elif cur and isinstance(row[3],str) and row[3].startswith("Q") and isinstance(row[4],(int,float)):
            h[cur]["PMI"].append({"kvartal":row[3],"vaerdi":row[4],"fase":row[5]})

    ws = wb["10 yr rate"]
    cur = None
    for row in ws.iter_rows(values_only=True):
        if row[3]=="USA 10 year": cur="USA"; h.setdefault("USA",{}).setdefault("10yr",[])
        elif row[3]=="Euroområdet 10 year": cur="Europa"; h.setdefault("Europa",{}).setdefault("10yr",[])
        elif cur and isinstance(row[2],str) and row[2].startswith("Q") and isinstance(row[3],(int,float)):
            h[cur]["10yr"].append({"kvartal":row[2],"vaerdi":row[3],"fase":row[4]})

    ws = wb["CPI(Inflation)"]
    cur = None
    for row in ws.iter_rows(values_only=True):
        if row[2]=="Kvartal":
            lbl = str(row[3]) if row[3] else ""
            cur = "Danmark" if "Danmark" in lbl else ("Europa" if "Euroområdet" in lbl else None)
            if cur: h.setdefault(cur,{}).setdefault("CPI",[])
        elif cur and isinstance(row[2],str) and row[2].startswith("Q") and isinstance(row[3],(int,float)):
            h[cur]["CPI"].append({"kvartal":row[2],"vaerdi":round(row[3]*100,2),"fase":row[4]})

    ws = wb["VIX"]
    cur = None
    for row in ws.iter_rows(values_only=True):
        if row[3]=="Kvartal":
            lbl = str(row[4]) if row[4] else ""
            if lbl=="Europa": cur="Europa"; h.setdefault("Europa",{}).setdefault("VIX",[])
            elif lbl=="USA": cur="USA"; h.setdefault("USA",{}).setdefault("VIX",[])
        elif cur and isinstance(row[3],str) and row[3].startswith("Q") and isinstance(row[4],(int,float)):
            h[cur]["VIX"].append({"kvartal":row[3],"vaerdi":row[4],"fase":row[5]})

    return h


def hent_etf_liste(wb):
    ws = wb["ETF - Liste"]
    res = {}
    for row in ws.iter_rows(values_only=True):
        if not row[0] or row[0]=="Kategori": continue
        kategori,navn,isin,region,sektor = (row[i] if len(row)>i else None for i in range(5))
        if navn and sektor:
            res.setdefault(norm(sektor),[]).append({"navn":navn,"isin":isin,"region":region})
    return res


def hent_aktier(wb):
    aktier = {"Europa":[],"USA":[]}
    for region,ark,t_col,s_col in [("Europa","Aktieliste EU",6,5),("USA","Aktieliste USA",6,5)]:
        ws = wb[ark]
        for row in list(ws.iter_rows(values_only=True))[1:]:
            ticker = row[t_col] if len(row)>t_col else None
            sektor = row[s_col] if len(row)>s_col else None
            mkt_cap = row[2] if len(row)>2 else None
            change = row[3] if len(row)>3 else None
            pe = row[7] if len(row)>7 else None
            beta = row[9] if len(row)>9 else None
            if ticker and isinstance(ticker,str) and sektor and isinstance(mkt_cap,(int,float)):
                aktier[region].append({
                    "ticker":ticker,"sektor":norm(sektor),
                    "market_cap":mkt_cap,"market_cap_mia":round(mkt_cap/1e9,1),
                    "change_pct":round(change*100,2) if isinstance(change,float) else None,
                    "pe":round(pe,1) if isinstance(pe,(int,float)) and pe>0 else None,
                    "beta":round(beta,2) if isinstance(beta,(int,float)) else None,
                })
    return aktier


def hent_spoergeskema(wb):
    ws = wb["Spørgeskema"]
    ql = []
    for row in list(ws.iter_rows(values_only=True))[1:]:
        if not row[0]: continue
        svar=[]; nr=1
        for i in range(4):
            sv,sc = row[1+i],row[5+i]
            if sv is not None and sc is not None:
                svar.append({"nr":nr,"tekst":str(sv),"score":int(sc)}); nr+=1
        ql.append({"tekst":str(row[0]),"svar":svar})
    return ql


def hent_profiler(wb):
    ws = wb["Profiler"]
    res = []
    for row in list(ws.iter_rows(values_only=True))[1:]:
        if not row[0]: continue
        res.append({"navn":str(row[0]),"fra":float(row[1]) if row[1] else 0,
                    "til":float(row[2]) if row[2] else 1,
                    "beskrivelse":str(row[3]) if row[3] else "",
                    "fordeling":str(row[4]) if row[4] else "",
                    "alternativer":str(row[5]) if row[5] else ""})
    return res


def hent_afstemning(wb):
    ws = wb["Afstemning til Virkelighed"]
    res = []
    for row in list(ws.iter_rows(values_only=True))[1:]:
        if not row[0]: continue
        res.append({"sektor":norm(str(row[0])),"makroscore":row[1],
                    "q3_afkast":row[2],"kommentar":str(row[3]) if row[3] else ""})
    return res

# ── Fasebregning ──────────────────────────────────────────────────────────────

def klassificer_makro(region_inputs, region="USA"):
    """
    Klassificer et sæt makroværdier til faser per indikator + samlet vægtet fase.
    region_inputs: {indikator: vaerdi}
    """
    v = region_inputs
    faser = {}

    faser["PMI"]          = fase_pmi(v.get("PMI"))
    faser["Yield Curve"]  = fase_yield_curve(v.get("Yield Curve"))
    faser["Retail Sales"] = fase_retail_sales(v.get("Retail Sales"))
    faser["NFP"]          = fase_nfp(v.get("NFP"), region)        # region-aware
    faser["Core CPI"]     = fase_core_cpi(v.get("Core CPI"))
    faser["BNP"]          = fase_bnp(v.get("BNP"))
    faser["Wage Growth"]  = fase_wage_growth(v.get("Wage Growth"))
    faser["Energy"]       = fase_energy(v.get("Energy"))
    faser["10 YR"]        = fase_rente(v.get("10 YR"), region)    # region-aware
    faser["VIX"]          = fase_vix(v.get("VIX"))
    faser["Unemployment"] = fase_unemployment(v.get("Unemployment"))

    # Vægtet afstemning
    point = {"Early":0,"Mid":0,"Late":0,"Recession":0}
    for ind, fase in faser.items():
        if fase:
            point[fase] += INDIKATOR_VAEGTER.get(ind, 1)

    global_fase = max(point, key=point.get)
    total = sum(point.values())

    faser["_global"] = global_fase
    faser["_point"]  = point
    faser["_pct"]    = {f: round(p/total*100) for f,p in point.items()} if total else {}
    return faser


def _pct(raw):
    """Omregn decimal til procent (0.019 → 1.9) hvis nødvendigt."""
    if raw is None: return None
    return round(raw * 100, 2) if abs(raw) < 1 else round(raw, 2)

def beregn_makrofase(fremtid):
    """
    Beregn global makrofase fra Excel Fremtid vækst-data.
    Nye indikatorer (Yield Curve, NFP, Retail Sales, Wage Growth, Energy)
    hentes fra DEFAULT_MAKRO som bedst-mulige estimat, da de ikke er i Excel.
    """
    global_point = {"Early":0,"Mid":0,"Late":0,"Recession":0}
    detaljer = []

    for region in ("Europa", "USA"):
        data = fremtid.get(region, {})
        dflt = DEFAULT_MAKRO.get(region, {})

        def ex(excel_key, fallback_ind):
            """Hent fra Excel, fallback til DEFAULT_MAKRO."""
            raw = data.get(excel_key, {}).get("q2")
            if raw is not None:
                return _pct(raw) if excel_key not in ("PMI","10 YR rate","VIX","Baltic Dry Index") else raw
            return dflt.get(fallback_ind, {}).get("vaerdi")

        inputs = {
            "PMI":          ex("PMI",         "PMI"),
            "Yield Curve":  dflt.get("Yield Curve",  {}).get("vaerdi"),  # ikke i Excel
            "Retail Sales": dflt.get("Retail Sales",{}).get("vaerdi"),  # ikke i Excel
            "NFP":          dflt.get("NFP",         {}).get("vaerdi"),  # ikke i Excel
            "Core CPI":     ex("CPI",         "Core CPI"),   # brug CPI som proxy
            "BNP":          ex("BNP",         "BNP"),
            "Wage Growth":  dflt.get("Wage Growth",{}).get("vaerdi"),  # ikke i Excel
            "Energy":       dflt.get("Energy",      {}).get("vaerdi"),  # ikke i Excel
            "10 YR":        ex("10 YR rate",  "10 YR"),
            "VIX":          ex("VIX",         "VIX"),
            "Unemployment": ex("Unemployment","Unemployment"),
        }

        faser = klassificer_makro(inputs, region)
        for f, pts in faser["_point"].items():
            global_point[f] += pts

        ind_liste = []
        for ind in INDIKATORER:
            val = inputs.get(ind)
            enhed = DEFAULT_MAKRO.get(region,{}).get(ind,{}).get("enhed","")
            if isinstance(val, float): vis = f"{val:.2f}"
            elif val is not None: vis = str(val)
            else: vis = "N/A"
            if enhed: vis += enhed
            ind_liste.append({
                "navn": ind, "vaerdi": vis,
                "fase": faser.get(ind),
                "vaegt": INDIKATOR_VAEGTER.get(ind, 1),
                "type": INDIKATOR_TYPE.get(ind, ""),
            })

        detaljer.append({
            "region": region, "fase": faser["_global"],
            "indikatorer": ind_liste,
            "point": faser["_point"], "pct": faser["_pct"],
        })

    global_fase = max(global_point, key=global_point.get)
    total = sum(global_point.values())
    fase_pct = {f: round(p/total*100) for f,p in global_point.items()} if total else {}
    titel, beskr, ikon, farve = FASE_META.get(global_fase, ("?","","❓","#fff"))

    return {"fase":global_fase,"titel":titel,"beskrivelse":beskr,"ikon":ikon,
            "farve":farve,"fase_pct":fase_pct,"detaljer":detaljer,"point":global_point}


# ── Sektorscoring ─────────────────────────────────────────────────────────────

def score_sektor_fra_inputs(makro_inputs):
    """
    Beregn 1-5 score per sektor for alle regioner fra rå makroværdier.
    makro_inputs: {region: {indikator: vaerdi}}
    Returnerer: {sektor: {region: score, 'avg': score, 'indikatorer': {...}}}
    """
    resultater = {}

    for sektor in SEKTOR_RÆKKEFØLGE:
        region_scores = []
        ind_detail = {}

        for region, inputs in makro_inputs.items():
            faser = klassificer_makro(inputs, region)
            vaegtet_sum = 0
            vaegt_sum = 0
            for ind in INDIKATORER:
                fase = faser.get(ind)
                if fase and sektor in SEKTOR_SENSITIVITET.get(ind, {}):
                    s = SEKTOR_SENSITIVITET[ind][sektor][fase]
                    vaegt = INDIKATOR_VAEGTER[ind]
                    vaegtet_sum += s * vaegt
                    vaegt_sum += vaegt
                    ind_detail.setdefault(ind, {})[region] = {"fase": fase, "score": s}
            if vaegt_sum > 0:
                region_scores.append(vaegtet_sum / vaegt_sum)

        avg = sum(region_scores) / len(region_scores) if region_scores else 0
        resultater[sektor] = {"avg": round(avg,2), "ind_detail": ind_detail}

    return resultater


def beregn_sektorscorer(dk, eu, usa, fase):
    """Kombiner rangliste-scores til rangerede sektorer."""
    res = []
    alle = set(dk) | set(eu) | set(usa)
    for sektor in alle:
        dk_s = dk.get(sektor,{}).get("Q2 2026")
        eu_s = eu.get(sektor,{}).get("Q2 2026")
        usa_s = usa.get(sektor,{}).get("Q2 2026")
        scores = [s for s in [dk_s,eu_s,usa_s] if isinstance(s,(int,float))]
        if not scores: continue
        avg = sum(scores)/len(scores)
        res.append({
            "sektor":sektor,"ikon":SEKTOR_IKONER.get(sektor,"📊"),
            "composite":round(avg,2),"makro_avg":round(avg,2),
            "dk":round(dk_s,2) if isinstance(dk_s,(int,float)) else None,
            "eu":round(eu_s,2) if isinstance(eu_s,(int,float)) else None,
            "usa":round(usa_s,2) if isinstance(usa_s,(int,float)) else None,
        })
    res.sort(key=lambda x: x["composite"], reverse=True)
    for i,s in enumerate(res): s["rank"] = i+1
    return res


def byg_heatmap(historisk_bnp, ranglister_dk, ranglister_eu, ranglister_usa):
    """
    Byg multi-kvartal heatmap data.
    Returnerer: {sektor: {kvartal: {'score': float, 'kilde': str}}}
    """
    dk, eu, usa = ranglister_dk, ranglister_eu, ranglister_usa
    heatmap = {}

    for sektor in SEKTOR_RÆKKEFØLGE:
        heatmap[sektor] = {}

        # Historiske kvartaler fra BNP-arket (Q1 2024 - Q4 2025)
        bnp_data = historisk_bnp.get(sektor, {})
        for kv in KVARTALER_HIST:
            region_vals = bnp_data.get(kv, {})
            vals = [v for v in region_vals.values() if isinstance(v,(int,float))]
            if vals:
                heatmap[sektor][kv] = {"score": round(sum(vals)/len(vals),2), "kilde":"historisk"}

        # Projekterede kvartaler fra Ranglister
        for kv in KVARTALER_PROJ:
            kv_key = "Q1 2026" if "Q1" in kv else "Q2 2026"
            scores = []
            for d in [dk.get(sektor,{}), eu.get(sektor,{}), usa.get(sektor,{})]:
                v = d.get(kv_key)
                if isinstance(v,(int,float)): scores.append(v)
            if scores:
                heatmap[sektor][kv] = {"score": round(sum(scores)/len(scores),2), "kilde":"prognose"}

    return heatmap


def simuler_sektorer(makro_inputs):
    """
    Simuler sektorscorer fra bruger-definerede makroværdier.
    makro_inputs: {region: {indikator: vaerdi}}
    """
    # Beregn fase per region
    faser = {}
    for region, inputs in makro_inputs.items():
        f = klassificer_makro(inputs, region)
        faser[region] = f

    # Score per sektor
    resultater = []
    for sektor in SEKTOR_RÆKKEFØLGE:
        region_scores = []
        for region, inputs in makro_inputs.items():
            f = faser[region]
            global_fase = f["_global"]
            # Vægtet score fra alle indikatorer
            vs, vv = 0, 0
            for ind in INDIKATORER:
                ind_fase = f.get(ind)
                if ind_fase and sektor in SEKTOR_SENSITIVITET.get(ind, {}):
                    s = SEKTOR_SENSITIVITET[ind][sektor][ind_fase]
                    w = INDIKATOR_VAEGTER[ind]
                    vs += s*w; vv += w
            if vv > 0: region_scores.append(vs/vv)

        avg = round(sum(region_scores)/len(region_scores),2) if region_scores else 0
        resultater.append({"sektor":sektor,"ikon":SEKTOR_IKONER.get(sektor,"📊"),"score":avg})

    resultater.sort(key=lambda x: x["score"], reverse=True)
    for i,s in enumerate(resultater): s["rank"] = i+1

    # Global fase
    global_pt = {"Early":0,"Mid":0,"Late":0,"Recession":0}
    for f in faser.values():
        for fase, pt in f["_point"].items():
            global_pt[fase] += pt
    global_fase = max(global_pt, key=global_pt.get)

    return {"sektorer": resultater, "fase": global_fase,
            "fase_meta": FASE_META.get(global_fase,{}), "faser": {r: f["_global"] for r,f in faser.items()}}


# ── Risikoprofil ──────────────────────────────────────────────────────────────

def match_profil(profiler, ratio):
    for p in profiler:
        if p["fra"] <= ratio <= p["til"]: return p
    return profiler[-1]

def parse_fordeling(s):
    parts = re.findall(r'([A-Za-zæøåÆØÅ ]+?)\s+(\d+)%', s)
    return {navn.strip(): int(pct) for navn, pct in parts}


# ── Samlet indlæsning ─────────────────────────────────────────────────────────

# Excel Fremtid vækst → indikator-navngivning (nye rækker tilføjet direkte i Excel)
_FREMTID_NAVNE = {
    "PMI":          "PMI",
    "BNP":          "BNP",
    "10 YR rate":   "10 YR",
    "CPI":          "Core CPI",     # bruges som Core CPI-proxy (headline ≈ core her)
    "VIX":          "VIX",
    "Unemployment": "Unemployment",
    "Yield Curve":  "Yield Curve",  # tilføjet i Excel (decimal → %)
    "Retail Sales": "Retail Sales", # tilføjet i Excel (decimal → %)
    "NFP":          "NFP",          # tilføjet i Excel (tusinde direkte — ingen omregning)
    "Wage Growth":  "Wage Growth",  # tilføjet i Excel (decimal → %)
    "Energy":       "Energy",       # tilføjet i Excel (decimal → %)
    # Baltic Dry Index og Currency (EUR/USD) ignoreres bevidst
}
# Disse gemmes som decimal i Excel og skal ganges med 100
_PROCENT_INDS = {"BNP", "Core CPI", "Unemployment", "Yield Curve", "Retail Sales", "Wage Growth", "Energy"}

def byg_seneste_makro(fremtid):
    """
    Byg seneste makro-snapshot til at præ-udfylde sliders.
    Excel-data bruges for indikatorer der findes i Fremtid vækst-arket;
    DEFAULT_MAKRO bruges for nye indikatorer (Yield Curve, NFP, Retail Sales,
    Wage Growth, Energy) der ikke er i Excel-filen endnu.
    Hvert felt markeres med 'kilde': 'excel' eller 'estimat'.
    """
    result = {}
    for region in ("Europa", "USA"):
        data = fremtid.get(region, {})
        dflt = DEFAULT_MAKRO.get(region, {})
        result[region] = {}

        for ind_key, ind_meta in dflt.items():
            excel_key = next((k for k, v in _FREMTID_NAVNE.items() if v == ind_key), None)
            kilde = "estimat"
            raw = None

            if excel_key and excel_key in data:
                raw = data[excel_key].get("q2") or data[excel_key].get("q1")
                if raw is not None:
                    if ind_key in _PROCENT_INDS and abs(raw) < 1:
                        raw = round(raw * 100, 2)
                    else:
                        raw = round(float(raw), 4)
                    kilde = "excel"

            if raw is None:
                raw = ind_meta.get("vaerdi", 0)

            result[region][ind_key] = {**ind_meta, "vaerdi": raw, "kilde": kilde}

    return result


def hent_alle_data():
    wb            = indlaes_wb()
    dk, eu, usa   = hent_ranglister(wb)
    makro_analyse  = hent_makro_analyse(wb)
    historisk_bnp  = hent_historisk_bnp(wb)
    fremtid        = hent_fremtid_vaekst(wb)
    historik       = hent_historisk_makro(wb)
    etf_liste      = hent_etf_liste(wb)
    aktier         = hent_aktier(wb)
    spoergeskema   = hent_spoergeskema(wb)
    profiler       = hent_profiler(wb)
    afstemning     = hent_afstemning(wb)

    makro_fase     = beregn_makrofase(fremtid)
    sektorer       = beregn_sektorscorer(dk, eu, usa, makro_fase["fase"])
    heatmap        = byg_heatmap(historisk_bnp, dk, eu, usa)
    seneste_makro  = byg_seneste_makro(fremtid)

    # Seneste kvartal: det nyeste kvartal med historiske data
    seneste_kvartal = ALLE_KVARTALER[-1]
    for kv in reversed(ALLE_KVARTALER):
        if any(kv in heatmap.get(s, {}) for s in SEKTOR_RÆKKEFØLGE):
            seneste_kvartal = kv
            break

    return {
        "makro_fase":     makro_fase,
        "sektorer":       sektorer,
        "heatmap":        heatmap,
        "makro_analyse":  makro_analyse,
        "etf_liste":      etf_liste,
        "aktier":         aktier,
        "spoergeskema":   spoergeskema,
        "profiler":       profiler,
        "afstemning":     afstemning,
        "historik":       historik,
        "fremtid":        fremtid,
        "alle_kvartaler": ALLE_KVARTALER,
        "indikatorer":    INDIKATORER,
        "indikator_vaegter": INDIKATOR_VAEGTER,
        "default_makro":  DEFAULT_MAKRO,
        "seneste_makro":  seneste_makro,
        "seneste_kvartal":seneste_kvartal,
        "opdateret":      datetime.now().strftime("%d.%m.%Y %H:%M"),
        "data_kvartal":   seneste_kvartal,
    }
