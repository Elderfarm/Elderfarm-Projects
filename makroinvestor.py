#!/usr/bin/env python3
"""
Makroinvestor - Dansk CLI-program til makrooekonomisk investeringsanalyse
Laeder data fra Excel-fil og anbefaler investeringssektorer baseret paa
risikoprofil og makrofase.
"""

import sys
import argparse
import openpyxl


# ANSI-farver
class C:
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


DEFAULT_EXCEL = (
    "/root/.claude/uploads/4353b6a9-163f-529f-a054-f6c3b69a4fdb"
    "/4eb3c991-Makroinvestoren_Final.xlsx"
)


def sektion(tekst, farve=C.BLUE):
    print(f"\n{farve}{C.BOLD}{chr(8212)*72}")
    print(f"  {tekst}")
    print(f"{chr(8212)*72}{C.RESET}")


def linje(tekst=""):
    print(f"  {tekst}")


def ascii_bar(score, max_score=5.0, bredde=28, farve=None):
    andel = max(0.0, min(1.0, score / max_score))
    fyldt = int(andel * bredde)
    bar = "█" * fyldt + "░" * (bredde - fyldt)
    if farve is None:
        if andel >= 0.7:
            farve = C.GREEN
        elif andel >= 0.45:
            farve = C.YELLOW
        else:
            farve = C.RED
    return f"{farve}{bar}{C.RESET} {score:.2f}"


def sporg_tal(prompt, min_val=None, max_val=None):
    while True:
        try:
            svar = input(f"{C.YELLOW}{prompt}{C.RESET} ").strip()
            tal = int(svar)
            if min_val is not None and tal < min_val:
                print(f"  {C.RED}Skal vaere mindst {min_val}.{C.RESET}")
                continue
            if max_val is not None and tal > max_val:
                print(f"  {C.RED}Skal vaere hoejst {max_val}.{C.RESET}")
                continue
            return tal
        except ValueError:
            print(f"  {C.RED}Indtast venligst et heltal.{C.RESET}")


def sporg_float(prompt, min_val=0):
    while True:
        try:
            svar = input(f"{C.YELLOW}{prompt}{C.RESET} ").strip()
            renset = svar.replace(".", "").replace(",", "").replace(" ", "")
            if not renset:
                print(f"  {C.RED}Indtast venligst et beloeb.{C.RESET}")
                continue
            tal = float(renset)
            if tal < min_val:
                print(f"  {C.RED}Bellobet skal vaere positivt.{C.RESET}")
                continue
            return tal
        except ValueError:
            print(f"  {C.RED}Indtast venligst et tal (f.eks. 100000).{C.RESET}")


def load_wb(excel_path):
    try:
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        return wb
    except FileNotFoundError:
        print(f"{C.RED}Fejl: Kan ikke finde Excel-filen:\n  {excel_path}{C.RESET}")
        sys.exit(1)
    except Exception as exc:
        print(f"{C.RED}Fejl ved indlaesning af Excel: {exc}{C.RESET}")
        sys.exit(1)


def _ws(wb, *navne):
    for navn in navne:
        if navn in wb.sheetnames:
            return wb[navn]
    raise KeyError(f"Ingen af arknavnene fundet: {navne}")


def hent_sporgeskema(wb):
    try:
        ws = _ws(wb, "Spørgeskema", "Sporgeskeema")
    except KeyError:
        return []
    sporgsmaal = []
    for row in ws.iter_rows(values_only=True):
        if not row[0]:
            continue
        tekst = str(row[0]).strip()
        if tekst[:2] not in ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8."):
            continue
        q = {"tekst": tekst, "svar": [], "scores": []}
        for idx in range(1, 5):
            s_val = row[idx] if len(row) > idx else None
            p_val = row[idx + 4] if len(row) > idx + 4 else None
            if s_val is not None:
                q["svar"].append(str(s_val).strip())
                try:
                    q["scores"].append(int(p_val) if p_val is not None else 1)
                except (TypeError, ValueError):
                    q["scores"].append(1)
        if q["svar"]:
            sporgsmaal.append(q)
    return sporgsmaal


