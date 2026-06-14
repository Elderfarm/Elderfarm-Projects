"""
data.py — Datahentning og beregningslogik for Makroinvestor Web
Læser fra Excel og (når tilgængeligt) live APIs.
"""

import os
import openpyxl
from datetime import datetime

_DEFAULT_EXCEL = os.path.join(os.path.dirname(__file__), "data.xlsx")
EXCEL_PATH = os.environ.get("MAKRO_EXCEL", _DEFAULT_EXCEL)

# ── Sektornormalisering ───────────────────────────────────────────────────────

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

SEKTOR_IKONER = {
    "Information Technology":   "💻",
    "Communications Services":  "📡",
    "Industrials":              "⚙️",
    "Financials":               "🏦",
    "Consumer Discretionary":   "🛍️",
    "Energy":                   "⚡",
    "Health Care":              "🏥",
    "Real Estate":              "🏗️",
    "Materials":                "🔩",
    "Utilities":                "💡",
    "Consumer Staples":         "🛒",
}

def norm(s):
    if not s:
        return ""
    return SEKTOR_MAP.get(str(s).strip().lower(), str(s).strip())


# ── Excel-indlæsning ─────────────────────────────────────────────────────────

def indlaes_wb():
    return openpyxl.load_workbook(EXCEL_PATH, data_only=True)


def hent_ranglister(wb):
    """Returnér dict: sektor -> {dk, eu, usa} Q2 2026 scores."""
    dk, eu, usa = {}, {}, {}

    ws = wb["Ranglisten DK"]
    rows = list(ws.iter_rows(values_only=True))
    for row in rows[1:12]:
        if row[2] and isinstance(row[4], (int, float)):
            dk[norm(row[2])] = float(row[4])

    ws = wb["Ranglisten EU"]
    rows = list(ws.iter_rows(values_only=True))
    for row in rows[1:12]:
        if row[1] and isinstance(row[4], (int, float)):
            eu[norm(row[1])] = float(row[4])

    ws = wb["Ranglisten USA"]
    rows = list(ws.iter_rows(values_only=True))
    for row in rows[1:12]:
        if row[1] and isinstance(row[5], (int, float)):
            usa[norm(row[1])] = float(row[5])

    return dk, eu, usa


def hent_bnp_sensitivitet(wb):
    """Returnér dict: sektor -> {Early, Mid, Late, Recession} -> int (-2..+2)."""
    konv = {"++": 2, "+": 1, None: 0, "–": -1, "--": -2, "-": -1, "−": -1}
    ws = wb["BNP"]
    rows = list(ws.iter_rows(values_only=True))
    res = {}
    for row in rows[2:14]:
        if not row[1]:
            continue
        s = norm(str(row[1]))
        res[s] = {
            "Early":     konv.get(row[2], 0),
            "Mid":       konv.get(row[3], 0),
            "Late":      konv.get(row[4], 0),
            "Recession": konv.get(row[5], 0),
        }
    return res


def hent_fremtid_vaekst(wb):
    """Returnér dict: region -> indikator -> {'q1': val, 'q2': val}"""
    ws = wb["Fremtid vækst"]
    rows = list(ws.iter_rows(values_only=True))
    data = {}
    cur = None
    for row in rows:
        if row[1] in ("Danmark", "Europa", "USA") and row[2] is not None and str(row[2]).startswith("Q"):
            cur = row[1]
            data.setdefault(cur, {})
        elif cur and row[1] and row[2] is not None and row[3] is not None:
            ind = str(row[1])
            try:
                q1 = float(str(row[2]).replace(" ", "")) if row[2] else None
            except:
                q1 = None
            try:
                q2 = float(str(row[3]).replace(" ", "")) if row[3] else None
            except:
                q2 = None
            if q1 or q2:
                data[cur][ind] = {"q1": q1, "q2": q2}
    return data


