#!/usr/bin/env python3
"""
Makroinvestor - Dansk makroøkonomisk investeringsanalyseværktøj
Analyserer makrotendenser fra Excel og anbefaler investeringssektorer.
"""

import sys
import os
import argparse

# ── ANSI farver ──────────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
WHITE   = "\033[97m"

# ── Standard Excel-fil ───────────────────────────────────────────────────────
DEFAULT_EXCEL = (
    "/root/.claude/uploads/4353b6a9-163f-529f-a054-f6c3b69a4fdb/"
    "4eb3c991-Makroinvestoren_Final.xlsx"
)

# ── Hjælpefunktioner til formattering ───────────────────────────────────────
def boks_top(titel, bredde=70):
    print(f"{BOLD}{CYAN}╔{'═'*(bredde-2)}╗{RESET}")
    padding = bredde - 4 - len(titel)
    padding = max(0, padding)
    print(f"{BOLD}{CYAN}║ {WHITE}{BOLD}{titel}{' '*padding} {CYAN}║{RESET}")
    print(f"{BOLD}{CYAN}╠{'═'*(bredde-2)}╣{RESET}")

def boks_bund(bredde=70):
    print(f"{BOLD}{CYAN}╚{'═'*(bredde-2)}╝{RESET}")

def boks_linje(tekst, bredde=70):
    synlig_laengde = len(tekst.encode('ascii', errors='ignore').decode('ascii'))
    # strip ANSI
    import re
    ansi_escape = re.compile(r'\033\[[0-9;]*m')
    ren = ansi_escape.sub('', tekst)
    padding = bredde - 4 - len(ren)
    padding = max(0, padding)
    print(f"{BOLD}{CYAN}║{RESET} {tekst}{' '*padding} {BOLD}{CYAN}║{RESET}")

def sektion(titel, bredde=70):
    print()
    print(f"{BOLD}{YELLOW}{'━'*bredde}{RESET}")
    print(f"{BOLD}{YELLOW}  {titel}{RESET}")
    print(f"{BOLD}{YELLOW}{'━'*bredde}{RESET}")

def ascii_bar(score, max_score=5.0, bredde=20, farve=GREEN):
    filled = int((score / max_score) * bredde) if max_score > 0 else 0
    filled = max(0, min(filled, bredde))
    bar = "█" * filled + "░" * (bredde - filled)
    return f"{farve}{bar}{RESET}"

# ── Indlæs Excel ─────────────────────────────────────────────────────────────
def load_workbook(path):
    try:
        import openpyxl
    except ImportError:
        print(f"{RED}Fejl: openpyxl er ikke installeret. Kør: pip install openpyxl{RESET}")
        sys.exit(1)
    if not os.path.exists(path):
        print(f"{RED}Fejl: Excel-filen blev ikke fundet: {path}{RESET}")
        sys.exit(1)
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
        return wb
    except Exception as e:
        print(f"{RED}Fejl ved indlæsning af Excel: {e}{RESET}")
        sys.exit(1)

# ── Spørgeskema ───────────────────────────────────────────────────────────────
def hent_spoergeskema(wb):
    ws = wb["Spørgeskema"]
    spoergsmaal = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue
        q_tekst = row[0]
        svar_og_scores = []
        for i in range(4):
            sv = row[1 + i]
            sc = row[5 + i]
            if sv is not None and sc is not None:
                svar_og_scores.append((i + 1, str(sv), int(sc)))
        if q_tekst and svar_og_scores:
            spoergsmaal.append((q_tekst, svar_og_scores))
    return spoergsmaal