def hent_risikoprofiler(wb):
    ws = _ws(wb, "Profiler")
    profiler = []
    for row in ws.iter_rows(values_only=True):
        if not row[0] or str(row[0]).strip() in ("Profilnavn", ""):
            continue
        navn = str(row[0]).strip()
        fra  = float(row[1]) if row[1] is not None else 0.0
        til  = float(row[2]) if row[2] is not None else 1.0
        beskr = str(row[3]).strip() if row[3] else ""
        aktiv = str(row[4]).strip() if row[4] else ""
        alt   = str(row[5]).strip() if row[5] else ""
        profiler.append({
            "navn": navn, "fra": fra, "til": til,
            "beskrivelse": beskr, "aktivfordeling": aktiv, "alternativer": alt,
        })
    return profiler


ALLE_SEKTORER = [
    "Financials", "Real Estate", "Consumer Discretionary",
    "Information Technology", "Industrials", "Materials",
    "Consumer Staples", "Health Care", "Energy",
    "Communications Services", "Utilities",
]


def hent_makro_scores(wb):
    ws = _ws(wb, "Makro analyse")
    raekker = list(ws.iter_rows(values_only=True))

    def hent_blok(start, slut, sektor_kol=1, q2_kol=19, q1_kol=10):
        res = {}
        for i in range(start, min(slut + 1, len(raekker))):
            row = raekker[i]
            sektor = row[sektor_kol]
            if sektor and str(sektor).strip() in ALLE_SEKTORER:
                score = row[q2_kol]
                if score is None:
                    score = row[q1_kol]
                try:
                    res[str(sektor).strip()] = float(score) if score is not None else 3.0
                except (TypeError, ValueError):
                    res[str(sektor).strip()] = 3.0
        return res

    dk_scores  = hent_blok(30, 40)
    eu_scores  = hent_blok(70, 80)
    usa_scores = hent_blok(110, 120)

    resultat = {}
    for s in ALLE_SEKTORER:
        dk  = dk_scores.get(s, 3.0)
        eu  = eu_scores.get(s, 3.0)
        usa = usa_scores.get(s, 3.0)
        resultat[s] = {"dk": dk, "eu": eu, "usa": usa, "avg": (dk + eu + usa) / 3.0}
    return resultat


def hent_bnp_sensitivitet(wb):
    ws = _ws(wb, "BNP")
    raekker = list(ws.iter_rows(values_only=True))

    def konv(val):
        if val is None:
            return 0
        s = str(val).strip()
        return {"++": 2, "+": 1, "--": -2, "-": -1}.get(s, 0)

    NAVN_MAP = {
        "financials":              "Financials",
        "real estate":             "Real Estate",
        "consumer discretionary":  "Consumer Discretionary",
        "infomation technology":   "Information Technology",
        "information technology":  "Information Technology",
        "industrials":             "Industrials",
        "materials":               "Materials",
        "consumer staples":        "Consumer Staples",
        "health care":             "Health Care",
        "energy":                  "Energy",
        "communications sercives": "Communications Services",
        "communications services": "Communications Services",
        "utilities":               "Utilities",
    }

    resultat = {}
    for i in range(3, min(14, len(raekker))):
        row = raekker[i]
        if not row[1]:
            continue
        key = str(row[1]).strip().lower()
        sektor = NAVN_MAP.get(key)
        if sektor:
            resultat[sektor] = {
                "Early":     konv(row[2]),
                "Mid":       konv(row[3]),
                "Late":      konv(row[4]),
                "Recession": konv(row[5]),
            }
    return resultat