def hent_historisk_makro(wb):
    """Hent historiske PMI, 10yr, CPI, VIX data per region."""
    historik = {}

    # PMI
    ws = wb["PMI"]
    cur = None
    for row in ws.iter_rows(values_only=True):
        lbl = row[4] if len(row) > 4 else None
        if isinstance(lbl, str) and "PMI" in lbl:
            region = "USA" if "USA" in lbl else ("Europa" if "Euroområdet" in lbl else "Danmark")
            cur = region
            historik.setdefault(region, {}).setdefault("PMI", [])
        elif cur and isinstance(row[3], str) and row[3].startswith("Q") and isinstance(row[4], (int, float)):
            historik[cur]["PMI"].append({"kvartal": row[3], "vaerdi": row[4], "fase": row[5]})

    # 10yr rente
    ws = wb["10 yr rate"]
    cur = None
    for row in ws.iter_rows(values_only=True):
        if row[3] == "USA 10 year":
            cur = "USA"
            historik.setdefault("USA", {}).setdefault("10yr", [])
        elif row[3] == "Euroområdet 10 year":
            cur = "Europa"
            historik.setdefault("Europa", {}).setdefault("10yr", [])
        elif cur and isinstance(row[2], str) and row[2].startswith("Q") and isinstance(row[3], (int, float)):
            historik[cur]["10yr"].append({"kvartal": row[2], "vaerdi": row[3], "fase": row[4]})

    # CPI
    ws = wb["CPI(Inflation)"]
    cur = None
    for row in ws.iter_rows(values_only=True):
        if row[2] == "Kvartal":
            lbl = str(row[3]) if row[3] else ""
            cur = "Danmark" if "Danmark" in lbl else ("Europa" if "Euroområdet" in lbl else None)
            if cur:
                historik.setdefault(cur, {}).setdefault("CPI", [])
        elif cur and isinstance(row[2], str) and row[2].startswith("Q") and isinstance(row[3], (int, float)):
            historik[cur]["CPI"].append({"kvartal": row[2], "vaerdi": row[3] * 100, "fase": row[4]})

    # VIX
    ws = wb["VIX"]
    cur = None
    for row in ws.iter_rows(values_only=True):
        if row[3] == "Kvartal":
            lbl = str(row[4]) if row[4] else ""
            if lbl == "Europa":
                cur = "Europa"
                historik.setdefault("Europa", {}).setdefault("VIX", [])
            elif lbl == "USA":
                cur = "USA"
                historik.setdefault("USA", {}).setdefault("VIX", [])
        elif cur and isinstance(row[3], str) and row[3].startswith("Q") and isinstance(row[4], (int, float)):
            historik[cur]["VIX"].append({"kvartal": row[3], "vaerdi": row[4], "fase": row[5]})

    return historik


def hent_etf_liste(wb):
    """Returnér dict: norm_sektor -> [ETF dict, ...]"""
    ws = wb["ETF - Liste"]
    res = {}
    for row in ws.iter_rows(values_only=True):
        if not row[0] or row[0] == "Kategori":
            continue
        kategori, navn, isin, region, sektor = (row[i] if len(row) > i else None for i in range(5))
        if navn and sektor:
            key = norm(sektor)
            res.setdefault(key, []).append({
                "navn": navn, "isin": isin, "region": region, "sektor": sektor
            })
    return res


def hent_aktier(wb):
    """Returnér dict: region -> [aktie dict, ...]"""
    aktier = {"Danmark": [], "Europa": [], "USA": []}

    for region, ark, ticker_col, sektor_col in [
        ("Danmark", "Aktieliste DK", 7, 5),
        ("Europa",  "Aktieliste EU", 6, 5),
        ("USA",     "Aktieliste USA", 6, 5),
    ]:
        ws = wb[ark]
        rows = list(ws.iter_rows(values_only=True))
        for row in rows[1:]:
            ticker = row[ticker_col] if len(row) > ticker_col else None
            sektor = row[sektor_col] if len(row) > sektor_col else None
            mkt_cap = row[2] if len(row) > 2 else None
            change = row[3] if len(row) > 3 else None
            pe = row[6] if region == "Danmark" and len(row) > 6 else (row[7] if len(row) > 7 else None)
            beta = row[9] if len(row) > 9 else None

            if ticker and isinstance(ticker, str) and sektor and isinstance(mkt_cap, (int, float)):
                aktier[region].append({
                    "ticker": ticker,
                    "sektor": norm(sektor),
                    "market_cap": mkt_cap,
                    "market_cap_mia": round(mkt_cap / 1e9, 1),
                    "change_pct": round(change * 100, 2) if isinstance(change, float) else None,
                    "pe": round(pe, 1) if isinstance(pe, (int, float)) and pe > 0 else None,
                    "beta": round(beta, 2) if isinstance(beta, (int, float)) else None,
                })
    return aktier


def hent_spoergeskema(wb):
    ws = wb["Spørgeskema"]
    rows = list(ws.iter_rows(values_only=True))
    ql = []
    for row in rows[1:]:
        if not row[0]:
            continue
        svar = []
        nr = 1
        for i in range(4):
            sv = row[1 + i]
            sc = row[5 + i]
            if sv is not None and sc is not None:
                svar.append({"nr": nr, "tekst": str(sv), "score": int(sc)})
                nr += 1
        ql.append({"tekst": str(row[0]), "svar": svar})
    return ql