def koer_spoergeskema(spoergsmaal):
    sektion("RISIKOANALYSE – Spørgeskema")
    print(f"{DIM}  Besvar venligst de følgende {len(spoergsmaal)} spørgsmål.{RESET}")
    print(f"{DIM}  Angiv nummeret på dit svar (f.eks. 1, 2, 3 eller 4).{RESET}\n")

    total_score = 0
    max_score = 0

    for idx, (q, svar) in enumerate(spoergsmaal, 1):
        print(f"  {BOLD}{WHITE}{idx}. {q}{RESET}")
        for nr, sv_tekst, sc in svar:
            print(f"     {CYAN}{nr}{RESET}. {sv_tekst}")
        mulige = [str(nr) for nr, _, _ in svar]
        maks_for_q = max(sc for _, _, sc in svar)
        max_score += maks_for_q

        while True:
            try:
                valg = input(f"     {YELLOW}Dit valg [{'/'.join(mulige)}]: {RESET}").strip()
                if valg not in mulige:
                    print(f"     {RED}Ugyldigt valg. Prøv igen.{RESET}")
                    continue
                valg_nr = int(valg)
                for nr, _, sc in svar:
                    if nr == valg_nr:
                        total_score += sc
                        break
                break
            except KeyboardInterrupt:
                print(f"\n{RED}Afbrudt.{RESET}")
                sys.exit(0)
        print()

    return total_score, max_score

# ── Risikoprofil ──────────────────────────────────────────────────────────────
def hent_profiler(wb):
    ws = wb["Profiler"]
    profiler = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue
        profiler.append({
            "navn": row[0],
            "fra": float(row[1]) if row[1] is not None else 0.0,
            "til": float(row[2]) if row[2] is not None else 1.0,
            "beskrivelse": row[3] or "",
            "aktivfordeling": row[4] or "",
            "alternativer": row[5] or "",
        })
    return profiler

def bestem_profil(ratio, profiler):
    for p in profiler:
        if p["fra"] <= ratio <= p["til"]:
            return p
    if ratio < profiler[0]["fra"]:
        return profiler[0]
    return profiler[-1]

def parse_aktivfordeling(fordeling_str):
    result = {}
    if not fordeling_str:
        return result
    parts = [p.strip() for p in fordeling_str.split(",")]
    for part in parts:
        try:
            idx = part.rfind(" ")
            if idx == -1:
                continue
            navn = part[:idx].strip()
            pct_str = part[idx+1:].strip().replace("%", "")
            pct_val = float(pct_str) / 100.0
            result[navn] = pct_val
        except (ValueError, AttributeError):
            pass
    return result

# ── Makrofase-detektion ───────────────────────────────────────────────────────
def pmi_til_fase(v):
    if v is None:
        return "Ukendt"
    if v < 45:
        return "Recession"
    elif v < 50:
        return "Early"
    elif v < 55:
        return "Mid"
    else:
        return "Late"

def rente_til_fase(v):
    if v is None:
        return "Ukendt"
    if v < 2.5:
        return "Early"
    elif v < 3.5:
        return "Mid"
    else:
        return "Late"

def cpi_til_fase(v):
    if v is None:
        return "Ukendt"
    if v < 0.015:
        return "Recession"
    elif v < 0.02:
        return "Early"
    elif v < 0.025:
        return "Mid"
    else:
        return "Late"

def vix_til_fase(v):
    if v is None:
        return "Ukendt"
    if v < 15:
        return "Early"
    elif v < 20:
        return "Mid"
    elif v < 25:
        return "Late"
    else:
        return "Recession"

FASE_POINT = {"Early": 1, "Mid": 2, "Late": 3, "Recession": 0, "Ukendt": -1}

