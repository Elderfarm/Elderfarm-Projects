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
KVARTALER_PROJ = ["Q1 2026","Q2 2026","Q3 2026"]
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
    # Pillar: Growth (35%) — ledende + lagging vækstmål
    "PMI":          4,   # Stærkeste enkelt-indikator, 2-3 mdr. lead
    "BNP":          2,   # Lagging bekræftelse
    "Retail Sales": 2,   # Coincident forbrugsdrevet vækst
    # Pillar: Labor (25%) — driver forbrug og inflationspres
    "NFP":          3,   # Stærkeste labor-signal (markedsbevægende)
    "Wage Growth":  2,   # Inflationspres + købekraft
    "Unemployment": 2,   # Lagging men vigtig regime-bekræftelse
    # Pillar: Inflation (20%) — driver pengepolitik
    "Core CPI":     3,   # Mest relevant for Fed/ECB
    "Energy":       1,   # Støj-indikator — rammer via ENERGI_AFHAENGIGHED
    # Pillar: Financial Conditions (20%)
    "Yield Curve":  3,   # 12-18 mdr. recession-predictor
    "10 YR":        1,   # Niveau-kontekst, delvis redundant med YC
    "VIX":          1,   # Markedssentiment, reaktiv ikke predictiv
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
    """
    PMI Composite — stærkeste leading indikator, 2-3 mdr. lead.
    50 = neutral, >50 = ekspansion, <50 = kontraktion.
    Threshold-zoner baseret på historisk cyklus-analyse.
    """
    if v is None: return None
    if v >= 54:   return "Mid"       # Stærk ekspansion — Mid-cycle momentum
    if v >= 50:   return "Early"     # Over 50 men ikke stærkt — early recovery
    if v >= 46:   return "Late"      # Svag kontraktion — Late/deceleration
    return "Recession"               # Dyb kontraktion

def fase_yield_curve(v):
    """
    10Y-2Y spread % — bedste recession-predictor, 12-18 mdr. lead.
    VIGTIGT: Stejl kurve EFTER inversion = CB har lettet = Early signal.
    Postiv kurve i normal vækst = Mid. Inverteret = Late/Recession.
    """
    if v is None: return None
    if v > 1.2:   return "Early"     # Meget stejl: CB har sænket post-recession
    if v > 0.2:   return "Mid"       # Normal positiv hældning = sund vækst
    if v > -0.5:  return "Late"      # Flad til let inverteret = stramning bider
    return "Recession"               # Dybt inverteret (> -0.5%) = recession imminent

def fase_retail_sales(v):
    """
    Retail Sales MoM % — coincident forbrugsmål.
    Gentagne negative måneder = recession. Stabil >0.3% = solid forbrug.
    """
    if v is None: return None
    if v < -0.2:  return "Recession" # Klart negativt
    if v < 0.1:   return "Late"      # Stagnation/svagt
    if v < 0.35:  return "Early"     # Moderat vækst
    return "Mid"                      # Solid forbrugsvækst

def fase_nfp(v, region="USA"):
    """
    NFP/jobbvækst — market-moving coincident/leading indikator.
    Negativ = recession-bekræftelse. Høj = mid-cycle acceleration.
    """
    if v is None: return None
    if region == "USA":
        if v > 200:  return "Mid"      # Stærk vækst — mid-cycle momentum
        if v > 80:   return "Early"    # Moderat vækst — early recovery
        if v > 0:    return "Late"     # Svag/positiv — deceleration
        return "Recession"             # Tab af jobs
    else:
        if v > 120:  return "Mid"
        if v > 40:   return "Early"
        if v > 0:    return "Late"
        return "Recession"

def fase_core_cpi(v):
    """
    Kerninflation YoY % — primær driver for pengepolitik.
    Peak-score ved 2.0% (Fed-mål). Stigende over 3% = stramning = Late-signal.
    IKKE-monoton: både for lav (<1.5%) og for høj (>3.5%) er negativt.
    """
    if v is None: return None
    if v < 1.2:   return "Recession"  # Deflationspres — CB mister handlingsrum
    if v < 2.0:   return "Early"      # Under mål — ekspansiv pengepolitik mulig
    if v < 3.0:   return "Mid"        # Acceptabel zone — 2-3% er kontrolleret
    return "Late"                      # Over 3% = stramning nødvendig (sænket threshold fra 3.5%)

