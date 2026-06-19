"""
live_data.py — Automatisk hentning af makrodata fra FRED (USA) og ECB SDW (Europa).

FRED API (gratis): https://fred.stlouisfed.org/docs/api/fred/
  - Kræver API-nøgle: sæt env-variabel FRED_API_KEY
  - Gratis nøgle: https://fred.stlouisfed.org/docs/api/api_key.html

ECB SDW API (gratis, ingen nøgle): https://data-api.ecb.europa.eu

Fallback til DEFAULT_MAKRO hvis API'er fejler eller mangler nøgle.
"""

import os, time, logging
from datetime import datetime, timedelta
from functools import lru_cache

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

logger = logging.getLogger(__name__)

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_BASE    = "https://api.stlouisfed.org/fred/series/observations"
ECB_BASE     = "https://data-api.ecb.europa.eu/service/data"

_cache = {}
_cache_ttl = 3600 * 6  # Genopfrisk hver 6. time


# ── FRED helpers ──────────────────────────────────────────────────────────────

def _fred(series_id, limit=13):
    """Hent seneste N observationer fra FRED. Returnerer liste af (dato, float)."""
    if not FRED_API_KEY or not REQUESTS_OK:
        return []
    key = f"fred_{series_id}"
    if key in _cache and time.time() - _cache[key][0] < _cache_ttl:
        return _cache[key][1]
    try:
        r = requests.get(FRED_BASE, params={
            "series_id": series_id, "api_key": FRED_API_KEY,
            "file_type": "json", "sort_order": "desc", "limit": limit,
        }, timeout=8)
        obs = [(o["date"], float(o["value"])) for o in r.json().get("observations", [])
               if o["value"] != "."]
        _cache[key] = (time.time(), obs)
        return obs
    except Exception as e:
        logger.warning(f"FRED {series_id}: {e}")
        return []


def _fred_latest(series_id):
    obs = _fred(series_id, limit=2)
    return obs[0][1] if obs else None


def _fred_yoy(series_id):
    """YoY% ændring: seneste vs. 12 måneder siden."""
    obs = _fred(series_id, limit=14)
    if len(obs) < 13: return None
    now, then = obs[0][1], obs[12][1]
    if then == 0: return None
    return round((now - then) / abs(then) * 100, 2)


def _fred_nfp_change():
    """NFP månedlig ændring (tusinde jobs)."""
    obs = _fred("PAYEMS", limit=2)
    if len(obs) < 2: return None
    return round((obs[0][1] - obs[1][1]), 1)


def _fred_gdp_yoy():
    """BNP YoY% — FRED har kvartalsvise niveauer."""
    obs = _fred("GDPC1", limit=6)
    if len(obs) < 5: return None
    return round((obs[0][1] - obs[4][1]) / obs[4][1] * 100, 2)


# ── ECB SDW helpers ───────────────────────────────────────────────────────────

def _ecb(flow, key, limit=14):
    """Hent tidsserie fra ECB SDW REST API."""
    if not REQUESTS_OK:
        return []
    cache_key = f"ecb_{flow}_{key}"
    if cache_key in _cache and time.time() - _cache[cache_key][0] < _cache_ttl:
        return _cache[cache_key][1]
    try:
        url = f"{ECB_BASE}/{flow}/{key}?lastNObservations={limit}&format=jsondata"
        r = requests.get(url, timeout=8, headers={"Accept": "application/json"})
        data = r.json()
        series = list(data["dataSets"][0]["series"].values())[0]["observations"]
        periods = data["structure"]["dimensions"]["observation"][0]["values"]
        obs = [(periods[int(k)]["id"], float(v[0])) for k, v in sorted(series.items(), reverse=True)]
        _cache[cache_key] = (time.time(), obs)
        return obs
    except Exception as e:
        logger.warning(f"ECB {flow}/{key}: {e}")
        return []


def _ecb_latest(flow, key):
    obs = _ecb(flow, key, limit=2)
    return obs[0][1] if obs else None


def _ecb_yoy(flow, key):
    obs = _ecb(flow, key, limit=14)
    if len(obs) < 13: return None
    now, then = obs[0][1], obs[12][1]
    if then == 0: return None
    return round((now - then) / abs(then) * 100, 2)


# ── Hent live makrodata ───────────────────────────────────────────────────────