def hent_makrodata(wb):
    data = {}

    # ── PMI ──
    ws = wb["PMI"]
    pmi_rows = list(ws.iter_rows(values_only=True))
    usa_pmi_q, usa_pmi_v = None, None
    eu_pmi_q, eu_pmi_v   = None, None
    dk_pmi_q, dk_pmi_v   = None, None
    mode = None
    for row in pmi_rows:
        if row[3] == "Kvartal" and isinstance(row[4], str):
            if "USA" in row[4]:
                mode = "USA"
            elif "Euro" in row[4]:
                mode = "EU"
            elif "Dan" in row[4] or "mark" in row[4]:
                mode = "DK"
            continue
        if row[3] and isinstance(row[3], str) and row[3].startswith("Q"):
            if row[4] is not None and isinstance(row[4], (int, float)):
                if mode == "USA":
                    usa_pmi_q, usa_pmi_v = row[3], row[4]
                elif mode == "EU":
                    eu_pmi_q, eu_pmi_v = row[3], row[4]
                elif mode == "DK":
                    dk_pmi_q, dk_pmi_v = row[3], row[4]
    data["pmi"] = {
        "USA": (usa_pmi_q, usa_pmi_v),
        "EU":  (eu_pmi_q,  eu_pmi_v),
        "DK":  (dk_pmi_q,  dk_pmi_v),
    }

    # ── 10yr rate ──
    ws = wb["10 yr rate"]
    rate_rows = list(ws.iter_rows(values_only=True))
    usa_r_q, usa_r_v = None, None
    eu_r_q, eu_r_v   = None, None
    dk_r_q, dk_r_v   = None, None
    mode = None
    for row in rate_rows:
        if row[2] == "Kvartal" and isinstance(row[3], str):
            if "USA" in row[3]:
                mode = "USA"
            elif "Euro" in row[3]:
                mode = "EU"
            elif "Dan" in row[3] or "mark" in row[3]:
                mode = "DK"
            continue
        if row[2] and isinstance(row[2], str) and row[2].startswith("Q"):
            if row[3] is not None and isinstance(row[3], (int, float)):
                if mode == "USA":
                    usa_r_q, usa_r_v = row[2], row[3]
                elif mode == "EU":
                    eu_r_q, eu_r_v = row[2], row[3]
                elif mode == "DK":
                    dk_r_q, dk_r_v = row[2], row[3]
    data["rate10yr"] = {
        "USA": (usa_r_q, usa_r_v),
        "EU":  (eu_r_q,  eu_r_v),
        "DK":  (dk_r_q,  dk_r_v),
    }

    # ── CPI ──
    ws = wb["CPI(Inflation)"]
    cpi_rows = list(ws.iter_rows(values_only=True))
    usa_c_q, usa_c_v = None, None
    eu_c_q,  eu_c_v  = None, None
    dk_c_q,  dk_c_v  = None, None
    mode = None
    for row in cpi_rows:
        if row[1] == "Kvartal":
            label = str(row[3]) if row[3] else ""
            if "USA" in label or "\U0001f1fa\U0001f1f8" in label:
                mode = "USA"
            elif "Euro" in label or "\U0001f1ea\U0001f1fa" in label:
                mode = "EU"
            elif "Dan" in label or "\U0001f1e9\U0001f1f0" in label:
                mode = "DK"
            continue
        if row[2] and isinstance(row[2], str) and row[2].startswith("Q"):
            if row[3] is not None and isinstance(row[3], (int, float)):
                if mode == "USA":
                    usa_c_q, usa_c_v = row[2], row[3]
                elif mode == "EU":
                    eu_c_q,  eu_c_v  = row[2], row[3]
                elif mode == "DK":
                    dk_c_q,  dk_c_v  = row[2], row[3]
    data["cpi"] = {
        "USA": (usa_c_q, usa_c_v),
        "EU":  (eu_c_q,  eu_c_v),
        "DK":  (dk_c_q,  dk_c_v),
    }

    # ── VIX ──
    ws = wb["VIX"]
    vix_rows = list(ws.iter_rows(values_only=True))
    usa_vx_q, usa_vx_v = None, None
    eu_vx_q,  eu_vx_v  = None, None
    dk_vx_q,  dk_vx_v  = None, None
    mode = None
    for row in vix_rows:
        if row[3] == "Kvartal":
            if row[4] == "USA":
                mode = "USA"
            elif row[4] == "Europa":
                mode = "EU"
            elif row[4] == "Danmark":
                mode = "DK"
            continue
        if row[3] and isinstance(row[3], str) and row[3].startswith("Q"):
            if row[4] is not None and isinstance(row[4], (int, float)):
                if mode == "USA":
                    usa_vx_q, usa_vx_v = row[3], row[4]
                elif mode == "EU":
                    eu_vx_q,  eu_vx_v  = row[3], row[4]
                elif mode == "DK":
                    dk_vx_q,  dk_vx_v  = row[3], row[4]
    data["vix"] = {
        "USA": (usa_vx_q, usa_vx_v),
        "EU":  (eu_vx_q,  eu_vx_v),
        "DK":  (dk_vx_q,  dk_vx_v),
    }

    return data