def fase_bnp(v):
    """
    BNP vækst YoY % — lagging bekræftelse.
    US potentiel vækst ~2%, Eurozone ~1.5%. Over potentiel = Late-signal.
    """
    if v is None: return None
    if v < 0:     return "Recession"
    if v < 0.8:   return "Early"      # Svag men positiv vækst — tidlig recovery
    if v < 2.2:   return "Mid"        # Omkring/over potentiel (sænket fra 2.5)
    return "Late"                      # Over potentiel = overophedning

def fase_wage_growth(v):
    """
    Lønvækst YoY % — coincident/lagging. Høj lønvækst driver inflation (Late).
    3-4% = normalt i stærkt marked. >4.5% = Fed bekymret.
    """
    if v is None: return None
    if v < 1.8:   return "Recession"
    if v < 3.2:   return "Early"
    if v < 4.2:   return "Mid"        # 3.2-4.2% = stærkt men acceptabelt
    return "Late"                      # >4.2% = inflationspres (sænket fra 4.5%)

def fase_energy(v):
    """
    Oliepris YoY % — støj-indikator. Primær effekt via ENERGI_AFHAENGIGHED.
    Giver faseindikation for energisektorens relativperformance.
    """
    if v is None: return None
    if v < -30:   return "Recession"  # Demand-drevet kollaps
    if v < 5:     return "Early"      # Stabil/let faldende priser
    if v < 30:    return "Mid"        # Stigende priser — industriel efterspørgsel
    return "Late"                      # Kraftig stigning = stagflationsrisiko

def fase_rente(v, region="USA"):
    """
    10-årig rente absolut niveau — lagging finansiel kontekst.
    Bruges som supplement til yield curve — fanger tightening-niveau.
    """
    if v is None: return None
    if region == "USA":
        if v < 3.0:   return "Early"   # Lave renter = akkommodativ CB
        if v < 4.2:   return "Mid"     # Normalt niveau
        if v < 5.0:   return "Late"    # Restriktivt (sænket øvre grænse fra 4.75→5.0)
        return "Recession"             # Ekstremt restriktivt — credit crunch risiko
    else:
        if v < 1.2:   return "Early"
        if v < 2.2:   return "Mid"
        if v < 3.2:   return "Late"
        return "Recession"

def fase_vix(v):
    """
    VIX — markedsbaseret risiko-sentiment. Reaktiv, ikke predictiv.
    VIGTIGT: I Early cycle er VIX ofte 18-25 (fortsat usikkerhed).
    Meget lav VIX (<14) kan signalere Mid-cycle complacency.
    """
    if v is None: return None
    if v < 14:    return "Mid"         # Lav vol = complacency/mid-cycle
    if v < 22:    return "Early"       # Moderat vol = recovery med usikkerhed (hævet fra 20→22)
    if v < 32:    return "Late"        # Høj vol = stressede markeder
    return "Recession"                 # Krise-vol

def fase_unemployment(v):
    """
    Arbejdsløshed % — lagging indikator. Bekræfter regime, trigger ikke.
    USA fuld-beskæftigelse ~3.5-4%. Europa strukturelt højere (~6.5-7%).
    Tærsklerne er globale — region-specificitet håndteres via NFP.
    """
    if v is None: return None
    if v > 7.5:   return "Recession"  # Klart forhøjet (sænket fra 8% for tidligere signal)
    if v > 5.5:   return "Late"       # Over normalt (sænket fra 6%)
    if v > 4.0:   return "Mid"        # Normalt arbejdsmarked (sænket fra 4.5%)
    return "Early"                     # Meget tight — stærkt arbejdsmarked

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
# ─────────────────────────────────────────────────────────────────────────────