def hent_makrofase(wb):
    def pmi_fase(v):
        if v < 45: return "Recession"
        if v < 50: return "Early"
        if v < 55: return "Mid"
        return "Late"

    def rate_fase(v):
        if v < 2.0: return "Recession"
        if v < 3.0: return "Early"
        if v < 4.0: return "Mid"
        return "Late"

    def cpi_fase(v):
        if v < 0.01: return "Recession"
        if v < 0.02: return "Early"
        if v < 0.03: return "Mid"
        return "Late"

    def vix_fase(v):
        if v >= 30: return "Recession"
        if v >= 20: return "Late"
        if v >= 15: return "Mid"
        return "Early"

    ws = _ws(wb, "Fremtid vækst", "Fremtid vaekst")
    fv = list(ws.iter_rows(values_only=True))

    def get_val(sektion_start, label):
        for i in range(sektion_start, min(sektion_start + 12, len(fv))):
            row = fv[i]
            if len(row) < 2:
                continue
            if row[1] and str(row[1]).strip() == label:
                val = row[3] if (len(row) > 3 and row[3] is not None) else None
                if val is None and len(row) > 2:
                    val = row[2]
                if val is not None:
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return None
        return None

    indikatorer = [
        ("PMI (DK)",   2,  "PMI",        pmi_fase),
        ("10yr (DK)",  2,  "10 YR rate", rate_fase),
        ("CPI (DK)",   2,  "CPI",        cpi_fase),
        ("VIX (DK)",   2,  "VIX",        vix_fase),
        ("PMI (EU)",   14, "PMI",        pmi_fase),
        ("10yr (EU)",  14, "10 YR rate", rate_fase),
        ("CPI (EU)",   14, "CPI",        cpi_fase),
        ("VIX (EU)",   14, "VIX",        vix_fase),
        ("PMI (USA)",  26, "PMI",        pmi_fase),
        ("10yr (USA)", 26, "10 YR rate", rate_fase),
        ("CPI (USA)",  26, "CPI",        cpi_fase),
        ("VIX (USA)",  26, "VIX",        vix_fase),
    ]

    FASE_SCORE = {"Early": 1, "Mid": 2, "Late": 3, "Recession": 0}
    SCORE_FASE = {0: "Recession", 1: "Early", 2: "Mid", 3: "Late"}

    faser_tal = []
    detaljer  = {}

    for (navn, start, label, fase_fn) in indikatorer:
        val = get_val(start, label)
        if val is not None:
            fase = fase_fn(val)
            faser_tal.append(FASE_SCORE[fase])
            detaljer[navn] = (val, fase)

    if faser_tal:
        gns = sum(faser_tal) / len(faser_tal)
        aktuel_fase = SCORE_FASE[round(gns)]
    else:
        aktuel_fase = "Mid"

    return aktuel_fase, detaljer


def hent_etf_liste(wb):
    ws = _ws(wb, "ETF - Liste")
    etf_liste = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0 or row[1] is None:
            continue
        etf_liste.append({
            "kategori": str(row[0]).strip() if row[0] else "",
            "navn":     str(row[1]).strip(),
            "isin":     str(row[2]).strip() if row[2] else "",
            "region":   str(row[3]).strip() if row[3] else "",
            "sektor":   str(row[4]).strip() if row[4] else "",
        })
    return etf_liste


def hent_aktier(wb, arknavn):
    """
    Henter aktieliste. Kolonnestruktur:
      DK:      A=navn(#VALUE!), B=pris, C=market_cap, D=change, E=industry, F=sektor, G=P/E, H=ticker
      EU/USA:  A=navn(#VALUE!), B=pris, C=market_cap, D=change, E=industry, F=sektor, G=ticker, H=P/E
    """
    ws = _ws(wb, arknavn)
    raekker = list(ws.iter_rows(values_only=True))
    if not raekker:
        return []

    header = raekker[0]
    # Find ticker-kolonnen ud fra header
    ticker_kol = 7  # default DK (H)
    for col_idx, hdr in enumerate(header):
        if hdr and str(hdr).strip().lower() in ("ticker", "ticker symbol"):
            ticker_kol = col_idx
            break

    aktier = []
    for i, row in enumerate(raekker):
        if i == 0:
            continue
        if len(row) < 6:
            continue

        navn_raa = row[0]
        if navn_raa is None or str(navn_raa).strip() == "#VALUE!":
            ticker = row[ticker_kol] if len(row) > ticker_kol else None
            if ticker is None or str(ticker).strip() in ("#VALUE!", ""):
                continue
            navn_display = str(ticker).strip()
        else:
            navn_display = str(navn_raa).strip()
            if not navn_display or navn_display == "#VALUE!":
                continue

        sektor = str(row[5]).strip() if row[5] else ""
        if not sektor or sektor == "#VALUE!":
            continue

        try:
            market_cap = float(row[2]) if row[2] is not None else 0.0
        except (TypeError, ValueError):
            market_cap = 0.0

        ticker_str = str(row[ticker_kol]).strip() if (len(row) > ticker_kol and row[ticker_kol]) else ""

        try:
            pris = float(row[1]) if row[1] is not None else 0.0
        except (TypeError, ValueError):
            pris = 0.0

        try:
            change = float(row[3]) if row[3] is not None else 0.0
        except (TypeError, ValueError):
            change = 0.0

        aktier.append({
            "navn":       navn_display,
            "ticker":     ticker_str,
            "market_cap": market_cap,
            "sektor":     sektor,
            "pris":       pris,
            "change":     change,
        })

    aktier.sort(key=lambda x: x["market_cap"], reverse=True)
    return aktier