def bestem_makrofase(makrodata):
    votes = []
    detaljer = {}

    for region in ["DK", "EU", "USA"]:
        q, v = makrodata["pmi"][region]
        if v is not None:
            fase = pmi_til_fase(v)
            votes.append(FASE_POINT[fase])
            detaljer[f"PMI {region}"] = (q, v, fase)

    for region in ["DK", "EU", "USA"]:
        q, v = makrodata["rate10yr"][region]
        if v is not None:
            fase = rente_til_fase(v)
            votes.append(FASE_POINT[fase])
            detaljer[f"10yr rente {region}"] = (q, v, fase)

    for region in ["DK", "EU", "USA"]:
        q, v = makrodata["cpi"][region]
        if v is not None:
            fase = cpi_til_fase(v)
            votes.append(FASE_POINT[fase])
            detaljer[f"CPI {region}"] = (q, v * 100, fase)

    for region in ["DK", "EU", "USA"]:
        q, v = makrodata["vix"][region]
        if v is not None:
            fase = vix_til_fase(v)
            votes.append(FASE_POINT[fase])
            detaljer[f"VIX {region}"] = (q, v, fase)

    gyldige = [x for x in votes if x >= 0]
    if not gyldige:
        return "Mid", detaljer

    avg = sum(gyldige) / len(gyldige)
    if avg < 0.5:
        return "Recession", detaljer
    elif avg < 1.5:
        return "Early", detaljer
    elif avg < 2.5:
        return "Mid", detaljer
    else:
        return "Late", detaljer

def fase_farve(fase):
    return {"Early": GREEN, "Mid": BLUE, "Late": YELLOW, "Recession": RED}.get(fase, WHITE)

def fase_dansk(fase):
    return {
        "Early": "Tidlig vækst",
        "Mid": "Mellemfase",
        "Late": "Sen vækst",
        "Recession": "Recession",
    }.get(fase, fase)

# ── Sektor-scoring ────────────────────────────────────────────────────────────
SEKTORER = [
    "Financials",
    "Real Estate",
    "Consumer Discretionary",
    "Information Technology",
    "Industrials",
    "Materials",
    "Consumer Staples",
    "Health Care",
    "Energy",
    "Communications Services",
    "Utilities",
]

BNP_SEKTOR_MAP = {
    "financials": "Financials",
    "real estate": "Real Estate",
    "consumer discretionary": "Consumer Discretionary",
    "infomation technology": "Information Technology",
    "information technology": "Information Technology",
    "industrials": "Industrials",
    "materials": "Materials",
    "consumer staples": "Consumer Staples",
    "health care": "Health Care",
    "energy": "Energy",
    "communications sercives": "Communications Services",
    "communications services": "Communications Services",
    "utilities": "Utilities",
}

RATING_MAP = {"++": 2, "+": 1, None: 0, "-": -1, "--": -2}

def hent_bnp_sensitivitet(wb):
    ws = wb["BNP"]
    sensitivitet = {}
    for row in ws.iter_rows(values_only=True):
        if row[2] in ("Early", "Mid", "Late", "Recession"):
            continue
        if row[1] and isinstance(row[1], str):
            key = row[1].strip().lower()
            if key in BNP_SEKTOR_MAP:
                sn = BNP_SEKTOR_MAP[key]
                sensitivitet[sn] = {
                    "Early":     RATING_MAP.get(row[2], 0),
                    "Mid":       RATING_MAP.get(row[3], 0),
                    "Late":      RATING_MAP.get(row[4], 0),
                    "Recession": RATING_MAP.get(row[5], 0),
                }
    return sensitivitet

def hent_makroscores(wb):
    ws = wb["Makro analyse"]
    scores = {s: {"DK": None, "EU": None, "USA": None} for s in SEKTORER}

    sektor_map = {}
    for s in SEKTORER:
        sektor_map[s.lower()] = s
    sektor_map["communications services"] = "Communications Services"
    sektor_map["communications sercives"] = "Communications Services"

    mode = None
    for row in ws.iter_rows(values_only=True):
        if row[1] in ("Danmark", "Europa", "USA") and row[2] == "PMI":
            mode = row[1] if row[1] in ("Europa", "USA") else "DK"
            if row[1] == "Danmark":
                mode = "DK"
            elif row[1] == "Europa":
                mode = "EU"
            continue
        if mode and row[1] and isinstance(row[1], str):
            key = row[1].strip().lower()
            if key in sektor_map:
                s = sektor_map[key]
                makro_score = row[10]
                if makro_score is not None and isinstance(makro_score, (int, float)):
                    scores[s][mode] = float(makro_score)
    return scores