# ── Energiafhængigheds-justeringer ───────────────────────────────────────────
# Europa er nettoimportør af energi (særligt naturgas og olie fra Mellemøsten/Rusland).
# Stigende energipriser (Energy = Mid/Late) rammer europæiske forbrugere og
# industrien hårdere end USA, som er nettooeksportør siden shale-revolutionen.
# Justeringerne tilføjes oveni basis-scoren og clampes til [1, 5].
# Stærkere effekt i Late end Mid (energipriser har haft tid til at slå igennem).
ENERGI_AFHAENGIGHED = {
    "Europa": {
        # Forbrugere rammes af høje energiregninger → presser reelt forbrug
        "Consumer Discretionary": {"Mid": -0.4, "Late": -0.9},
        # Tung industri med høje energiomkostninger
        "Industrials":            {"Mid": -0.3, "Late": -0.7},
        "Materials":              {"Mid": -0.3, "Late": -0.6},
        "Consumer Staples":       {"Mid": -0.2, "Late": -0.4},
        # Europæiske energiselskaber profiterer delvist
        "Energy":                 {"Mid": +0.3, "Late": +0.5},
    },
    "USA": {
        # USA er nettoeksportør → energiprisstigninger gavner energisektoren ekstra
        "Energy":      {"Mid": +0.4, "Late": +0.7},
        # Olie-service og raffinaderier
        "Industrials": {"Mid": +0.2, "Late": +0.3},
        # Forbrugere rammes dog stadig, men mindre end Europa
        "Consumer Discretionary": {"Late": -0.3},
    },
}

# ── USA's strukturelle AI-fordel ─────────────────────────────────────────────
# USA huser verdens dominerende AI-infrastruktur (NVIDIA, Microsoft, Google,
# Meta, OpenAI). Denne strukturelle fordel giver IT og Communications Services
# en vedvarende premium ift. Europa, særligt i vækstfaser (Early/Mid) hvor
# AI-monetarisering og capex-cycles er stærkest.
# Ingen tilsvarende European AI-champion i samme liga endnu (2025-2026 horizon).
AI_FORDEL_USA = {
    # USA's AI-strukturelle fordel er størst i vækstfaser (capex-cycles, monetarisering).
    # I recession rammes selv FAANG hårdt af multiples-kompression og capex-cuts.
    # Bonus = 0 i Recession (realistisk — systemisk krise rammer alle).
    "Information Technology":  {"Early": +0.6, "Mid": +0.8, "Late": +0.3, "Recession": 0},
    "Communications Services": {"Early": +0.4, "Mid": +0.6, "Late": +0.2, "Recession": 0},
}