def beregn_risikoprofil(sporgsmaal, profiler):
    sektion("RISIKOPROFILSPORGESKEEMA", C.MAGENTA)
    linje("Besvar venligst de 8 sporgsmal ved at indtaste et tal.")
    linje()

    total_score = 0
    max_score   = 0

    for q in sporgsmaal:
        print(f"\n  {C.BOLD}{C.WHITE}{q['tekst']}{C.RESET}")
        for s_idx, (svar_tekst, _score) in enumerate(zip(q["svar"], q["scores"]), start=1):
            print(f"    {C.CYAN}{s_idx}{C.RESET}. {svar_tekst}")

        n = len(q["svar"])
        valg  = sporg_tal(f"  Dit valg (1-{n}): ", min_val=1, max_val=n)
        point = q["scores"][valg - 1]
        total_score += point
        max_score   += max(q["scores"])

    score_ratio = total_score / max_score if max_score > 0 else 0.5

    valgt_profil = profiler[-1]
    for profil in profiler:
        if profil["fra"] <= score_ratio < profil["til"]:
            valgt_profil = profil
            break
    if score_ratio >= profiler[-1]["til"]:
        valgt_profil = profiler[-1]

    return valgt_profil, score_ratio, total_score, max_score


def beregn_sektor_scores(makro_scores, bnp_sensitivitet, aktuel_fase):
    """Final score = makro_avg * 0.7 + bnp_norm * 0.3  (bnp_norm = bnp_val+3)"""
    resultater = {}
    for sektor in ALLE_SEKTORER:
        makro_avg = makro_scores[sektor]["avg"]
        bnp_val   = bnp_sensitivitet.get(sektor, {}).get(aktuel_fase, 0)
        bnp_norm  = bnp_val + 3
        composite = makro_avg * 0.7 + bnp_norm * 0.3
        resultater[sektor] = {
            "makro_avg": makro_avg, "bnp_val": bnp_val,
            "bnp_norm":  bnp_norm,  "composite": composite,
            "dk":  makro_scores[sektor]["dk"],
            "eu":  makro_scores[sektor]["eu"],
            "usa": makro_scores[sektor]["usa"],
        }
    return sorted(resultater.items(), key=lambda x: x[1]["composite"], reverse=True)


def parse_aktivfordeling(tekst):
    fordeling = {}
    for del_str in tekst.split(","):
        del_str = del_str.strip()
        if not del_str:
            continue
        parts = del_str.replace("%", "").rsplit(None, 1)
        if len(parts) == 2:
            try:
                fordeling[parts[0].strip()] = float(parts[1]) / 100.0
            except ValueError:
                pass
    return fordeling


FASE_FARVE = {"Early": C.GREEN, "Mid": C.CYAN, "Late": C.YELLOW, "Recession": C.RED}
FASE_DANSK = {
    "Early": "Tidlig vaekst", "Mid": "Midt-cyklus",
    "Late":  "Sen cyklus",    "Recession": "Recession",
}
FASE_BESKRIVELSE = {
    "Early":     "Oekonomier vokser igen. Cykliske sektorer har fordelagtige udsigter.",
    "Mid":       "Solid vaekst med moderat inflation. Bred markedseksponering er fordelagtig.",
    "Late":      "Vaeksten aftager, inflationen stiger. Skift mod defensive sektorer.",
    "Recession": "Negativ vaekst. Defensive sektorer, guld og obligationer foretraekkes.",
}
BNP_LABELS = {2: "++", 1: " +", 0: " 0", -1: " -", -2: "--"}
PROFIL_FARVE = {
    "Konservativ": C.BLUE, "Balanceret": C.CYAN,
    "Vækstorienteret": C.GREEN, "Dynamisk": C.YELLOW,
}
AKTIV_FARVE = {
    "Obligationer": C.BLUE, "ETF": C.GREEN,
    "Aktier": C.YELLOW, "Alternative": C.MAGENTA,
}