def hent_profiler(wb):
    ws = wb["Profiler"]
    rows = list(ws.iter_rows(values_only=True))
    res = []
    for row in rows[1:]:
        if not row[0]:
            continue
        res.append({
            "navn": str(row[0]),
            "fra": float(row[1]) if row[1] else 0,
            "til": float(row[2]) if row[2] else 1,
            "beskrivelse": str(row[3]) if row[3] else "",
            "fordeling": str(row[4]) if row[4] else "",
            "alternativer": str(row[5]) if row[5] else "",
        })
    return res


def hent_afstemning(wb):
    """Historisk afstemning makroscore vs. faktisk afkast."""
    ws = wb["Afstemning til Virkelighed"]
    rows = list(ws.iter_rows(values_only=True))
    res = []
    for row in rows[1:]:
        if not row[0]:
            continue
        res.append({
            "sektor": norm(str(row[0])),
            "makroscore": row[1],
            "q3_afkast": row[2],
            "kommentar": str(row[3]) if row[3] else "",
        })
    return res


# ── Makrofaseberegning ────────────────────────────────────────────────────────

FASE_VAEGTER = {
    "PMI": 3,       # Vigtigste konjunkturindikator
    "10yr": 2,      # Renteniveau fortæller om pengepolitik
    "CPI": 1,       # Inflation-fase
    "VIX": 2,       # Markedsusikkerhed
    "BNP": 3,       # Vækstfase
    "Unemployment": 1,
}

FASE_BESKRIVELSER = {
    "Early":     ("Tidlig opsving", "Økonomi kommer ud af lavvækst. Bred aktieopgang, cykliske sektorer outperformer.", "🌱"),
    "Mid":       ("Midt-cyklus",    "Solid vækst med moderat inflation. Bred markedseksponering er fordelagtig.",     "🚀"),
    "Late":      ("Sent cyklus",    "Stram pengepolotik, stigende inflation. Defensivt og energi klarer sig bedst.",   "🌇"),
    "Recession": ("Recession",      "Negativ vækst. Obligationer, guld og defensive sektorer er tilflugt.",            "⚠️"),
}

def klassificer_pmi(v):
    if v is None: return None
    if v >= 53: return "Mid"
    if v >= 50: return "Early"
    if v >= 47: return "Late"
    return "Recession"

def klassificer_10yr(v, region="USA"):
    if v is None: return None
    if region == "USA":
        if v < 3.0:  return "Early"
        if v < 4.0:  return "Mid"
        if v < 4.75: return "Late"
        return "Recession"
    else:
        if v < 2.0:  return "Early"
        if v < 2.75: return "Mid"
        if v < 3.5:  return "Late"
        return "Recession"

def klassificer_cpi(v):
    if v is None: return None
    if v < 1.5: return "Recession"
    if v < 2.0: return "Early"
    if v < 3.0: return "Mid"
    return "Late"

def klassificer_vix(v):
    if v is None: return None
    if v < 15:   return "Mid"
    if v < 20:   return "Early"
    if v < 30:   return "Late"
    return "Recession"

def klassificer_bnp(v):
    if v is None: return None
    if v < 0:    return "Recession"
    if v < 0.5:  return "Early"
    if v < 1.5:  return "Mid"
    return "Late"


def beregn_makrofase(fremtid):
    """
    Beregn vægtet makrofase per region og samlet global fase.
    Returnerer dict med detaljer.
    """
    fase_point = {"Early": 0, "Mid": 0, "Late": 0, "Recession": 0}
    detaljer = []

    for region, data in fremtid.items():
        pmi = data.get("PMI", {}).get("q2")
        rate_key = "10 YR rate"
        rate = data.get(rate_key, {}).get("q2")
        cpi = data.get("CPI", {}).get("q2")
        vix = data.get("VIX", {}).get("q2")
        bnp = data.get("BNP", {}).get("q2")
        unemp = data.get("Unemployment", {}).get("q2")

        indikatorer = [
            ("PMI",          pmi,   klassificer_pmi(pmi),           FASE_VAEGTER["PMI"],   f"{pmi:.1f}" if pmi else "N/A"),
            ("10yr rente",   rate,  klassificer_10yr(rate, region), FASE_VAEGTER["10yr"],  f"{rate:.2f}%" if rate else "N/A"),
            ("CPI",          cpi,   klassificer_cpi(cpi * 100 if cpi and cpi < 1 else cpi),  FASE_VAEGTER["CPI"],   f"{cpi*100:.1f}%" if cpi else "N/A"),
            ("VIX",          vix,   klassificer_vix(vix),           FASE_VAEGTER["VIX"],   f"{vix:.1f}" if vix else "N/A"),
            ("BNP vækst",    bnp,   klassificer_bnp(bnp * 100 if bnp and bnp < 1 else bnp), FASE_VAEGTER["BNP"],   f"{bnp*100:.1f}%" if bnp else "N/A"),
        ]

        region_point = {"Early": 0, "Mid": 0, "Late": 0, "Recession": 0}
        ind_liste = []
        for navn, val, fase, vaegt, visning in indikatorer:
            if fase:
                region_point[fase] += vaegt
                fase_point[fase] += vaegt
            ind_liste.append({"navn": navn, "vaerdi": visning, "fase": fase, "vaegt": vaegt})

        dom_region = max(region_point, key=region_point.get)
        detaljer.append({
            "region": region,
            "fase": dom_region,
            "indikatorer": ind_liste,
            "point": region_point,
        })

    global_fase = max(fase_point, key=fase_point.get)
    total = sum(fase_point.values())
    fase_pct = {f: round(v / total * 100) for f, v in fase_point.items()} if total else {}

    titel, beskrivelse, ikon = FASE_BESKRIVELSER.get(global_fase, ("Ukendt", "", "❓"))

    return {
        "fase": global_fase,
        "titel": titel,
        "beskrivelse": beskrivelse,
        "ikon": ikon,
        "fase_pct": fase_pct,
        "detaljer": detaljer,
        "point": fase_point,
    }