def beregn_composite_score(scores, bnp_sensitivitet, fase):
    resultater = {}
    for sektor in SEKTORER:
        region_scores = [v for v in scores[sektor].values() if v is not None]
        avg_makro = sum(region_scores) / len(region_scores) if region_scores else 3.0

        bnp_bonus = 0
        if sektor in bnp_sensitivitet:
            bnp_bonus = bnp_sensitivitet[sektor].get(fase, 0)

        # Skaler BNP bonus fra -2..+2 til 0..5
        bnp_skaleret = (bnp_bonus + 2) * (5.0 / 4.0)
        composite = avg_makro * 0.7 + bnp_skaleret * 0.3

        resultater[sektor] = {
            "makro_avg":   avg_makro,
            "bnp_bonus":   bnp_bonus,
            "bnp_skaleret": bnp_skaleret,
            "composite":   composite,
            "dk":          scores[sektor]["DK"],
            "eu":          scores[sektor]["EU"],
            "usa":         scores[sektor]["USA"],
        }
    return resultater

# ── ETF og aktier ─────────────────────────────────────────────────────────────
def hent_etf_liste(wb):
    ws = wb["ETF - Liste"]
    etf_liste = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[1]:
            continue
        etf_liste.append({
            "kategori": row[0] or "",
            "navn":     row[1] or "",
            "isin":     row[2] or "",
            "region":   row[3] or "",
            "sektor":   row[4] or "",
        })
    return etf_liste

def find_etf_for_sektor(etf_liste, sektor):
    sektor_l = sektor.lower()
    resultater = []
    seen = set()
    for etf in etf_liste:
        etf_s = etf["sektor"].lower()
        if etf_s == sektor_l or sektor_l in etf_s or etf_s in sektor_l:
            if etf["navn"] not in seen:
                seen.add(etf["navn"])
                resultater.append(etf)
    return resultater

AKTIE_SEKTOR_NORM = {
    "financials": "Financials",
    "financial services": "Financials",
    "health care": "Health Care",
    "healthcare": "Health Care",
    "information technology": "Information Technology",
    "technology": "Information Technology",
    "consumer discretionary": "Consumer Discretionary",
    "consumer staples": "Consumer Staples",
    "industrials": "Industrials",
    "materials": "Materials",
    "energy": "Energy",
    "utilities": "Utilities",
    "real estate": "Real Estate",
    "communication services": "Communications Services",
    "communications services": "Communications Services",
}

def hent_aktier(wb, region):
    ark = {"DK": "Aktieliste DK", "EU": "Aktieliste EU", "USA": "Aktieliste USA"}[region]
    ws = wb[ark]
    aktier = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        market_cap = row[2]
        sektor = row[5]
        if not sektor or not isinstance(market_cap, (int, float)):
            continue
        ticker = row[7] if region == "DK" else row[6]
        navn = row[0]
        if navn == "#VALUE!" or not navn:
            navn = ticker or "Ukendt"
        aktier.append({
            "navn":       str(navn),
            "pris":       row[1],
            "market_cap": float(market_cap),
            "sektor":     str(sektor),
            "ticker":     str(ticker) if ticker else "",
            "region":     region,
        })
    return aktier

def find_aktier_for_sektor(aktier, sektor, top_n=3):
    sektor_l = sektor.lower()
    matches = []
    for a in aktier:
        a_sektor_l = a["sektor"].lower()
        normaliseret = AKTIE_SEKTOR_NORM.get(a_sektor_l, a_sektor_l)
        if normaliseret.lower() == sektor_l or a_sektor_l == sektor_l:
            matches.append(a)
        elif sektor_l in a_sektor_l or a_sektor_l in sektor_l:
            matches.append(a)
    matches.sort(key=lambda x: x["market_cap"], reverse=True)
    return matches[:top_n]