def vis_velkomst():
    w = 72
    print()
    print(f"{C.CYAN}{C.BOLD}+{'='*w}+")
    print(f"|{'MAKROINVESTOR':^{w}}|")
    print(f"|{'Dansk makrooekonomisk investeringsanalyse':^{w}}|")
    print(f"+{'='*w}+{C.RESET}")
    linje()
    linje(f"{C.DIM}Version 1.0  |  Data: Q2 2026  |  Alle beloeb i DKK{C.RESET}")


def vis_makrofase(fase, detaljer):
    farve = FASE_FARVE.get(fase, C.WHITE)
    dansk = FASE_DANSK.get(fase, fase)
    sektion(f"AKTUEL MAKROOEKONOMISK FASE: {fase.upper()} -- {dansk}", farve)

    print(f"\n  {'Indikator':<22} {'Vaerdi':>10}  Fase")
    print(f"  {'─'*22} {'─'*10}  {'─'*12}")
    for navn, (val, ind_fase) in detaljer.items():
        ind_farve = FASE_FARVE.get(ind_fase, C.WHITE)
        print(f"  {navn:<22} {val:>10.3f}  {ind_farve}{ind_fase}{C.RESET}")

    print()
    print(f"  {farve}{C.BOLD}>>> Samlet fase: {fase} ({dansk}) <<<{C.RESET}")
    linje()
    linje(f"{C.DIM}{FASE_BESKRIVELSE.get(fase, '')}{C.RESET}")


def vis_risikoprofil(profil, score_ratio, total_score, max_score):
    sektion("DIN RISIKOPROFIL", C.MAGENTA)
    pfarve = PROFIL_FARVE.get(profil["navn"], C.WHITE)
    linje(f"Score:   {C.BOLD}{total_score}{C.RESET} / {max_score}  "
          f"({score_ratio*100:.0f}%)  {ascii_bar(score_ratio, max_score=1.0, bredde=20)}")
    linje()
    linje(f"Profil:  {pfarve}{C.BOLD}{profil['navn']}{C.RESET}")
    linje()
    linje(profil["beskrivelse"])
    linje()
    linje(f"{C.DIM}Aktivfordeling: {profil['aktivfordeling']}{C.RESET}")
    if profil["alternativer"]:
        linje(f"{C.DIM}Alternativer:   {profil['alternativer']}{C.RESET}")


def vis_sektor_anbefalinger(sorteret, aktuel_fase, top_n=5):
    farve = FASE_FARVE.get(aktuel_fase, C.WHITE)
    sektion(f"SEKTORSCORE OG ANBEFALINGER  (fase: {aktuel_fase})", farve)

    print(f"  {'Nr.':<4} {'Sektor':<30} {'Makro':>6} {'BNP':>4} {'Total':>6}  Bar")
    print(f"  {'─'*4} {'─'*30} {'─'*6} {'─'*4} {'─'*6}  {'─'*33}")

    for rang, (sektor, data) in enumerate(sorteret, start=1):
        bnp_str   = BNP_LABELS.get(data["bnp_val"], " 0")
        bnp_farve = (C.GREEN if data["bnp_val"] > 0
                     else (C.RED if data["bnp_val"] < 0 else C.DIM))
        bar       = ascii_bar(data["composite"], max_score=5.0, bredde=20)
        top_farve = C.GREEN if rang <= top_n else C.DIM
        prefix    = "*" if rang <= 3 else (">" if rang <= top_n else " ")

        print(f"  {top_farve}{prefix}{rang:<3}{C.RESET} {sektor:<30} "
              f"{data['makro_avg']:>6.2f} "
              f"{bnp_farve}{bnp_str:>4}{C.RESET} "
              f"{data['composite']:>6.2f}  {bar}")

    linje()
    linje(f"{C.DIM}Makro = vgtet gns (DK/EU/USA, 1-5)  |  BNP = fasesensitivitet  |  "
          f"Total = 70% makro + 30% BNP{C.RESET}")


