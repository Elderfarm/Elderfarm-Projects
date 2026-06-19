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
# Q1+Q2 2026 er afsluttede kvartaler på beregningstidspunktet (ikke prognose
# længere) — scores beregnes med samme model-metode som KVARTALER_HIST, men ud
# fra "Fremtid vækst"-arkets q1/q2-kolonner i stedet for de historiske ark.
KVARTALER_Q1Q2_2026 = ["Q1 2026","Q2 2026"]
KVARTALER_PROJ = ["Q3 2026"]
ALLE_KVARTALER = KVARTALER_HIST + KVARTALER_Q1Q2_2026 + KVARTALER_PROJ

# Optimeret indikatorliste — Baltic Dry og Currency fjernet (Asien-bias, ikke konjunkturel)
# Tilføjet: Yield Curve (10Y-2Y), NFP, Retail Sales, Wage Growth, Energy (olie YoY%)
# CPI → Core CPI (ex. food+energy) — mere pengepolitisk relevant
INDIKATORER = [
    "PMI", "Yield Curve", "Retail Sales", "NFP",
    "Core CPI", "BNP", "Wage Growth",
    "Energy", "10 YR", "VIX", "Unemployment",
]
# Region-specifik vægtning — USA og Europa har strukturelt forskellige
# transmissionsmekanismer (se INDIKATOR_VAEGTER_REGION), så samme indikator
# skal ikke nødvendigvis tælle lige meget i de to regioner.
INDIKATOR_VAEGTER_REGION = {
    "USA": {
        # Growth — forbrugsdrevet økonomi (~68% af BNP), PMI/Retail er kernen
        "PMI":          4,   # Stærkeste enkelt-indikator, 2-3 mdr. lead
        "BNP":          2,   # Lagging bekræftelse
        "Retail Sales": 3,   # Direkte mål for forbrug — dominerende vækstdriver i USA
        # Labor — fleksibelt arbejdsmarked, NFP er markedsbevægende/leading
        "NFP":          4,   # Stærkeste labor-signal i USA
        "Wage Growth":  2,   # Inflationspres + købekraft
        "Unemployment": 1,   # Overskygges af NFP som leading signal
        # Inflation — demand-drevet, tæt Fed-link
        "Core CPI":     4,   # Direkte pengepolitik-trigger (demand-pull)
        "Energy":       1,   # USA strukturelt mindre energiafhængig (skifer)
        # Financial Conditions — dyb/likvid markedsbaseret transmission
        "Yield Curve":  4,   # Bedste recession-predictor, hurtig Fed-transmission
        "10 YR":        1,   # Niveau-kontekst, delvis redundant med YC
        "VIX":          1,   # Markedssentiment, reaktiv ikke predictiv
    },
    "Europa": {
        # Growth — mindre forbrugsdrevet (~54% af BNP), PMI stadig stærkest leading
        "PMI":          4,   # Leading lige stærkt som i USA
        "BNP":          2,   # Lagging bekræftelse
        "Retail Sales": 1,   # Mindre dominerende vækstdriver end i USA
        # Labor — rigidt/institutionelt, lønvækst og NFP-ækvivalent er lagging
        "NFP":          2,   # Mere lagging og mindre volatil pga. arbejdsmarkedsrigiditet
        "Wage Growth":  1,   # Forsinket af overenskomster, lav prædiktiv værdi
        "Unemployment": 2,   # Bedste lagging regime-bekræftelse i et trægt arbejdsmarked
        # Inflation — cost-push (energi/import), Core CPI er et mindre "rent" signal
        "Core CPI":     2,   # Forurenes af supply-side chok, mindre rent demand-signal
        "Energy":       4,   # Kritisk driver — Europa er importafhængig (vækst+inflation)
        # Financial Conditions — fragmenteret/bankbaseret transmission
        "Yield Curve":  2,   # Mindre pålidelig predictor pga. fragmenteret transmission
        "10 YR":        2,   # Statsrente-niveau vigtigere pga. periferi-spreads/gældsrisiko
        "VIX":          1,   # Globalt risikosentiment, samme rolle som i USA
    },
}

def vaegt(ind, region="USA"):
    """Region-specifik indikatorvægt med USA som fallback."""
    return INDIKATOR_VAEGTER_REGION.get(region, INDIKATOR_VAEGTER_REGION["USA"]).get(ind, 1)

# Bagudkompatibel flad vægtning (USA-basis) — bruges hvor region ikke er kendt.
INDIKATOR_VAEGTER = INDIKATOR_VAEGTER_REGION["USA"]
# Kategorisering: ledende vs. lagging (til UI-visning)
INDIKATOR_TYPE = {
    "PMI": "leading", "Yield Curve": "leading",
    "Retail Sales": "leading", "NFP": "leading",
    "Core CPI": "coincident", "BNP": "lagging", "Wage Growth": "coincident",
    "Energy": "leading", "10 YR": "lagging", "VIX": "leading", "Unemployment": "lagging",
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
    "Early":     ("Early recovery", "Economy improving. Broad upswing, cyclical sectors outperform.", "🌱", "#4ade80"),
    "Mid":       ("Mid-cycle",      "Solid growth, moderate inflation. Broad exposure favorable.",    "🚀", "#60a5fa"),
    "Late":      ("Late-cycle",     "Tight monetary policy, rising inflation. Defensives & energy.",  "🌇", "#facc15"),
    "Recession": ("Recession",      "Negative growth. Bonds, gold and defensive sectors.",            "⚠️", "#f87171"),
}