# ── Vis-funktioner ────────────────────────────────────────────────────────────
def vis_profil_resultat(profil, total_score, max_score, ratio):
    sektion("RISIKOPROFIL")
    titel = f"Din risikoprofil: {profil['navn']}"
    boks_top(titel, 70)

    score_farve = GREEN if ratio > 0.6 else (YELLOW if ratio > 0.45 else BLUE)
    score_bar = ascii_bar(ratio, 1.0, 28, score_farve)
    boks_linje(f"Score: {total_score}/{max_score}  ({ratio*100:.1f}%)  {score_bar}", 70)
    boks_linje("", 70)

    besk = profil["beskrivelse"] or ""
    # Wrap ved 62 tegn
    ord_liste = besk.split()
    linje_buf = "Beskrivelse: "
    for ord in ord_liste:
        if len(linje_buf) + len(ord) + 1 > 62:
            boks_linje(linje_buf, 70)
            linje_buf = "             " + ord
        else:
            linje_buf += (" " if linje_buf != "Beskrivelse: " else "") + ord
    if linje_buf.strip():
        boks_linje(linje_buf, 70)

    boks_bund(70)

def vis_makrofase(fase, detaljer):
    sektion("MAKROØKONOMISK FASE")
    farve = fase_farve(fase)
    print(f"\n  Samlet vurderet fase: {BOLD}{farve}{fase_dansk(fase)} ({fase}){RESET}\n")
    print(f"  {DIM}{'Indikator':<26} {'Kvartal':<10} {'Værdi':>10}  {'Fase':<12}{RESET}")
    print(f"  {'─'*62}")

    for navn in sorted(detaljer.keys()):
        q, v, f = detaljer[navn]
        f_farve = fase_farve(f)
        q_str = q or "N/A"
        if isinstance(v, float):
            v_str = f"{v:.2f}" if v >= 1 else f"{v:.3f}"
        else:
            v_str = str(v)
        print(f"  {navn:<26} {q_str:<10} {v_str:>10}  {f_farve}{f:<12}{RESET}")

    print(f"  {'─'*62}")
    fase_forklaring = {
        "Early":     "Tidlig vækst: PMI stiger, lav inflation, lave obligationsrenter.",
        "Mid":       "Mellemfase: Solid vækst, PMI over 50, inflation moderat.",
        "Late":      "Sen vækst: Høj rente og inflation, PMI begynder at falde.",
        "Recession": "Recession: PMI under 45, negativ vækst, høj markedsvolatilitet.",
    }
    print(f"\n  {DIM}{fase_forklaring.get(fase, '')}{RESET}")

def vis_sektor_anbefalinger(composite_scores, top_n=5):
    sektion("SEKTORSCORE OG ANBEFALINGER")
    sorteret = sorted(
        composite_scores.items(),
        key=lambda x: x[1]["composite"],
        reverse=True
    )

    print(f"  {'Rang':<5} {'Sektor':<30} {'Score':>6}  {'Bar (maks 5)':<22} {'DK':>5} {'EU':>5} {'USA':>5}")
    print(f"  {'─'*80}")

    for rang, (sektor, d) in enumerate(sorteret, 1):
        score = d["composite"]
        if rang <= top_n:
            rang_farve = GREEN
            prefix = f"{BOLD}{GREEN}★ {RESET}"
        elif rang <= len(SEKTORER) - 3:
            rang_farve = WHITE
            prefix = "  "
        else:
            rang_farve = RED
            prefix = "  "

        bar = ascii_bar(score, 5.0, 20, rang_farve)
        dk_s  = f"{d['dk']:.2f}"  if d["dk"]  is not None else "  N/A"
        eu_s  = f"{d['eu']:.2f}"  if d["eu"]  is not None else "  N/A"
        usa_s = f"{d['usa']:.2f}" if d["usa"] is not None else "  N/A"

        print(f"  {prefix}{rang_farve}{rang:<3}{RESET}  {sektor:<30} "
              f"{rang_farve}{score:>5.2f}{RESET}  {bar} {dk_s:>5} {eu_s:>5} {usa_s:>5}")

    print()
    return [s for s, _ in sorteret[:top_n]]