def _find_etf(sektor, etf_liste):
    sl = sektor.lower().replace(" ", "")
    return [e for e in etf_liste
            if sl in e["sektor"].lower().replace(" ", "")
            or e["sektor"].lower().replace(" ", "") in sl]


def _find_aktier(sektor, aktier_dk, aktier_eu, aktier_usa, max_per=3):
    sl = sektor.lower()

    def match(s):
        return sl in s.lower() or s.lower() in sl

    return (
        [a for a in aktier_dk  if match(a["sektor"])][:max_per],
        [a for a in aktier_eu  if match(a["sektor"])][:max_per],
        [a for a in aktier_usa if match(a["sektor"])][:max_per],
    )


def vis_top_anbefalinger(sorteret, etf_liste, aktier_dk, aktier_eu, aktier_usa, top_n=5):
    sektion(f"TOP {top_n} SEKTORER: ETF'ER OG AKTIER", C.GREEN)

    for rang, (sektor, data) in enumerate(sorteret[:top_n], start=1):
        print(f"\n  {C.BOLD}{C.YELLOW}{'─'*68}{C.RESET}")
        print(f"  {C.BOLD}{C.YELLOW}{rang}. {sektor}  (Score: {data['composite']:.2f}){C.RESET}")
        print(f"     DK={data['dk']:.2f}  EU={data['eu']:.2f}  USA={data['usa']:.2f}")

        etfs = _find_etf(sektor, etf_liste)
        if etfs:
            print(f"\n     {C.CYAN}ETF'er:{C.RESET}")
            for etf in etfs:
                print(f"       - {etf['navn']}  [{etf['isin']}]  ({etf['region']})")
        else:
            print(f"\n     {C.DIM}Ingen matchende ETF'er fundet.{C.RESET}")

        dk_a, eu_a, usa_a = _find_aktier(sektor, aktier_dk, aktier_eu, aktier_usa)
        if dk_a or eu_a or usa_a:
            print(f"\n     {C.MAGENTA}Aktier (top efter markedsvaerdi):{C.RESET}")
            for region, aktion_liste in [("Danmark", dk_a), ("Europa", eu_a), ("USA", usa_a)]:
                if not aktion_liste:
                    continue
                print(f"       {C.BOLD}{region}:{C.RESET}")
                for a in aktion_liste:
                    mia = a["market_cap"] / 1e9
                    chg = a["change"] * 100
                    chg_str   = f"+{chg:.1f}%" if chg >= 0 else f"{chg:.1f}%"
                    chg_farve = C.GREEN if chg >= 0 else C.RED
                    print(f"         {a['ticker']:<10} {a['navn'][:25]:<25}"
                          f"  Mkt={mia:.0f}mia  {chg_farve}{chg_str}{C.RESET}")
        else:
            print(f"\n     {C.DIM}Ingen matchende aktier fundet.{C.RESET}")


def vis_aktivallokering(profil, beloeb):
    fordeling = parse_aktivfordeling(profil["aktivfordeling"])
    sektion("AKTIVALLOKERING", C.CYAN)
    linje(f"Investeringsbeloeb: {C.BOLD}{beloeb:,.0f} DKK{C.RESET}")
    linje(f"Risikoprofil:       {C.BOLD}{profil['navn']}{C.RESET}")
    linje()
    print(f"  {'Aktivklasse':<20} {'Andel':>7}  {'Beloeb (DKK)':>16}  Bar")
    print(f"  {'─'*20} {'─'*7}  {'─'*16}  {'─'*30}")
    for kategori, andel in fordeling.items():
        beloeb_del = beloeb * andel
        farve = AKTIV_FARVE.get(kategori, C.WHITE)
        bar   = ascii_bar(andel, max_score=1.0, bredde=20, farve=farve)
        print(f"  {farve}{kategori:<20}{C.RESET} {andel*100:>6.0f}%  {beloeb_del:>16,.0f}  {bar}")
    linje()
    if profil["alternativer"]:
        linje(f"{C.DIM}Alternative investeringer kan inkludere: {profil['alternativer']}{C.RESET}")