def hent_live_makro():
    """
    Returnerer {region: {indikator: vaerdi}} med live data.
    Felter der ikke kunne hentes returneres som None og filtreres ud
    i kalderen, som derefter falder tilbage på DEFAULT_MAKRO.
    """
    if not REQUESTS_OK:
        logger.info("requests ikke tilgængeligt — bruger DEFAULT_MAKRO")
        return {}

    usa = {}
    eu  = {}

    # ── USA (FRED) ────────────────────────────────────────────────────────────

    # PMI — ISM Manufacturing (NAPM på FRED = historisk serie, ny er MANEMP-adj.)
    # Bruger Institute for Supply Management composite: NMFCI eller BSXDIFP
    pmi_usa = _fred_latest("NAPM")      # ISM Manufacturing PMI
    if pmi_usa: usa["PMI"] = round(pmi_usa, 1)

    # Yield Curve 10Y-2Y (%)
    r10 = _fred_latest("GS10")
    r2  = _fred_latest("GS2")
    if r10 and r2: usa["Yield Curve"] = round(r10 - r2, 2)

    # NFP månedlig ændring (tusinde)
    nfp = _fred_nfp_change()
    if nfp is not None: usa["NFP"] = nfp

    # Core CPI YoY% (ex. food & energy)
    core_cpi = _fred_yoy("CPILFESL")
    if core_cpi: usa["Core CPI"] = core_cpi

    # BNP vækst YoY% (real GDP)
    gdp = _fred_gdp_yoy()
    if gdp: usa["BNP"] = gdp

    # Løn-vækst YoY% (Average Hourly Earnings, alle ansatte)
    wage = _fred_yoy("CES0500000003")
    if wage: usa["Wage Growth"] = wage

    # Retail Sales YoY% (advance retail & food services)
    retail = _fred_yoy("RSXFS")
    if retail: usa["Retail Sales"] = retail

    # Energi — WTI råolie YoY%
    energy_yoy = _fred_yoy("DCOILWTICO")
    if energy_yoy: usa["Energy"] = energy_yoy

    # 10YR rente absolut
    if r10: usa["10 YR"] = round(r10, 2)

    # VIX
    vix = _fred_latest("VIXCLS")
    if vix: usa["VIX"] = round(vix, 1)

    # Arbejdsløshed %
    unemp = _fred_latest("UNRATE")
    if unemp: usa["Unemployment"] = round(unemp, 1)

    # ── Europa (ECB SDW) ──────────────────────────────────────────────────────

    # PMI Europa — ikke tilgængeligt på ECB/Eurostat (proprietær S&P Global data)
    # Lader DEFAULT_MAKRO håndtere dette

    # Yield Curve 10Y (ECB AAA government bonds) minus 2Y
    r10_eu = _ecb_latest("YC", "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y")
    r2_eu  = _ecb_latest("YC", "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y")
    if r10_eu and r2_eu: eu["Yield Curve"] = round(r10_eu - r2_eu, 2)

    # Core HICP inflation YoY (ex energi, mad, alkohol, tobak)
    core_hicp = _ecb_latest("ICP", "M.U2.N.XEF000.4.ANR")
    if core_hicp: eu["Core CPI"] = round(core_hicp, 2)

    # Eurozone arbejdsløshed %
    unemp_eu = _ecb_latest("STS", "M.I8.S.UNEH.RTT000.4.000")
    if unemp_eu: eu["Unemployment"] = round(unemp_eu, 1)

    # 10YR Eurozone (ECB benchmark)
    if r10_eu: eu["10 YR"] = round(r10_eu, 2)

    # Energi — HICP energikomponent YoY% som proxy
    energy_eu = _ecb_latest("ICP", "M.U2.N.NRG000.4.ANR")
    if energy_eu: eu["Energy"] = round(energy_eu, 1)

    # VIX bruges for begge regioner (global risikosignal)
    if vix: eu["VIX"] = round(vix, 1)

    logger.info(f"Live makrodata hentet: USA={list(usa.keys())} EU={list(eu.keys())}")
    return {"USA": usa, "Europa": eu}


# ── Sektor-ETF historiske afkast (Stooq, gratis, ingen nøgle) ─────────────────
# Bruges som ÆGTE ground truth i model-backtesten (se data.backtest_model),
# i stedet for det manuelt tildelte "Point score sektor"-ark i Excel-filen.
# Kun USA har verificerede, likvide sektor-ETF-tickers (SPDR Select Sector).
# Europa har ikke et tilsvarende robust ETF-sæt med pålidelige tickers på Stooq,
# så Europa falder fortsat tilbage til Point-score-arket i backtesten.

STOOQ_BASE = "https://stooq.com/q/d/l/"

SEKTOR_ETF_USA = {
    "Information Technology":  "xlk.us",
    "Communications Services": "xlc.us",
    "Industrials":              "xli.us",
    "Financials":                "xlf.us",
    "Consumer Discretionary":  "xly.us",
    "Energy":                    "xle.us",
    "Health Care":                "xlv.us",
    "Real Estate":              "xlre.us",
    "Consumer Staples":          "xlp.us",
    "Materials":                  "xlb.us",
    "Utilities":                  "xlu.us",
}