# ── Sektorscoring ─────────────────────────────────────────────────────────────

def beregn_sektorscorer(dk, eu, usa, bnp_sens, fase):
    """
    Composite score = makro_avg * 0.70 + bnp_norm * 0.30
    BNP bonus (-2..+2) normaliseres til 1..5 skala.
    """
    alle = set(dk) | set(eu) | set(usa)
    res = []

    for sektor in alle:
        scores = [s for s in [dk.get(sektor), eu.get(sektor), usa.get(sektor)] if s is not None]
        if not scores:
            continue
        makro_avg = sum(scores) / len(scores)

        bnp_raw = 0
        match = next((v for k, v in bnp_sens.items() if norm(k) == sektor), None)
        if match:
            bnp_raw = match.get(fase, 0)

        bnp_norm = (bnp_raw + 2) / 4 * 5  # -2..+2 → 0..5

        composite = makro_avg * 0.70 + bnp_norm * 0.30

        res.append({
            "sektor":    sektor,
            "ikon":      SEKTOR_IKONER.get(sektor, "📊"),
            "composite": round(composite, 2),
            "makro_avg": round(makro_avg, 2),
            "dk":        round(dk.get(sektor, 0), 2),
            "eu":        round(eu.get(sektor, 0), 2),
            "usa":       round(usa.get(sektor, 0), 2),
            "bnp_raw":   bnp_raw,
            "bnp_norm":  round(bnp_norm, 2),
        })

    res.sort(key=lambda x: x["composite"], reverse=True)
    for i, s in enumerate(res):
        s["rank"] = i + 1
    return res


# ── Risikoprofil ──────────────────────────────────────────────────────────────

def match_profil(profiler, score_ratio):
    for p in profiler:
        if p["fra"] <= score_ratio <= p["til"]:
            return p
    return profiler[-1]


def parse_fordeling(fordeling_str):
    """Parse 'Obligationer 0%, ETF 55%, Aktier 35%, Alternative 10%' til dict."""
    import re
    parts = re.findall(r'([A-Za-zæøåÆØÅ ]+?)\s+(\d+)%', fordeling_str)
    return {navn.strip(): int(pct) for navn, pct in parts}


# ── Samlet dataindlæsning ─────────────────────────────────────────────────────

def hent_alle_data():
    wb = indlaes_wb()
    dk, eu, usa      = hent_ranglister(wb)
    bnp_sens          = hent_bnp_sensitivitet(wb)
    fremtid           = hent_fremtid_vaekst(wb)
    historik          = hent_historisk_makro(wb)
    etf_liste         = hent_etf_liste(wb)
    aktier            = hent_aktier(wb)
    spoergeskema      = hent_spoergeskema(wb)
    profiler          = hent_profiler(wb)
    afstemning        = hent_afstemning(wb)

    makro_fase        = beregn_makrofase(fremtid)
    sektorer          = beregn_sektorscorer(dk, eu, usa, bnp_sens, makro_fase["fase"])

    return {
        "makro_fase":   makro_fase,
        "sektorer":     sektorer,
        "etf_liste":    etf_liste,
        "aktier":       aktier,
        "spoergeskema": spoergeskema,
        "profiler":     profiler,
        "afstemning":   afstemning,
        "historik":     historik,
        "fremtid":      fremtid,
        "opdateret":    datetime.now().strftime("%d.%m.%Y %H:%M"),
        "data_kvartal": "Q2 2026",
    }