def vis_etf_og_aktier(top_sektorer, etf_liste, alle_aktier, top_per_region=2):
    sektion("ETF OG AKTIEFORSLAG")

    region_navne = {"DK": "Danmark", "EU": "Europa", "USA": "USA"}

    for rang, sektor in enumerate(top_sektorer, 1):
        print(f"\n  {BOLD}{CYAN}#{rang} {sektor}{RESET}")
        print(f"  {'─'*60}")

        etfs = find_etf_for_sektor(etf_liste, sektor)
        if etfs:
            print(f"  {BOLD}{GREEN}ETF'er:{RESET}")
            for etf in etfs[:3]:
                print(f"    • {etf['navn']}")
                print(f"      {DIM}ISIN: {etf['isin']}  |  Region: {etf['region']}{RESET}")
        else:
            print(f"  {DIM}Ingen specifikke ETF'er fundet for denne sektor.{RESET}")

        print(f"\n  {BOLD}{CYAN}Top aktier:{RESET}")
        fundet = False
        for region in ["DK", "EU", "USA"]:
            matches = find_aktier_for_sektor(alle_aktier[region], sektor, top_per_region)
            if matches:
                fundet = True
                print(f"    {YELLOW}{region_navne[region]}:{RESET}")
                for a in matches:
                    mc = a["market_cap"]
                    if mc >= 1e9:
                        mc_str = f"{mc/1e9:.1f} mia."
                    else:
                        mc_str = f"{mc/1e6:.0f} mio."
                    print(f"      • {a['ticker']:<10} {a['navn'][:22]:<24} MarkedsCap: {mc_str}")
        if not fundet:
            print(f"    {DIM}Ingen aktier fundet for denne sektor.{RESET}")

def vis_aktivallokering(profil, beloeb):
    fordeling = parse_aktivfordeling(profil["aktivfordeling"])
    ALLOK_FARVER = {
        "Obligationer": BLUE,
        "ETF":          GREEN,
        "Aktier":       CYAN,
        "Alternative":  MAGENTA,
    }

    print(f"\n  {BOLD}Aktivfordeling for profil: {profil['navn']}{RESET}")
    print(f"  {'─'*55}")

    total = 0.0
    for aktivklasse, pct in fordeling.items():
        dkk = beloeb * pct
        total += dkk
        farve = ALLOK_FARVER.get(aktivklasse, WHITE)
        bar_w = int(pct * 30)
        bar = "█" * bar_w + "░" * (30 - bar_w)
        print(f"  {farve}{aktivklasse:<14}{RESET} {farve}{bar}{RESET} "
              f"{pct*100:5.0f}%   {YELLOW}{dkk:>12,.0f} DKK{RESET}")

    print(f"  {'─'*55}")
    print(f"  {'Total':<14} {'':30} {' ':5}   {YELLOW}{total:>12,.0f} DKK{RESET}")

    if profil.get("alternativer"):
        print(f"\n  {DIM}Alternative muligheder: {profil['alternativer']}{RESET}")

def vis_afslutning(profil, fase, top_sektorer, beloeb):
    sektion("SAMMENFATNING")
    print(f"  {BOLD}Risikoprofil:{RESET}        {GREEN}{profil['navn']}{RESET}")
    farve = fase_farve(fase)
    print(f"  {BOLD}Makrofase:{RESET}           {farve}{fase_dansk(fase)} ({fase}){RESET}")
    print(f"  {BOLD}Investeringsbeløb:{RESET}   {YELLOW}{beloeb:,.0f} DKK{RESET}")
    print()
    print(f"  {BOLD}Top anbefalede sektorer:{RESET}")
    for i, s in enumerate(top_sektorer, 1):
        print(f"    {GREEN}{i}.{RESET} {s}")
    print()
    print(f"  {DIM}Bemærk: Denne analyse er baseret på historiske og fremskrevne data.{RESET}")
    print(f"  {DIM}Det er ikke finansiel rådgivning. Søg professionel vejledning ved behov.{RESET}")
    print()