# ─────────────────────────────────────────────────────────────────────────────
SEKTOR_SENSITIVITET = {
    # ── PMI (ledende, vægt 3) ─────────────────────────────────────────────
    # Cykliske sektorer reagerer kraftigt på PMI-bevægelser
    "PMI": {
        # PMI driver cykliske sektorer. IT starter tidligt (capex recovery).
        # Materials topper i Mid (industriel efterspørgsel peak). Energy Late.
        "Financials":              {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Real Estate":             {"Early":3,"Mid":3,"Late":2,"Recession":1},
        "Consumer Discretionary":  {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Information Technology":  {"Early":4,"Mid":5,"Late":3,"Recession":1},  # Early↑: capex recovery
        "Industrials":             {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":4,"Mid":5,"Late":3,"Recession":1},  # Mid↑: peak industriel demand
        "Consumer Staples":        {"Early":2,"Mid":2,"Late":4,"Recession":5},
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":5},
        "Energy":                  {"Early":2,"Mid":4,"Late":5,"Recession":2},  # Recession↑: 1→2 (ikke katastrofe)
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Utilities":               {"Early":1,"Mid":2,"Late":4,"Recession":5},  # Early↓: alternativ cost
    },
    # ── Yield Curve 10Y-2Y (ledende, vægt 3) ─────────────────────────────
    # Stejl kurve = bankmargin stiger → Financials outperformer stærkt
    # Inverteret kurve = duration-aktiver (Utilities, Staples) outperformer relativt
    "Yield Curve": {
        # Stejl kurve = bankmargin + kreditvækst = Financials/Industrials outperformer.
        # Flad/inverteret = duration premium: Utilities/Staples relativt bedre.
        # RE: dybt sensitiv til renteniveau — Late score sænket til 1.
        "Financials":              {"Early":5,"Mid":4,"Late":2,"Recession":2},  # NIM benefit
        "Real Estate":             {"Early":4,"Mid":3,"Late":1,"Recession":3},  # Recession↑: CB letter
        "Consumer Discretionary":  {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Information Technology":  {"Early":4,"Mid":4,"Late":2,"Recession":2},  # Mid↓: duration-risk
        "Industrials":             {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":4,"Mid":3,"Late":2,"Recession":2},
        "Consumer Staples":        {"Early":2,"Mid":2,"Late":3,"Recession":4},
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":4},
        "Energy":                  {"Early":3,"Mid":3,"Late":4,"Recession":2},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":3},
        "Utilities":               {"Early":1,"Mid":2,"Late":4,"Recession":5},  # Bond-proxy, Early↓
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
            if region == "Danmark": continue
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

_FASE_SCORE = {"Early": 2, "Mid": 3, "Late": 1, "Recession": 0}

def klassificer_makro(region_inputs, region="USA"):
    """
    Klassificer makroværdier til faser per indikator + vægtet global fase.

    ARKITEKTUR (4-pillar model):
      Growth     (35%): PMI w4, BNP w2, Retail Sales w2
      Labor      (25%): NFP w3, Wage Growth w2, Unemployment w2
      Inflation  (20%): Core CPI w3, Energy w1
      Financial  (20%): Yield Curve w3, 10 YR w1, VIX w1

    Global fase bestemmes ved PILLAR-REGLER — ikke simpel afstemning.
    Dette eliminerer cliff-effects og giver mere robust regime-detection.
    Afstemningen (point/_pct) bevares til UI-visning og konfidensvisning.
    """
    v = region_inputs
    faser = {}

    faser["PMI"]          = fase_pmi(v.get("PMI"))
    faser["Yield Curve"]  = fase_yield_curve(v.get("Yield Curve"))
    faser["Retail Sales"] = fase_retail_sales(v.get("Retail Sales"))
    faser["NFP"]          = fase_nfp(v.get("NFP"), region)
    faser["Core CPI"]     = fase_core_cpi(v.get("Core CPI"))
    faser["BNP"]          = fase_bnp(v.get("BNP"))
    faser["Wage Growth"]  = fase_wage_growth(v.get("Wage Growth"))
    faser["Energy"]       = fase_energy(v.get("Energy"))
    faser["10 YR"]        = fase_rente(v.get("10 YR"), region)
    faser["VIX"]          = fase_vix(v.get("VIX"))
    faser["Unemployment"] = fase_unemployment(v.get("Unemployment"))

    # ── Pillar-aggregering ──────────────────────────────────────────────────
    def pillar_score(inds_weights):
        """Vægtet gennemsnit af _FASE_SCORE for en pillar. Returnerer 0-3."""
        s, w = 0, 0
        for ind, wt in inds_weights:
            f = faser.get(ind)
            if f:
                s += _FASE_SCORE[f] * wt; w += wt
        return s / w if w else 1.5

    growth_p = pillar_score([("PMI",4),("BNP",2),("Retail Sales",2)])
    labor_p  = pillar_score([("NFP",3),("Wage Growth",2),("Unemployment",2)])
    infl_p   = pillar_score([("Core CPI",3),("Energy",1)])
    fin_p    = pillar_score([("Yield Curve",3),("10 YR",1),("VIX",1)])

    # ── Pillar-baseret fasebeslutning (prioriteret rækkefølge) ──────────────
    # Recession: klart growth-kollaps
    if growth_p < 0.8 or (growth_p < 1.3 and labor_p < 0.8):
        global_fase = "Recession"
    # Late: inflationsoverhedning (infl i Late-zone ≤1.5) + finansiel stramning + decelererende vækst
    elif infl_p <= 1.5 and fin_p < 1.8 and growth_p < 2.0:
        global_fase = "Late"
    # Late: stagflation — høj inflation selvom finansielle forhold ikke ekstreme
    elif infl_p <= 1.2 and growth_p < 1.8:
        global_fase = "Late"
    # Mid: stærk vækst + solidt arbejdsmarked (begge over neutral)
    elif growth_p >= 2.2 and labor_p >= 2.0:
        global_fase = "Mid"
    # Early: recovery — alt andet
    else:
        global_fase = "Early"

    # ── Afstemning bevares til fase_pct UI-visning ──────────────────────────
    point = {"Early":0,"Mid":0,"Late":0,"Recession":0}
    for ind, fase in faser.items():
        if fase and not ind.startswith("_"):
            point[fase] += INDIKATOR_VAEGTER.get(ind, 1)
    total = sum(point.values())

    faser["_global"]   = global_fase
    faser["_point"]    = point
    faser["_pct"]      = {f: round(p/total*100) for f,p in point.items()} if total else {}
    faser["_pillars"]  = {"Growth": round(growth_p,2), "Labor": round(labor_p,2),
                          "Inflation": round(infl_p,2), "Financial": round(fin_p,2)}
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


def byg_heatmap(historisk_bnp, sim_scores):
    """
    Byg multi-kvartal heatmap data.
    historisk_bnp: {sektor: {kvartal: {region: score}}} — fra BNP-ark (EU+USA)
    sim_scores: {sektor: score} — fra simuler_sektorer(), bruges til Q1+Q2 2026
    Returnerer: {sektor: {kvartal: {'score': float, 'kilde': str}}}
    """
    heatmap = {}

    for sektor in SEKTOR_RÆKKEFØLGE:
        heatmap[sektor] = {}

        # Historiske kvartaler fra BNP-arket (Q1 2024 - Q4 2025), kun EU+USA
        bnp_data = historisk_bnp.get(sektor, {})
        for kv in KVARTALER_HIST:
            region_vals = bnp_data.get(kv, {})
            vals = [v for r,v in region_vals.items() if isinstance(v,(int,float)) and r != "Danmark"]
            if vals:
                heatmap[sektor][kv] = {"score": round(sum(vals)/len(vals),2), "kilde":"historisk"}

        # Projekterede kvartaler: brug simulator-score (samme som dashboard)
        score = sim_scores.get(sektor)
        if score is not None:
            for kv in KVARTALER_PROJ:
                heatmap[sektor][kv] = {"score": score, "kilde":"prognose"}

    return heatmap


def _score_sektor_region(sektor, region, f):
    """
    Beregn vægtet score for én sektor i én region fra en allerede klassificeret
    fase-dict f (output fra klassificer_makro). Anvender:
      1. SEKTOR_SENSITIVITET — basis indikator-scores
      2. ENERGI_AFHAENGIGHED — Europa/USA energijustering baseret på Energy-fase
      3. AI_FORDEL_USA — strukturel IT/ComSvcs premium for USA
    Returnerer float [1,5] eller None hvis ingen data.
    """
    vs, vv = 0, 0
    for ind in INDIKATORER:
        ind_fase = f.get(ind)
        if ind_fase and sektor in SEKTOR_SENSITIVITET.get(ind, {}):
            s = SEKTOR_SENSITIVITET[ind][sektor][ind_fase]
            w = INDIKATOR_VAEGTER[ind]
            vs += s * w; vv += w
    if vv == 0: return None
    base = vs / vv

    # Energiafhængighedsjustering (aktiv når Energy-indikatoren = Mid eller Late)
    energy_fase = f.get("Energy")
    if energy_fase in ("Mid", "Late"):
        adj = ENERGI_AFHAENGIGHED.get(region, {}).get(sektor, {}).get(energy_fase, 0)
        base += adj

    # USA's strukturelle AI-fordel (aktiv i alle faser, stærkest i Early/Mid)
    if region == "USA":
        global_fase = f.get("_global", "Mid")
        base += AI_FORDEL_USA.get(sektor, {}).get(global_fase, 0)

    return round(max(1.0, min(5.0, base)), 2)


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
            sc = _score_sektor_region(sektor, region, faser[region])
            if sc is not None: region_scores.append(sc)

        avg = round(sum(region_scores)/len(region_scores),2) if region_scores else 0
        region_score_map = {}
        for region in makro_inputs:
            sc = _score_sektor_region(sektor, region, faser[region])
            region_score_map[region] = sc if sc is not None else 0
        resultater.append({"sektor":sektor,"ikon":SEKTOR_IKONER.get(sektor,"📊"),"score":avg,
                           "region_scores": region_score_map})

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


def sektor_ind_scores(seneste_makro, sektor):
    """
    Returnerer per-indikator score for en sektor baseret på seneste_makro.
    Totals inkluderer energiafhængigheds- og AI-justeringer (samme som simuler_sektorer).
    Output: {region: [{ind, fase, score, vaegt}], totals: {region: float},
             justeringer: {region: {label, delta}}}
    """
    result = {}
    totals = {}
    justeringer = {}
    for region, inds in seneste_makro.items():
        inputs = {k: v["vaerdi"] for k, v in inds.items()}
        f = klassificer_makro(inputs, region)
        rows = []
        for ind in INDIKATORER:
            fase = f.get(ind)
            if fase and sektor in SEKTOR_SENSITIVITET.get(ind, {}):
                sc = SEKTOR_SENSITIVITET[ind][sektor][fase]
                w = INDIKATOR_VAEGTER[ind]
                rows.append({"ind": ind, "fase": fase, "score": sc, "vaegt": w})
        result[region] = rows

        # Totals via _score_sektor_region (inkl. justeringer)
        total = _score_sektor_region(sektor, region, f)
        totals[region] = total if total is not None else 0

        # Beregn hvilke justeringer der er aktive
        adjs = []
        energy_fase = f.get("Energy")
        if energy_fase in ("Mid", "Late"):
            delta = ENERGI_AFHAENGIGHED.get(region, {}).get(sektor, {}).get(energy_fase, 0)
            if delta != 0:
                adjs.append({"label": f"Energiafhængighed ({region})", "delta": round(delta, 2)})
        if region == "USA":
            global_fase = f.get("_global", "Mid")
            delta = AI_FORDEL_USA.get(sektor, {}).get(global_fase, 0)
            if delta != 0:
                adjs.append({"label": "USA AI-strukturel fordel", "delta": round(delta, 2)})
        justeringer[region] = adjs

    return {"regioner": result, "totals": totals, "justeringer": justeringer}


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
    wb             = indlaes_wb()
    dk, eu, usa    = hent_ranglister(wb)
    makro_analyse  = hent_makro_analyse(wb)
    historisk_bnp  = hent_historisk_bnp(wb)
    fremtid        = hent_fremtid_vaekst(wb)
    historik       = hent_historisk_makro(wb)
    etf_liste      = hent_etf_liste(wb)
    aktier         = hent_aktier(wb)
    spoergeskema   = hent_spoergeskema(wb)
    profiler       = hent_profiler(wb)
    afstemning     = hent_afstemning(wb)

    # Byg seneste_makro: Excel → live FRED/ECB data (hvis tilgængeligt) → DEFAULT_MAKRO
    seneste_makro_excel = byg_seneste_makro(fremtid)
    try:
        from live_data import hent_live_makro, flet_med_default
        live = hent_live_makro()
        if live:
            seneste_makro = flet_med_default(live, seneste_makro_excel)
        else:
            seneste_makro = seneste_makro_excel
    except Exception as _e:
        import logging; logging.getLogger(__name__).warning(f"live_data fejl: {_e}")
        seneste_makro = seneste_makro_excel

    makro_fase     = beregn_makrofase(fremtid)

    # Brug samme algoritme som "Mine forventninger" så tallene stemmer overens
    sim_inputs = {r: {k: v["vaerdi"] for k, v in inds.items()}
                  for r, inds in seneste_makro.items()}
    sim_result = simuler_sektorer(sim_inputs)
    sektorer = sim_result["sektorer"]

    for s in sektorer:
        rs = s.pop("region_scores", {})
        s["eu"]  = rs.get("Europa", None)
        s["usa"] = rs.get("USA", None)
        s["composite"] = s["score"]

    # Byg sim_scores lookup til heatmap projection: {sektor: score}
    sim_scores_map = {s["sektor"]: s["score"] for s in sektorer}
    heatmap = byg_heatmap(historisk_bnp, sim_scores_map)

    # Seneste kvartal med data
    seneste_kvartal = ALLE_KVARTALER[-1]
    for kv in reversed(ALLE_KVARTALER):
        if any(kv in heatmap.get(s["sektor"], {}) for s in sektorer):
            seneste_kvartal = kv
            break

    return {
        "makro_fase":      makro_fase,
        "sektorer":        sektorer,
        "heatmap":         heatmap,
        "makro_analyse":   makro_analyse,
        "etf_liste":       etf_liste,
        "aktier":          aktier,
        "spoergeskema":    spoergeskema,
        "profiler":        profiler,
        "afstemning":      afstemning,
        "historik":        historik,
        "fremtid":         fremtid,
        "alle_kvartaler":  ALLE_KVARTALER,
        "indikatorer":     INDIKATORER,
        "indikator_vaegter": INDIKATOR_VAEGTER,
        "default_makro":   DEFAULT_MAKRO,
        "seneste_makro":   seneste_makro,
        "seneste_kvartal": seneste_kvartal,
        "opdateret":       datetime.now().strftime("%d.%m.%Y %H:%M"),
        "data_kvartal":    seneste_kvartal,
    }