def vis_konklusion(profil, fase, top_sektorer, beloeb):
    sektion("SAMMENFATNING OG HANDLINGSPLAN", C.GREEN)
    fase_dansk = FASE_DANSK.get(fase, fase)
    linje(f"Makrofase:     {FASE_FARVE.get(fase, C.WHITE)}{C.BOLD}{fase} -- {fase_dansk}{C.RESET}")
    linje(f"Risikoprofil:  {C.BOLD}{profil['navn']}{C.RESET}")
    linje(f"Investering:   {C.BOLD}{beloeb:,.0f} DKK{C.RESET}")
    linje()
    linje(f"{C.BOLD}Anbefalede sektorer:{C.RESET}")
    for rang, (sektor, data) in enumerate(top_sektorer, start=1):
        stjerne = "***" if rang == 1 else ("**" if rang == 2 else ("*" if rang == 3 else " "))
        print(f"    {C.GREEN}{stjerne}{C.RESET} {rang}. {sektor}  (score: {data['composite']:.2f})")
    linje()
    linje(f"{C.DIM}NB: Denne analyse er vejledende og udgor ikke finansiel raadgivning.{C.RESET}")
    linje(f"{C.DIM}Invester altid paa baggrund af egen research og evt. professionel vejledning.{C.RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Makroinvestor - Dansk makrooekonomisk investeringsanalyse"
    )
    parser.add_argument(
        "--excel", "-e", default=DEFAULT_EXCEL,
        help=f"Sti til Excel-filen (standard: {DEFAULT_EXCEL})",
    )
    parser.add_argument(
        "--top", "-t", type=int, default=5,
        help="Antal top sektorer at vise (standard: 5)",
    )
    args = parser.parse_args()

    vis_velkomst()
    linje(f"\n{C.DIM}Indlaesser data fra:{C.RESET}")
    linje(f"{C.DIM}{args.excel}{C.RESET}")
    wb = load_wb(args.excel)

    sporgsmaal   = hent_sporgeskema(wb)
    profiler     = hent_risikoprofiler(wb)
    makro_scores = hent_makro_scores(wb)
    bnp_sensitiv = hent_bnp_sensitivitet(wb)
    etf_liste    = hent_etf_liste(wb)
    aktier_dk    = hent_aktier(wb, "Aktieliste DK")
    aktier_eu    = hent_aktier(wb, "Aktieliste EU")
    aktier_usa   = hent_aktier(wb, "Aktieliste USA")
    linje(f"{C.GREEN}Data indlaest succesfuldt.{C.RESET}")

    aktuel_fase, fase_detaljer = hent_makrofase(wb)
    vis_makrofase(aktuel_fase, fase_detaljer)

    linje()
    if sporgsmaal:
        linje("Tryk Enter for at starte risikoprofilsporgeskemaet...")
        input()
        valgt_profil, score_ratio, total_score, max_score = beregn_risikoprofil(
            sporgsmaal, profiler
        )
    else:
        linje(f"{C.YELLOW}Sporgeskeema ikke tilgaengeligt. Bruger 'Balanceret'.{C.RESET}")
        valgt_profil = profiler[1] if len(profiler) > 1 else profiler[0]
        score_ratio, total_score, max_score = 0.5, 20, 40

    vis_risikoprofil(valgt_profil, score_ratio, total_score, max_score)

    linje()
    beloeb = sporg_float("Hvor meget onsker du at investere (DKK)? ", min_val=0)

    sorteret_sektorer = beregn_sektor_scores(makro_scores, bnp_sensitiv, aktuel_fase)
    top_n = args.top

    vis_sektor_anbefalinger(sorteret_sektorer, aktuel_fase, top_n=top_n)
    vis_top_anbefalinger(
        sorteret_sektorer, etf_liste, aktier_dk, aktier_eu, aktier_usa, top_n=top_n
    )
    vis_aktivallokering(valgt_profil, beloeb)
    vis_konklusion(valgt_profil, aktuel_fase, sorteret_sektorer[:top_n], beloeb)

    w = 72
    print(f"\n{C.CYAN}{C.BOLD}+{'='*w}+")
    print(f"|{'Tak for at bruge Makroinvestor!':^{w}}|")
    print(f"+{'='*w}+{C.RESET}\n")


if __name__ == "__main__":
    main()