def vis_velkomst():
    print()
    w = 70
    print(f"{BOLD}{CYAN}╔{'═'*(w-2)}╗{RESET}")
    l1 = "MAKROINVESTOR – Intelligent Investeringsanalyse"
    l2 = "Baseret på makroøkonomiske data og sektoranalyse"
    p1 = " " * ((w - 2 - len(l1)) // 2)
    p2 = " " * ((w - 2 - len(l2)) // 2)
    print(f"{BOLD}{CYAN}║{WHITE}{p1}{l1}{p1}{' ' if (w-2-len(l1))%2 else ''}{CYAN}║{RESET}")
    print(f"{BOLD}{CYAN}║{DIM}{p2}{l2}{p2}{' ' if (w-2-len(l2))%2 else ''}{CYAN}║{RESET}")
    print(f"{BOLD}{CYAN}╚{'═'*(w-2)}╝{RESET}")
    print()
    print(f"  {DIM}Programmet analyserer aktuelle makrotendenser og hjælper dig med at{RESET}")
    print(f"  {DIM}identificere de bedste investeringssektorer baseret på din risikoprofil.{RESET}")
    print()

# ── Hoved-program ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Makroinvestor – Dansk investeringsanalyseværktøj",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Eksempel:
  python3 makroinvestor.py
  python3 makroinvestor.py --excel /sti/til/fil.xlsx
        """
    )
    parser.add_argument(
        "--excel",
        default=DEFAULT_EXCEL,
        help=f"Sti til Excel-fil (standard: {DEFAULT_EXCEL})"
    )
    args = parser.parse_args()

    vis_velkomst()

    print(f"  {DIM}Indlæser Excel-data ...{RESET}")
    wb = load_workbook(args.excel)
    print(f"  {GREEN}✓ Excel-data indlæst.{RESET}\n")

    # Trin 1: Spørgeskema
    spoergsmaal = hent_spoergeskema(wb)
    total_score, max_score = koer_spoergeskema(spoergsmaal)
    ratio = total_score / max_score if max_score > 0 else 0.5

    # Trin 2: Risikoprofil
    profiler = hent_profiler(wb)
    profil = bestem_profil(ratio, profiler)
    vis_profil_resultat(profil, total_score, max_score, ratio)

    # Trin 3: Makrofase
    makrodata = hent_makrodata(wb)
    fase, fase_detaljer = bestem_makrofase(makrodata)
    vis_makrofase(fase, fase_detaljer)

    # Trin 4: Sektor-scoring
    makro_scores    = hent_makroscores(wb)
    bnp_sensitivitet = hent_bnp_sensitivitet(wb)
    composite_scores = beregn_composite_score(makro_scores, bnp_sensitivitet, fase)
    top_sektorer    = vis_sektor_anbefalinger(composite_scores, top_n=5)

    # Trin 5: ETF og aktier
    etf_liste  = hent_etf_liste(wb)
    alle_aktier = {
        "DK":  hent_aktier(wb, "DK"),
        "EU":  hent_aktier(wb, "EU"),
        "USA": hent_aktier(wb, "USA"),
    }
    vis_etf_og_aktier(top_sektorer, etf_liste, alle_aktier, top_per_region=2)

    # Trin 6: Investeringsbeløb og aktivallokering
    sektion("INVESTERINGSBELØB OG AKTIVALLOKERING")
    print()
    while True:
        try:
            svar = input(f"  {YELLOW}Hvor meget ønsker du at investere (DKK)? {RESET}").strip()
            svar_renset = svar.replace(".", "").replace(",", "").replace(" ", "")
            beloeb = float(svar_renset)
            if beloeb <= 0:
                print(f"  {RED}Beløbet skal være positivt.{RESET}")
                continue
            break
        except ValueError:
            print(f"  {RED}Ugyldigt beløb. Angiv et tal (f.eks. 100000).{RESET}")
        except KeyboardInterrupt:
            print(f"\n{RED}Afbrudt.{RESET}")
            sys.exit(0)

    vis_aktivallokering(profil, beloeb)

    # Trin 7: Sammenfatning
    vis_afslutning(profil, fase, top_sektorer, beloeb)

    print(f"{BOLD}{CYAN}{'═'*70}{RESET}")
    print(f"{BOLD}{GREEN}  Tak for at bruge Makroinvestor! God investering!{RESET}")
    print(f"{BOLD}{CYAN}{'═'*70}{RESET}")
    print()


if __name__ == "__main__":
    main()