def _stooq_quarterly(ticker):
    """Hent kvartalsvise lukkekurser for en ticker fra Stooq. Gratis, ingen API-nøgle."""
    if not REQUESTS_OK:
        return []
    cache_key = f"stooq_{ticker}"
    if cache_key in _cache and time.time() - _cache[cache_key][0] < _cache_ttl:
        return _cache[cache_key][1]
    try:
        r = requests.get(
            STOOQ_BASE, params={"s": ticker, "i": "q"}, timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MakroinvestorBot/1.0)"},
        )
        lines = r.text.strip().splitlines()
        # Stooq svarer med en fejl-side ("Exceeded the daily hits limit" e.l.) i
        # stedet for CSV hvis IP'en bliver bot-blokeret — fang det tydeligt i loggen
        # i stedet for at fejle stille med 0 rækker.
        if r.status_code != 200 or not lines or not lines[0].lower().startswith("date"):
            logger.warning(f"Stooq {ticker}: uventet svar (status={r.status_code}): {r.text[:120]!r}")
            return []
        rows = []
        for line in lines[1:]:
            felter = line.split(",")
            if len(felter) >= 5:
                try:
                    rows.append({"dato": felter[0], "close": float(felter[4])})
                except ValueError:
                    continue
        if not rows:
            logger.warning(f"Stooq {ticker}: CSV-header ok, men 0 rækker parset ({len(lines)} linjer)")
        _cache[cache_key] = (time.time(), rows)
        return rows
    except Exception as e:
        logger.warning(f"Stooq {ticker}: {e}")
        return []


def _kvartal_fra_dato(dato_str):
    """'2024-03-28' → 'Q1 2024'."""
    try:
        aar, mdr, _ = dato_str.split("-")
        return f"Q{(int(mdr) - 1) // 3 + 1} {aar}"
    except Exception:
        return None


def hent_live_sektor_afkast(kvartaler):
    """
    Hent faktiske kvartalsafkast (%) for USA's GICS-sektorer via SPDR sector-ETF'er.
    Returnerer {sektor: {kvartal: afkast_pct}} — afkast fra forrige kvartals
    slutkurs til dette kvartals slutkurs. Tom dict hvis Stooq er uden for
    rækkevidde (f.eks. en sandbox uden internetadgang) — kalderen falder da
    tilbage til den manuelle Point-score-vurdering i backtesten.
    """
    result = {}
    for sektor, ticker in SEKTOR_ETF_USA.items():
        rows = _stooq_quarterly(ticker)
        if not rows:
            continue
        by_kv = {}
        for row in rows:
            kv = _kvartal_fra_dato(row["dato"])
            if kv in kvartaler:
                by_kv[kv] = row["close"]
        sorted_kv = sorted(by_kv.keys(), key=lambda k: kvartaler.index(k))
        afkast = {}
        prev_close = None
        for kv in sorted_kv:
            close = by_kv[kv]
            if prev_close is not None:
                afkast[kv] = round((close / prev_close - 1) * 100, 2)
            prev_close = close
        if afkast:
            result[sektor] = afkast
    if result:
        logger.info(f"Live sektor-ETF-afkast hentet for {len(result)} sektorer")
    return result


def flet_med_default(live, default):
    """
    Flet live data med DEFAULT_MAKRO.
    Live-data har prioritet; DEFAULT_MAKRO fylder huller.
    Returnerer {region: {ind: {vaerdi, kilde}}} kompatibelt med seneste_makro-format.
    """
    result = {}
    for region in ("Europa", "USA"):
        live_rg    = live.get(region, {})
        default_rg = default.get(region, {})
        result[region] = {}
        all_inds = set(default_rg.keys()) | set(live_rg.keys())
        for ind in all_inds:
            if ind in live_rg and live_rg[ind] is not None:
                # Bevar prev_vaerdi fra excel-data (live_rg har kun nuværende)
                prev = default_rg.get(ind, {}).get("prev_vaerdi") if isinstance(default_rg.get(ind), dict) else None
                result[region][ind] = {"vaerdi": live_rg[ind], "kilde": "live", "prev_vaerdi": prev}
            elif ind in default_rg:
                v = default_rg[ind]
                if isinstance(v, dict):
                    result[region][ind] = v  # bevar eksisterende kilde-felt + prev_vaerdi
                else:
                    result[region][ind] = {"vaerdi": v, "kilde": "estimat", "prev_vaerdi": None}
    return result