# Aktuelle makrodata — opdateret 18. juni 2026 med live kilde-referencer
# Kilder: ISM PMI maj 2026, BLS jobs-rapport maj 2026, BLS CPI maj 2026,
#         BEA GDP Q1 2026 (anden estimat), US/DE Treasury juni 17-18 2026,
#         Eurostat HICP maj/juni 2026, Eurostat BNP Q1 2026, S&P Global/HCOB PMI (final maj),
#         EIA/Bloomberg oliepriser juni 2026 (kollaps efter USA-Iran fredsaftale)
DEFAULT_MAKRO = {
    "Europa": {
        # Eurozone Composite PMI maj 2026 FINAL: 48.5 (opjusteret fra prelim. 47.5)
        # Manufacturing 51.6 (op), Services 47.7 (stadig kontraktion, men mindre hård)
        "PMI":          {"vaerdi": 48.5, "enhed": "",   "label": "PMI Eurozone Composite (May 2026, final)"},
        # Germany 10Y Bund: 2.93% · 2Y: 2.63% → spread +0.30% (18. juni 2026)
        "Yield Curve":  {"vaerdi": 0.30, "enhed": "%",  "label": "Yield Curve 10Y-2Y (June 18, 2026)"},
        # EU Retail Sales svag — services PMI indikerer forbrugertilbageholdelse
        # Estimat: ca. +2.5% YoY (eurozone retail Q1/tidlig Q2)
        "Retail Sales": {"vaerdi": 2.5,  "enhed": "%",  "label": "Retail Sales YoY % (estimate)"},
        # Eurozone månedlig beskæftigelse ca. 60-80k netto (stabil men aftagende)
        "NFP":          {"vaerdi": 65.0, "enhed": "k",  "label": "Net employment growth (per month)"},
        # Eurostat core HICP (ex energi, mad, alkohol, tobak) maj 2026: 2.5% YoY (headline 3.2%)
        "Core CPI":     {"vaerdi": 2.5,  "enhed": "%",  "label": "Core inflation HICP (May 2026)"},
        # Eurozone BNP YoY Q1 2026: +0.8% (markant afmatning fra 1.3% i Q4 2025)
        "BNP":          {"vaerdi": 0.8,  "enhed": "%",  "label": "GDP growth YoY Q1 2026"},
        # ECB forhandlet lønvækst fortsat ca. 3.5% i tidlig 2026 (ECB løntracker)
        "Wage Growth":  {"vaerdi": 3.5,  "enhed": "%",  "label": "Wage growth YoY % (ECB wage tracker)"},
        # Brent oliepris kollapset: ~$79 (18. juni 2026) vs ~$105 i juni 2025 → ca. -25% YoY
        # USA-Iran fredsaftale fjernede forsyningskrisen der drev sidste års høje priser
        "Energy":       {"vaerdi": -25.0,"enhed": "%",  "label": "Oil price YoY % (Brent, June 18, 2026)"},
        # Germany 10Y Bund: 2.93% (18. juni 2026) — faldet fra 3.00% efter oliekollaps
        "10 YR":        {"vaerdi": 2.93, "enhed": "%",  "label": "10Y Bund yield (June 18, 2026)"},
        # VIX globalt signal: 16.4 (17. juni 2026 close) — fortsat aftagende fra 30+ i marts
        "VIX":          {"vaerdi": 16.4, "enhed": "",   "label": "VIX (June 17, 2026)"},
        # Eurozone arbejdsløshed april 2026: 6.3% (Eurostat)
        "Unemployment": {"vaerdi": 6.3,  "enhed": "%",  "label": "Unemployment rate (April 2026)"},
    },
    "USA": {
        # ISM Manufacturing PMI maj 2026: 54.0 (5. ekspansionsmåned i træk, udgivet 1. juni)
        "PMI":          {"vaerdi": 54.0, "enhed": "",   "label": "ISM Manufacturing PMI (maj 2026)"},
        # 10Y Treasury: 4.49% · 2Y: 4.20% → spread +0.29% (17. juni 2026)
        "Yield Curve":  {"vaerdi": 0.29, "enhed": "%",  "label": "Yield Curve 10Y-2Y (June 17, 2026)"},
        # US Retail Sales core YoY maj 2026: +7.0% (8. vækstmåned i træk)
        "Retail Sales": {"vaerdi": 7.0,  "enhed": "%",  "label": "Retail Sales YoY % (May 2026)"},
        # BLS NFP maj 2026: +172k (over forventning på 85k) — juni-tal udkommer 2. juli
        "NFP":          {"vaerdi": 172,  "enhed": "k",  "label": "Non-Farm Payrolls (May 2026)"},
        # BLS Core CPI (ex food+energy) maj 2026: +2.9% YoY (headline 4.2%) — juni-tal udkommer 14. juli
        "Core CPI":     {"vaerdi": 2.9,  "enhed": "%",  "label": "Core CPI YoY (May 2026)"},
        # BEA Real GDP YoY Q1 2026: +2.6% (Q/Q annualiseret: 1.6%)
        "BNP":          {"vaerdi": 2.6,  "enhed": "%",  "label": "Real GDP YoY Q1 2026"},
        # BLS Avg. Hourly Earnings maj 2026: +3.4% YoY (aftagende fra 3.6%)
        "Wage Growth":  {"vaerdi": 3.4,  "enhed": "%",  "label": "Avg. Hourly Earnings YoY (May 2026)"},
        # WTI oliepris kollapset: ~$75.5 (18. juni 2026) vs ~$100 i juni 2025 → ca. -24% YoY
        # USA-Iran fredsaftale + IEA-varsel om forsyningsoverskud presser priserne ned
        "Energy":       {"vaerdi": -24.0,"enhed": "%",  "label": "WTI crude oil YoY % (June 18, 2026)"},
        # 10Y US Treasury: 4.49% (17. juni 2026)
        "10 YR":        {"vaerdi": 4.49, "enhed": "%",  "label": "10Y Treasury (June 17, 2026)"},
        # VIX: 16.4 (17. juni 2026 close)
        "VIX":          {"vaerdi": 16.4, "enhed": "",   "label": "VIX (June 17, 2026)"},
        # BLS Unemployment maj 2026: 4.3% (stabilt)
        "Unemployment": {"vaerdi": 4.3,  "enhed": "%",  "label": "Unemployment rate (May 2026)"},
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
    Retail Sales YoY % — coincident forbrugsmål.
    Negativ = recession-signal. 0-2% = svag/late. 2-5% = moderate/early. >5% = mid-cycle styrke.
    Thresholds: nominelle YoY-tal (inkl. inflation), så 5%+ er normalt i moderate inflationsmiljøer.
    """
    if v is None: return None
    if v < 0.0:  return "Recession"  # Negativt = recession/kontraktion
    if v < 2.0:  return "Late"       # Svag vækst — forbrugere presset
    if v < 5.0:  return "Early"      # Moderat vækst
    return "Mid"                      # Solid forbrugsvækst (>5% YoY nominelt)

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
    US potentiel vækst ~2%, Eurozone ~1.5%. Klart over potentiel = Late-signal.
    Tærskel hævet til 3.0% da 2-3% YoY er normalt i mid-cycle, ikke overophedning.
    """
    if v is None: return None
    if v < 0:     return "Recession"
    if v < 0.8:   return "Early"      # Svag men positiv vækst — tidlig recovery
    if v < 3.0:   return "Mid"        # Normal til stærk vækst (0.8-3.0%)
    return "Late"                      # >3% YoY = potentiel overophedning

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

# ── Defensiv stagflations-premium ────────────────────────────────────────────
# Når oliepriserne stiger kraftigt (Energy-indikator = Late ≥ +30% YoY) udløses
# stagflations-regime. Defensiver (Consumer Staples, Health Care, Utilities) og
# råvaresektorer (Materials, Energy) outperformer historisk i dette miljø:
# - Consumer Staples: prisgennemstrømning + inelastisk efterspørgsel + udbytteflow
# - Materials: råvarepriser (kobber, guld, kemi) stiger med energi-commodity-cycle
# - Health Care: defensiv med pricing power (reguleret + innovationsdrevet)
# - Utilities: regulated rate pass-through + inflation-linked tariffer
# - Financials: kreditkvalitets-risiko stiger → NEGATIV premium
# Kilde: BofA/JPM sector rotation frameworks; Fidelity business cycle data.
DEFENSIV_STAGFLATION = {
    "Consumer Staples":  +0.5,   # Pricing power + defensiv tilstrømning
    "Materials":         +0.5,   # Råvare-commodity-correlation
    "Health Care":       +0.3,   # Defensiv + biologics pricing power
    "Utilities":         +0.3,   # Regulerede tariffer + inflation-linkage
    "Financials":        -0.4,   # Kreditkvalitet forringes, margin-squeeze
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
        "Financials":              {"Early":4,"Mid":3,"Late":2,"Recession":1},  # Mid↓: credit losses + reg headwinds
        "Real Estate":             {"Early":3,"Mid":3,"Late":2,"Recession":1},
        "Consumer Discretionary":  {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Information Technology":  {"Early":4,"Mid":5,"Late":3,"Recession":1},  # Early↑: capex recovery
        "Industrials":             {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":4,"Mid":5,"Late":3,"Recession":1},  # Mid↑: peak industriel demand
        "Consumer Staples":        {"Early":2,"Mid":3,"Late":4,"Recession":5},  # Mid↑: pricing power + inelastic demand
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
        "Consumer Staples":        {"Early":2,"Mid":3,"Late":3,"Recession":4},  # Mid↑: defensive pricing power
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":4},
        "Energy":                  {"Early":3,"Mid":3,"Late":4,"Recession":2},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":3},
        "Utilities":               {"Early":1,"Mid":2,"Late":4,"Recession":5},  # Bond-proxy, Early↓
    },
    # ── Retail Sales MoM% (ledende, vægt 2) ──────────────────────────────
    # Direkte forbrugsmål — Consumer Discretionary reagerer mest
    "Retail Sales": {
        "Financials":              {"Early":3,"Mid":3,"Late":2,"Recession":1},  # Mid↓: credit losses
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
        "Financials":              {"Early":4,"Mid":3,"Late":2,"Recession":1},  # Mid↓: credit losses
        "Real Estate":             {"Early":4,"Mid":3,"Late":2,"Recession":1},
        "Consumer Discretionary":  {"Early":5,"Mid":5,"Late":2,"Recession":1},
        "Information Technology":  {"Early":4,"Mid":4,"Late":3,"Recession":1},
        "Industrials":             {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":4,"Mid":4,"Late":2,"Recession":2},  # Mid↑: commodity demand
        "Consumer Staples":        {"Early":2,"Mid":3,"Late":3,"Recession":5},  # Mid↑: inelastic demand
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
        "Financials":              {"Early":4,"Mid":3,"Late":2,"Recession":1},  # Mid↓: credit losses
        "Real Estate":             {"Early":4,"Mid":3,"Late":3,"Recession":1},
        "Consumer Discretionary":  {"Early":5,"Mid":4,"Late":1,"Recession":1},
        "Information Technology":  {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Industrials":             {"Early":5,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":4,"Mid":4,"Late":2,"Recession":2},  # Mid↑: GDP lift for commodities
        "Consumer Staples":        {"Early":2,"Mid":3,"Late":4,"Recession":5},  # Mid↑: inelastic demand
        "Health Care":             {"Early":2,"Mid":3,"Late":3,"Recession":5},
        "Energy":                  {"Early":2,"Mid":3,"Late":5,"Recession":1},
        "Communications Services": {"Early":3,"Mid":4,"Late":3,"Recession":2},
        "Utilities":               {"Early":2,"Mid":2,"Late":4,"Recession":5},
    },
    # ── Lønvækst (samtidig, vægt 2) ───────────────────────────────────────
    # Høj lønvækst gavner Consumer Disc. men presser marginer (Late-signal)
    "Wage Growth": {
        "Financials":              {"Early":3,"Mid":3,"Late":2,"Recession":1},  # Mid↓: margin pressure
        "Real Estate":             {"Early":3,"Mid":3,"Late":2,"Recession":1},
        "Consumer Discretionary":  {"Early":4,"Mid":5,"Late":2,"Recession":1},  # Købekraft topper i Mid
        "Information Technology":  {"Early":4,"Mid":4,"Late":3,"Recession":1},
        "Industrials":             {"Early":4,"Mid":4,"Late":2,"Recession":1},
        "Materials":               {"Early":3,"Mid":4,"Late":3,"Recession":2},  # Mid↑: labor cost pass-through
        "Consumer Staples":        {"Early":2,"Mid":3,"Late":3,"Recession":4},  # Mid↑: pricing power
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
        "Materials":               {"Early":4,"Mid":4,"Late":4,"Recession":2},  # Late↑: commodity price spike
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
        "Financials":              {"Early":4,"Mid":3,"Late":2,"Recession":1},  # Mid↓: volatility hurts trading
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
        "Consumer Staples":        {"Early":2,"Mid":3,"Late":3,"Recession":5},  # Mid↑: employment supports staples spending
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

    # Unemployment — to ark dækker forskellige perioder og lægges sammen:
    # "Arbejdsløshed" (Q1 2024-Q1 2025, % som tal eller tekststreng med komma)
    # og "Unemployment" (Q3 2025- , decimal andel der skal ganges med 100).
    ws = wb["Arbejdsløshed"]
    cur = None
    for row in ws.iter_rows(values_only=True):
        if row[3]=="Kvartal" and isinstance(row[4],str):
            lbl = row[4]
            if "Euroområdet" in lbl or "EU" in lbl: cur="Europa"
            elif "USA" in lbl: cur="USA"
            else: cur=None
            if cur: h.setdefault(cur,{}).setdefault("Unemployment",[])
        elif cur and isinstance(row[3],str) and row[3].startswith("Q"):
            raw = row[4]
            if isinstance(raw,str):
                raw = raw.replace(" ","").replace(" ","").replace(",",".")
                try: raw = float(raw)
                except ValueError: continue
            if isinstance(raw,(int,float)):
                h[cur]["Unemployment"].append({"kvartal":row[3],"vaerdi":round(raw,2)})

    ws = wb["Unemployment"]
    cur = None
    for row in ws.iter_rows(values_only=True):
        if row[3]=="Kvartal" and isinstance(row[4],str):
            cur = row[4] if row[4] in ("Europa","USA") else None
            if cur: h.setdefault(cur,{}).setdefault("Unemployment",[])
        elif cur and isinstance(row[3],str) and row[3].startswith("Q") and isinstance(row[4],(int,float)):
            h[cur]["Unemployment"].append({"kvartal":row[3],"vaerdi":round(row[4]*100,2)})

    return h


def hent_etf_liste(wb):
    ws = wb["ETF - Liste"]
    res = {}
    for row in ws.iter_rows(values_only=True):
        if not row[0] or row[0]=="Kategori": continue
        kategori,navn,isin,region,sektor = (row[i] if len(row)>i else None for i in range(5))
        if navn and sektor:
            res.setdefault(norm(sektor),[]).append({"navn":navn,"isin":isin,"region":region})
    # Patch: udskift/tilføj ETFs der ikke passer til analysen
    res["Communications Services"] = [
        {"navn": "iShares Global Comm Services ETF", "isin": "IE00BMW3QX54", "region": "Global"},
        {"navn": "SPDR MSCI World Communication Services", "isin": "IE00BYTRR863", "region": "Global"},
    ]
    res["Information Technology"] = [
        {"navn": "iShares Global Technology ETF", "isin": "IE00B1XNHC34", "region": "Global"},
        {"navn": "Invesco Nasdaq-100 UCITS (acc)", "isin": "IE00B60SX394", "region": "USA/Global"},
    ]
    res.setdefault("Energy", [])
    if not any(e["isin"] == "IE00B4MW6V84" for e in res.get("Energy", [])):
        res["Energy"].append({"navn": "iShares Oil & Gas Exploration & Production ETF", "isin": "IE00B4MW6V84", "region": "Global"})
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

    # ── Datakvalitet-patches ──────────────────────────────────────────────────
    # Fjern konkurs/fejl-tickers
    FJERN_EU = {"CS"}           # Credit Suisse: konkurs 2023, overtaget af UBS
    FJERN_EU |= {"ENEL"}        # Enel: utilities-selskab, fejlklassificeret som Energy
    FJERN_EU |= {"WLN"}         # Worldline: betalingskrise 2023, -70% fra top
    FJERN_EU |= {"MMO"}         # Ukendt/obsolet ticker
    aktier["Europa"] = [a for a in aktier["Europa"] if a["ticker"] not in FJERN_EU]

    # Fjern Intel + Liberty Global fra USA (strukturelle problemer)
    FJERN_USA = {"INTC", "LBTYA"}
    aktier["USA"] = [a for a in aktier["USA"] if a["ticker"] not in FJERN_USA]

    # Fix: SAN ticker-konflikt — Sanofi (Healthcare) vs Santander (Financials)
    # Beholder Santander i Financials. Erstatter Sanofi med SNY (US-notering) → SAN.PA-logik
    # I praksis: ændrer SAN i Healthcare EU til SNY ticker (Sanofi ADR)
    for a in aktier["Europa"]:
        if a["ticker"] == "SAN" and a["sektor"] == "Health Care":
            a["ticker"] = "SNY"  # Sanofi US ADR / europæisk SAN.PA

    # Tilføj manglende aktier: EU Financials (UBS erstatter CS)
    aktier["Europa"].append({
        "ticker": "UBSG", "sektor": "Financials",
        "market_cap": 98_000_000_000, "market_cap_mia": 98.0,
        "change_pct": None, "pe": 14.5, "beta": 1.05,
    })
    # Tilføj EU Energy korrekte selskaber (olie/gas — ikke ENEL som er utilities)
    aktier["Europa"].append({
        "ticker": "SHEL", "sektor": "Energy",
        "market_cap": 195_000_000_000, "market_cap_mia": 195.0,
        "change_pct": None, "pe": 13.8, "beta": 0.65,
    })
    aktier["Europa"].append({
        "ticker": "BP", "sektor": "Energy",
        "market_cap": 73_000_000_000, "market_cap_mia": 73.0,
        "change_pct": None, "pe": 10.2, "beta": 0.71,
    })

    # Tilføj manglende USA Materials
    for t, mc, pe, beta in [
        ("LIN", 195_000_000_000, 30.5, 0.74),   # Linde (gasser)
        ("FCX",  65_000_000_000, 18.2, 1.85),   # Freeport McMoRan (kobber)
        ("NEM",  50_000_000_000, 22.1, 0.63),   # Newmont (guld)
        ("APD",  54_000_000_000, 26.4, 0.85),   # Air Products
    ]:
        aktier["USA"].append({
            "ticker": t, "sektor": "Materials",
            "market_cap": mc, "market_cap_mia": round(mc/1e9,1),
            "change_pct": None, "pe": pe, "beta": beta,
        })

    # Tilføj manglende USA Utilities
    for t, mc, pe, beta in [
        ("NEE",  99_000_000_000, 21.4, 0.62),   # NextEra Energy (sol/vind + reguleret)
        ("DUK",  76_000_000_000, 18.9, 0.55),   # Duke Energy
        ("SO",   93_000_000_000, 19.8, 0.50),   # Southern Company
    ]:
        aktier["USA"].append({
            "ticker": t, "sektor": "Utilities",
            "market_cap": mc, "market_cap_mia": round(mc/1e9,1),
            "change_pct": None, "pe": pe, "beta": beta,
        })

    # Tilføj AMD som erstatning for INTC i USA IT
    aktier["USA"].append({
        "ticker": "AMD", "sektor": "Information Technology",
        "market_cap": 220_000_000_000, "market_cap_mia": 220.0,
        "change_pct": None, "pe": 35.2, "beta": 1.72,
    })

    # Tilføj ASML til EU IT — Europas største tech/halvleder-aktie
    aktier["Europa"].append({
        "ticker": "ASML", "sektor": "Information Technology",
        "market_cap": 270_000_000_000, "market_cap_mia": 270.0,
        "change_pct": None, "pe": 32.5, "beta": 1.38,
    })

    # Tilføj ENEL til EU Utilities (var fejlagtigt i Energy)
    aktier["Europa"].append({
        "ticker": "ENEL", "sektor": "Utilities",
        "market_cap": 68_000_000_000, "market_cap_mia": 68.0,
        "change_pct": None, "pe": 11.8, "beta": 0.72,
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

# Pillar-definitioner — bruges også i momentum-beregning.
# Indikator-grupperingen pr. pillar er ens for begge regioner; det er VÆGTEN
# (fra INDIKATOR_VAEGTER_REGION) der gør pillarene region-specifikke.
_PILLAR_GROUPS = {
    "Growth":    ["PMI", "BNP", "Retail Sales"],
    "Labor":     ["NFP", "Wage Growth", "Unemployment"],
    "Inflation": ["Core CPI", "Energy"],
    "Financial": ["Yield Curve", "10 YR", "VIX"],
}

def _pillar_inds(region):
    """Region-specifikke (indikator, vægt)-lister pr. pillar."""
    return {p: [(ind, vaegt(ind, region)) for ind in inds]
            for p, inds in _PILLAR_GROUPS.items()}

def _fase_fra_inputs(v, region):
    """Beregn per-indikator faser fra et input-dict. Intern hjælper."""
    return {
        "PMI":          fase_pmi(v.get("PMI")),
        "Yield Curve":  fase_yield_curve(v.get("Yield Curve")),
        "Retail Sales": fase_retail_sales(v.get("Retail Sales")),
        "NFP":          fase_nfp(v.get("NFP"), region),
        "Core CPI":     fase_core_cpi(v.get("Core CPI")),
        "BNP":          fase_bnp(v.get("BNP")),
        "Wage Growth":  fase_wage_growth(v.get("Wage Growth")),
        "Energy":       fase_energy(v.get("Energy")),
        "10 YR":        fase_rente(v.get("10 YR"), region),
        "VIX":          fase_vix(v.get("VIX")),
        "Unemployment": fase_unemployment(v.get("Unemployment")),
    }

def _pillar(faser, inds_weights):
    """Vægtet pillar-score (0-3) fra et faser-dict."""
    s, w = 0, 0
    for ind, wt in inds_weights:
        f = faser.get(ind)
        if f: s += _FASE_SCORE[f] * wt; w += wt
    return s / w if w else 1.5

def klassificer_makro(region_inputs, region="USA", prev_inputs=None):
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

    # ── Pillar-aggregering (region-specifik vægtning) ───────────────────────
    pillar_inds = _pillar_inds(region)
    growth_p = _pillar(faser, pillar_inds["Growth"])
    labor_p  = _pillar(faser, pillar_inds["Labor"])
    infl_p   = _pillar(faser, pillar_inds["Inflation"])
    fin_p    = _pillar(faser, pillar_inds["Financial"])

    # ── Momentum-justering (hvis forrige periode er tilgængelig) ─────────────
    # Princip: 70% niveau + 30% retning/acceleration.
    # En PMI der stiger fra 48→52 = Early i niveau, men momentum er positiv
    # → pillar-score justeres op, rykker fasebeslutningen mod det bedre.
    # Cap på ±0.5 per pillar for at undgå single-period outliers dominerer.
    momentum_adj = {}
    if prev_inputs:
        pf = _fase_fra_inputs(prev_inputs, region)
        pg = _pillar(pf, pillar_inds["Growth"])
        pl = _pillar(pf, pillar_inds["Labor"])
        pi = _pillar(pf, pillar_inds["Inflation"])
        pn = _pillar(pf, pillar_inds["Financial"])
        MCLIP = 0.5
        def m(cur, prv): return max(-MCLIP, min(MCLIP, (cur - prv) * 0.4))
        mg = m(growth_p, pg); ml = m(labor_p, pl)
        mi = m(infl_p, pi);   mf = m(fin_p, pn)
        growth_p += mg; labor_p += ml; infl_p += mi; fin_p += mf
        momentum_adj = {"Growth": round(mg,2), "Labor": round(ml,2),
                        "Inflation": round(mi,2), "Financial": round(mf,2)}

    # ── Pillar-baseret fasebeslutning (prioriteret rækkefølge) ──────────────
    # Recession: klart growth-kollaps
    if growth_p < 0.8 or (growth_p < 1.3 and labor_p < 0.8):
        global_fase = "Recession"
    # Late (stagflation/energichok): høj inflation + svag vækst — fanger supply-chok
    # Eksempel: Europa 2022 (energikrise), 2026 (Mellemøsten-krise).
    # infl_p > 2.3 = klart over neutrale niveauer på 0-3 skalaen.
    elif infl_p > 2.3 and growth_p < 1.8:
        global_fase = "Late"
    # Late (inflation-drevet): overhedning + finansiel stramning + aftagende vækst
    elif infl_p <= 1.5 and fin_p < 1.8 and growth_p < 2.0:
        global_fase = "Late"
    # Late (finansiel stramning): stramme finansielle forhold + ikke-accelererende vækst.
    # Fanger 2018/2019-type cykler: inverteret/flat yield curve + Fed-hikes
    elif fin_p < 1.8 and growth_p < 2.3:
        global_fase = "Late"
    # Mid: stærk vækst + solidt arbejdsmarked
    elif growth_p >= 2.2 and labor_p >= 2.0:
        global_fase = "Mid"
    # Early: recovery — alt andet
    else:
        global_fase = "Early"

    # ── Afstemning bevares til fase_pct UI-visning ──────────────────────────
    point = {"Early":0,"Mid":0,"Late":0,"Recession":0}
    for ind, fase in faser.items():
        if fase and not ind.startswith("_"):
            point[fase] += vaegt(ind, region)
    total = sum(point.values())

    faser["_global"]   = global_fase
    faser["_point"]    = point
    faser["_pct"]      = {f: round(p/total*100) for f,p in point.items()} if total else {}
    faser["_pillars"]  = {"Growth": round(growth_p,2), "Labor": round(labor_p,2),
                          "Inflation": round(infl_p,2), "Financial": round(fin_p,2),
                          "_momentum": momentum_adj}
    return faser


def _pct(raw):
    """Omregn decimal til procent (0.019 → 1.9) hvis nødvendigt."""
    if raw is None: return None
    return round(raw * 100, 2) if abs(raw) < 1 else round(raw, 2)

def beregn_makrofase(seneste_makro):
    """
    Beregn global makrofase fra seneste makrodata (DEFAULT_MAKRO / live / Excel).
    seneste_makro: {region: {indikator: {vaerdi, enhed, label, kilde}}}
    """
    global_point = {"Early":0,"Mid":0,"Late":0,"Recession":0}
    detaljer = []

    for region in ("Europa", "USA"):
        reg_data = seneste_makro.get(region, {})
        inputs = {ind: reg_data.get(ind, {}).get("vaerdi") for ind in INDIKATORER}

        faser = klassificer_makro(inputs, region)
        for f, pts in faser["_point"].items():
            global_point[f] += pts

        ind_liste = []
        for ind in INDIKATORER:
            val = inputs.get(ind)
            meta = reg_data.get(ind, {})
            enhed = meta.get("enhed", "")
            kilde = meta.get("kilde", "estimat")
            if isinstance(val, float): vis = f"{val:.2f}"
            elif val is not None: vis = str(val)
            else: vis = "N/A"
            if enhed: vis += enhed
            ind_liste.append({
                "navn": ind, "vaerdi": vis,
                "fase": faser.get(ind),
                "vaegt": vaegt(ind, region),
                "type": INDIKATOR_TYPE.get(ind, ""),
                "kilde": kilde,
            })

        r_titel, r_beskr, r_ikon, r_farve = FASE_META.get(faser["_global"], ("?","","❓","#fff"))
        detaljer.append({
            "region": region, "fase": faser["_global"],
            "titel": r_titel, "beskrivelse": r_beskr, "ikon": r_ikon, "farve": r_farve,
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
                    w = vaegt(ind, region)
                    vaegtet_sum += s * w
                    vaegt_sum += w
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


def _hent_live_historisk_indikatorer(kvartaler):
    """Forsøg at hente rigtige FRED/ECB-historiske indikatorer (se live_data.py).
    Tom dict ved manglende FRED_API_KEY/netværk — kalderen falder da tilbage til
    de Excel-baserede historiske ark."""
    try:
        from live_data import hent_historisk_indikatorer
        return hent_historisk_indikatorer(kvartaler)
    except Exception as e:
        import logging; logging.getLogger(__name__).warning(f"live historisk indikator-hentning fejl: {e}")
        return {}


def _model_faser_for_kvartal(kv, region, historik, fremtid, live_hist=None):
    """
    Indikator-input til klassificer_makro for ét kvartal/én region. Live
    FRED/ECB-tal (live_hist, se hent_historisk_indikatorer) har FØRSTE prioritet
    per indikator/kvartal — de er rigtige tal, ikke estimater. Excel-arkene
    bruges som fallback for indikatorer/kvartaler hvor live-data ikke fandtes:
      - KVARTALER_HIST (Q1 2024-Q4 2025): de historiske Excel-ark
        (PMI, 10 yr rate, CPI, VIX, Unemployment) — 5 indikatorer, og
        Unemployment har et hul i Q2 2025 (ingen data i kildearkene).
      - KVARTALER_Q1Q2_2026: "Fremtid vækst"-arkets q1/q2-kolonner —
        6 indikatorer tilgængelige (+ BNP).
    Returnerer en klassificeret fase-dict, eller None hvis ingen data fandtes.
    """
    inputs = {}
    live_region = (live_hist or {}).get(region, {})
    for ind, serie in live_region.items():
        val = serie.get(kv)
        if val is not None:
            inputs[ind] = val

    for ind, excel_key in _HIST_IND_KEYS.items():
        if ind in inputs:
            continue
        serie = historik.get(region, {}).get(excel_key, [])
        entry = next((e for e in serie if e.get("kvartal") == kv), None)
        if entry and isinstance(entry.get("vaerdi"), (int, float)):
            inputs[ind] = entry["vaerdi"]

    if not inputs:
        kol = {"Q1 2026": "q1", "Q2 2026": "q2"}.get(kv)
        if kol:
            for excel_key, ind in _FREMTID_NAVNE.items():
                serie = fremtid.get(region, {}).get(excel_key)
                if not serie:
                    continue
                val = serie.get(kol)
                if val is None:
                    continue
                if ind in _PROCENT_INDS and abs(val) < 1:
                    val = round(val * 100, 2)
                inputs[ind] = val

    if not inputs:
        return None
    return klassificer_makro(inputs, region)


def _model_score_kvartal(kv, historik, fremtid, live_hist=None):
    """{sektor: score} for ét kvartal — gennemsnit af Europa+USA, beregnet med
    klassificer_makro + _score_sektor_region. Samme metode for alle kvartaler,
    uanset om input kommer fra live FRED/ECB-data, historik-arkene eller
    Fremtid vækst-arket."""
    region_scores = {sektor: [] for sektor in SEKTOR_RÆKKEFØLGE}
    for region in ("Europa", "USA"):
        faser = _model_faser_for_kvartal(kv, region, historik, fremtid, live_hist)
        if faser is None:
            continue
        for sektor in SEKTOR_RÆKKEFØLGE:
            sc = _score_sektor_region(sektor, region, faser)
            if sc is not None:
                region_scores[sektor].append(sc)
    return {s: round(sum(v) / len(v), 2) for s, v in region_scores.items() if v}


def model_historisk_sektorer(wb):
    """
    Beregn sektorscorer for alle afsluttede kvartaler (Q1 2024 - Q2 2026) med
    PRÆCIS samme metode som det aktuelle/projekterede kvartal:
    klassificer_makro + _score_sektor_region på rå indikatorværdier, IKKE det
    manuelt tildelte "Point score sektor"-ark.

    Indikator-kilder, i prioriteret orden: rigtige FRED/ECB-tal (hvis
    FRED_API_KEY/netværk er tilgængeligt — se hent_historisk_indikatorer i
    live_data.py, op til 9-10 indikatorer for USA og 5 for Europa), dernæst
    Excel-arkene som fallback (5 for Q1 2024-Q4 2025, 6 for Q1+Q2 2026).
    Modellen anvendes derfor potentielt på et tyndere datagrundlag for fortiden
    end for nutiden, men beregningsmetoden er ens.

    Returnerer {sektor: {kvartal: score}} — gennemsnit af Europa+USA.
    """
    historik = hent_historisk_makro(wb)
    fremtid = hent_fremtid_vaekst(wb)
    kvartaler = KVARTALER_HIST + KVARTALER_Q1Q2_2026
    live_hist = _hent_live_historisk_indikatorer(kvartaler)
    resultat = {sektor: {} for sektor in SEKTOR_RÆKKEFØLGE}

    for kv in kvartaler:
        for sektor, score in _model_score_kvartal(kv, historik, fremtid, live_hist).items():
            resultat[sektor][kv] = score

    return resultat


def byg_heatmap(model_historisk, sim_scores):
    """
    Byg multi-kvartal heatmap data.
    model_historisk: {sektor: {kvartal: score}} — fra model_historisk_sektorer(),
                      samme beregningsmetode som de projekterede kvartaler.
    sim_scores: {sektor: score} — fra simuler_sektorer(), bruges til projekterede kvartaler
    Returnerer: {sektor: {kvartal: {'score': float, 'kilde': str}}}
    """
    heatmap = {}

    for sektor in SEKTOR_RÆKKEFØLGE:
        heatmap[sektor] = {}

        # Afsluttede kvartaler (historik + Q1/Q2 2026) — model-beregnet, samme metode som prognosen
        hist_data = model_historisk.get(sektor, {})
        for kv in KVARTALER_HIST + KVARTALER_Q1Q2_2026:
            score = hist_data.get(kv)
            if score is not None:
                heatmap[sektor][kv] = {"score": score, "kilde": "historisk"}

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
            w = vaegt(ind, region)
            vs += s * w; vv += w
    if vv == 0: return None
    base = vs / vv

    # Energiafhængighedsjustering (aktiv når Energy-indikatoren = Mid eller Late)
    energy_fase = f.get("Energy")
    if energy_fase in ("Mid", "Late"):
        adj = ENERGI_AFHAENGIGHED.get(region, {}).get(sektor, {}).get(energy_fase, 0)
        base += adj

    # Defensiv stagflations-premium (aktiv kun ved kraftigt energichok = Energy Late)
    # Fanger defensiv rotation og råvare-commodity-cycle i stagflations-regime.
    if energy_fase == "Late":
        base += DEFENSIV_STAGFLATION.get(sektor, 0)

    # USA's strukturelle AI-fordel (aktiv i alle faser, stærkest i Early/Mid)
    if region == "USA":
        global_fase = f.get("_global", "Mid")
        base += AI_FORDEL_USA.get(sektor, {}).get(global_fase, 0)

    return round(max(1.0, min(5.0, base)), 2)


def simuler_sektorer(makro_inputs, prev_inputs=None):
    """
    Simuler sektorscorer fra bruger-definerede makroværdier.
    makro_inputs: {region: {indikator: vaerdi}}
    prev_inputs:  {region: {indikator: vaerdi}} — forrige periode (til momentum)
    """
    # Beregn fase per region
    faser = {}
    for region, inputs in makro_inputs.items():
        prev = (prev_inputs or {}).get(region)
        f = klassificer_makro(inputs, region, prev_inputs=prev)
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

    pillars = {r: f.get("_pillars", {}) for r, f in faser.items()}
    return {"sektorer": resultater, "fase": global_fase,
            "fase_meta": FASE_META.get(global_fase,{}),
            "faser": {r: f["_global"] for r,f in faser.items()},
            "pillars": pillars}


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
                w = vaegt(ind, region)
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
                adjs.append({"label": f"Energy dependency ({region})", "delta": round(delta, 2)})
        if energy_fase == "Late":
            delta = DEFENSIV_STAGFLATION.get(sektor, 0)
            if delta != 0:
                adjs.append({"label": "Stagflation premium (energy shock)", "delta": round(delta, 2)})
        if region == "USA":
            global_fase = f.get("_global", "Mid")
            delta = AI_FORDEL_USA.get(sektor, {}).get(global_fase, 0)
            if delta != 0:
                adjs.append({"label": "USA AI structural advantage", "delta": round(delta, 2)})
        justeringer[region] = adjs

    return {"regioner": result, "totals": totals, "justeringer": justeringer}


# ── Backtest / model-validering ───────────────────────────────────────────────
# Sammenligner modellens sektor-ranking mod realiserede sektorscorer (fra BNP-
# arket) per historisk kvartal, via Spearman rangkorrelation. Begrænset til de
# indikatorer der findes historisk (PMI, 10 YR, Core CPI [kun Europa], VIX) —
# ikke det fulde 11-indikator-sæt, så resultatet er en tilnærmelse, ikke en
# eksakt replay af det live model-output.

_HIST_IND_KEYS = {"PMI": "PMI", "10 YR": "10yr", "Core CPI": "CPI", "VIX": "VIX",
                   "Unemployment": "Unemployment"}

def _rang(vaerdier):
    rang = [0] * len(vaerdier)
    for r, i in enumerate(sorted(range(len(vaerdier)), key=lambda i: vaerdier[i])):
        rang[i] = r + 1
    return rang

def _spearman(a, b):
    n = len(a)
    if n < 3:
        return None
    ra, rb = _rang(a), _rang(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((x - mb) ** 2 for x in rb)
    if va == 0 or vb == 0:
        return None
    return round(cov / (va * vb) ** 0.5, 3)

def backtest_model(wb, sektor_afkast_live=None):
    """
    Backtest: for hvert afsluttet kvartal (Q1 2024–Q2 2026), beregn modellens
    sektorscore (baseret på tilgængelige indikatorer for kvartalet) og
    sammenlign rang mod realiseret sektorperformance — PER REGION, ikke
    blandet sammen.

    Vigtigt: Europa og USA sammenlignes hver for sig, fordi deres ground truth
    har forskellige enheder (USA: faktisk ETF-afkast i %, Europa: manuelt
    1-5 point-score). At gennemsnitte dem sammen ville producere en
    meningsløs "realiseret"-værdi. I stedet beregnes en Spearman-korrelation
    for hver region for sig, og kvartalets samlede korrelation er
    gennemsnittet af de regioner der har nok datapunkter (≥3 sektorer).

    Q1+Q2 2026 indgår nu også som rigtige (afsluttede) valideringskvartaler —
    modelinput hentes fra "Fremtid vækst"-arket i stedet for historik-arkene
    (se _model_faser_for_kvartal). De har ingen Point-score-fallback (det
    arket dækker kun Q1 2024-Q4 2025), så de bidrager kun til backtesten når
    live ETF-afkast kan hentes.

    Ground truth pr. region (sektor_afkast_live: {region: {sektor: {kvartal: pct}}}):
      USA:    SPDR Select Sector-ETF'er (Stooq) — verificerede tickers, ægte marked.
      Europa: iShares STOXX 600-sektor-UCITS-ETF'er (Stooq) — tickers IKKE
              verificeret i sandbox, se note i live_data.SEKTOR_ETF_EUROPA.
      Begge regioner falder tilbage til Point-score-arket (BNP-fanen i Excel,
      et manuelt ekspertskøn, ikke faktiske afkast) hvis live-data ikke kan
      hentes for en given sektor/kvartal (kun muligt for Q1 2024-Q4 2025).

    "Frosne" kvartaler: Point-score-arket har flere kvartaler i træk med
    BOGSTAVELIGT identiske sektor-scorer per region (sandsynligvis ikke
    genvurderet, blot kopieret fra forrige kvartal). At sammenligne modellen
    mod uændret ground truth tester ikke noget reelt, så sådanne
    region/kvartal-kombinationer markeres "frosset": true og udelades fra
    både kvartalets og det samlede gennemsnits korrelation (selve tallet vises
    stadig, til diagnostik).
    """
    historik = hent_historisk_makro(wb)
    historisk_bnp = hent_historisk_bnp(wb)
    fremtid = hent_fremtid_vaekst(wb)
    sektor_afkast_live = sektor_afkast_live or {}
    kvartaler = KVARTALER_HIST + KVARTALER_Q1Q2_2026
    live_hist = _hent_live_historisk_indikatorer(kvartaler)

    rows = []
    prev_realized = {}
    for kv in kvartaler:
        region_resultater = {}

        for region in ("Europa", "USA"):
            faser = _model_faser_for_kvartal(kv, region, historik, fremtid, live_hist)
            if faser is None:
                continue

            model_per_sektor = {}
            realized_per_sektor = {}
            kilde = "point_score_estimat"
            live_region = sektor_afkast_live.get(region, {})

            for sektor in SEKTOR_RÆKKEFØLGE:
                sc = _score_sektor_region(sektor, region, faser)
                if sc is not None:
                    model_per_sektor[sektor] = sc

                live_afkast = live_region.get(sektor, {}).get(kv)
                if live_afkast is not None:
                    realized_per_sektor[sektor] = live_afkast
                    kilde = "live_etf"
                else:
                    realiseret = historisk_bnp.get(sektor, {}).get(kv, {}).get(region)
                    if isinstance(realiseret, (int, float)):
                        realized_per_sektor[sektor] = realiseret

            faelles = sorted(set(model_per_sektor) & set(realized_per_sektor))
            if len(faelles) < 3:
                continue
            model_vals = [model_per_sektor[s] for s in faelles]
            realized_vals = [realized_per_sektor[s] for s in faelles]
            korr = _spearman(model_vals, realized_vals)

            frosset = (kilde == "point_score_estimat" and
                       prev_realized.get(region) == realized_per_sektor)
            if kilde == "point_score_estimat":
                prev_realized[region] = realized_per_sektor

            region_resultater[region] = {
                "korrelation": korr, "antal_sektorer": len(faelles),
                "kilde": kilde, "frosset": frosset,
            }

        korr_vals = [r["korrelation"] for r in region_resultater.values()
                     if r["korrelation"] is not None and not r["frosset"]]
        korr_kvartal = round(sum(korr_vals) / len(korr_vals), 3) if korr_vals else None
        rows.append({
            "kvartal": kv,
            "korrelation": korr_kvartal,
            "regioner": region_resultater,
        })

    gyldige = [r["korrelation"] for r in rows if r["korrelation"] is not None]
    gennemsnit = round(sum(gyldige) / len(gyldige), 3) if gyldige else None
    live_andel = sum(
        1 for r in rows
        if any(reg.get("kilde") == "live_etf" for reg in r["regioner"].values())
    )

    return {"kvartaler": rows, "gennemsnit": gennemsnit,
            "live_data_brugt": live_andel > 0, "antal_kvartaler_live": live_andel}


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
    Prioritet: DEFAULT_MAKRO (manuelt opdateret med aktuelle tal) > FRED/ECB live (via flet_med_default).
    Excel Fremtid-arket bruges KUN til prev_vaerdi (Q1-historik til momentumberegning).
    DEFAULT_MAKRO er altid den primære kilde, da det opdateres med ægte makrodata.
    """
    result = {}
    for region in ("Europa", "USA"):
        excel_data = fremtid.get(region, {})
        dflt = DEFAULT_MAKRO.get(region, {})
        result[region] = {}

        for ind_key, ind_meta in dflt.items():
            excel_key = next((k for k, v in _FREMTID_NAVNE.items() if v == ind_key), None)

            # Primær kilde: DEFAULT_MAKRO (opdateret med ægte juni 2026-data)
            raw = ind_meta.get("vaerdi", 0)

            # Excel Q1-data bruges KUN til momentum (prev_vaerdi), ikke som primær kilde
            prev_raw = None
            if excel_key and excel_key in excel_data:
                prev_raw = excel_data[excel_key].get("q1")
                if prev_raw is not None:
                    if ind_key in _PROCENT_INDS and abs(prev_raw) < 1:
                        prev_raw = round(prev_raw * 100, 2)
                    else:
                        prev_raw = round(float(prev_raw), 4)

            result[region][ind_key] = {**ind_meta, "vaerdi": raw, "prev_vaerdi": prev_raw, "kilde": "estimat"}

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

    makro_fase     = beregn_makrofase(seneste_makro)

    # Brug samme algoritme som "Mine forventninger" så tallene stemmer overens
    sim_inputs = {r: {k: v["vaerdi"] for k, v in inds.items()}
                  for r, inds in seneste_makro.items()}
    # Byg prev_inputs til momentum-beregning (q1 data fra Excel)
    prev_inputs = {}
    for r, inds in seneste_makro.items():
        prev_r = {k: v["prev_vaerdi"] for k, v in inds.items() if v.get("prev_vaerdi") is not None}
        if prev_r:
            prev_inputs[r] = prev_r
    sim_result = simuler_sektorer(sim_inputs, prev_inputs if prev_inputs else None)
    sektorer = sim_result["sektorer"]

    for s in sektorer:
        rs = s.pop("region_scores", {})
        s["eu"]  = rs.get("Europa", None)
        s["usa"] = rs.get("USA", None)
        s["composite"] = s["score"]

    # Byg sim_scores lookup til heatmap projection: {sektor: score}
    sim_scores_map = {s["sektor"]: s["score"] for s in sektorer}
    model_historisk = model_historisk_sektorer(wb)
    heatmap = byg_heatmap(model_historisk, sim_scores_map)

    # Seneste kvartal med data
    seneste_kvartal = ALLE_KVARTALER[-1]
    for kv in reversed(ALLE_KVARTALER):
        if any(kv in heatmap.get(s["sektor"], {}) for s in sektorer):
            seneste_kvartal = kv
            break

    return {
        "makro_fase":      makro_fase,
        "sektorer":        sektorer,
        "pillars":         sim_result.get("pillars", {}),
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
        "indikator_vaegter": INDIKATOR_VAEGTER_REGION,
        "default_makro":   DEFAULT_MAKRO,
        "seneste_makro":   seneste_makro,
        "seneste_kvartal": seneste_kvartal,
        "opdateret":       datetime.now().strftime("%d.%m.%Y %H:%M"),
        "data_kvartal":    seneste_kvartal,
    }
