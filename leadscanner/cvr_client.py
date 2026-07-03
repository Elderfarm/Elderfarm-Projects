"""
CVR-klient — henter danske virksomhedsdata.

To lag:
1. Datafordelerens fulde CVR-søge-API (bulk, filtrerbart på branche/region) —
   kræver en GRATIS konto på https://datafordeler.dk (kan ikke oprettes automatisk).
   Sæt CVR_API_USER + CVR_API_PASSWORD for at aktivere.
2. cvrapi.dk til enkelt-opslag på CVR-nummer (gratis, rate-begrænset, ingen login).

Uden credentials falder klienten tilbage til SIMULERET data, så resten af
systemet kan bygges, testes og demonstreres uden ekstern adgang.
"""

import os
import random
import requests

CVR_API_USER = os.environ.get("CVR_API_USER")
CVR_API_PASSWORD = os.environ.get("CVR_API_PASSWORD")
HAS_LIVE_CVR = bool(CVR_API_USER and CVR_API_PASSWORD)

CVRAPI_URL = "https://cvrapi.dk/api"
USER_AGENT = "leadscanner/1.0 (dataindsamling til B2B-leads)"

_BRANCHER = {
    "412000": "Opførelse af bygninger",
    "433410": "Malerarbejde",
    "432100": "El-installation",
    "432200": "VVS- og blikkenslagerforretning",
    "433200": "Tømrer- og bygningssnedkervirksomhed",
    "620200": "Konsulentbistand vedr. informationsteknologi",
    "702200": "Virksomhedsrådgivning",
    "479110": "Detailhandel via internet",
}
_BYER = [("2100", "København Ø"), ("8000", "Aarhus C"), ("5000", "Odense C"),
         ("9000", "Aalborg"), ("4000", "Roskilde"), ("6700", "Esbjerg")]
_FORMER = ["Enkeltmandsvirksomhed", "Anpartsselskab", "Aktieselskab", "Interessentskab"]


def _simulate_companies(branchekoder, postnumre, limit):
    random.seed(f"{branchekoder}-{postnumre}-{limit}")
    results = []
    for i in range(limit):
        kode = random.choice(branchekoder) if branchekoder else random.choice(list(_BRANCHER))
        if postnumre:
            postnr = random.choice(postnumre)
            by = next((b for p, b in _BYER if p == postnr), "Ukendt by")
        else:
            postnr, by = random.choice(_BYER)
        cvr = str(random.randint(10000000, 39999999))
        results.append({
            "cvr_nummer": cvr,
            "navn": f"{random.choice(['Nordic', 'Dansk', 'Elite', 'Prima', 'Byg', 'Nord'])} "
                    f"{random.choice(['Byg', 'Service', 'Solutions', 'Håndværk', 'Consult'])} "
                    f"{random.choice(['ApS', 'A/S', ''])}".strip(),
            "adresse": f"{random.choice(['Hovedgade', 'Industrivej', 'Fabriksvej', 'Havnegade'])} {random.randint(1, 99)}",
            "postnr": postnr,
            "by": by,
            "branchekode": kode,
            "branchetekst": _BRANCHER.get(kode, "Ukendt branche"),
            "virksomhedsform": random.choice(_FORMER),
            "status": "AKTIV" if random.random() > 0.08 else "OPHØRT",
            "stiftelsesdato": f"{random.randint(2005, 2024)}-{random.randint(1,12):02d}-01",
            "antal_ansatte_interval": random.choice(["1-1", "2-4", "5-9", "10-19", "20-49", "50-99"]),
            "seneste_omsaetning": random.choice([None, random.randint(500_000, 45_000_000)]),
            "seneste_regnskabsaar": 2025,
        })
    return results


def search_companies(branchekoder=None, postnumre=None, min_ansatte=None, limit=25):
    """
    Søger virksomheder på tværs af branche/region.
    Returnerer (liste_af_virksomheder, kilde) hvor kilde er "live" eller "simuleret".
    """
    if not HAS_LIVE_CVR:
        return _simulate_companies(branchekoder or [], postnumre or [], limit), "simuleret"

    # Datafordelerens CVR-søge-API (Elasticsearch-baseret).
    # Struktur/felter kan afvige — test og juster mod den faktiske respons når
    # credentials er sat op, jf. dokumentationen på datafordeler.dk.
    try:
        query = {"size": limit, "query": {"bool": {"must": []}}}
        if branchekoder:
            query["query"]["bool"]["must"].append(
                {"terms": {"Vrvirksomhed.virksomhedMetadata.nyesteHovedbranche.branchekode": branchekoder}}
            )
        if postnumre:
            query["query"]["bool"]["must"].append(
                {"terms": {"Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.postnummer": postnumre}}
            )
        resp = requests.post(
            "http://distribution.virk.dk/cvr-permanent/virksomhed/_search",
            json=query,
            auth=(CVR_API_USER, CVR_API_PASSWORD),
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        return [_parse_live_hit(h) for h in hits], "live"
    except requests.RequestException:
        return _simulate_companies(branchekoder or [], postnumre or [], limit), "simuleret"


def _parse_live_hit(hit):
    v = hit.get("_source", {}).get("Vrvirksomhed", {})
    meta = v.get("virksomhedMetadata", {})
    branche = meta.get("nyesteHovedbranche", {})
    adresse = meta.get("nyesteBeliggenhedsadresse", {})
    return {
        "cvr_nummer": str(v.get("cvrNummer", "")),
        "navn": meta.get("nyesteNavn", {}).get("navn", ""),
        "adresse": f"{adresse.get('vejnavn', '')} {adresse.get('husnummerFra', '')}".strip(),
        "postnr": str(adresse.get("postnummer", "")),
        "by": adresse.get("postdistrikt", ""),
        "branchekode": str(branche.get("branchekode", "")),
        "branchetekst": branche.get("branchetekst", ""),
        "virksomhedsform": meta.get("nyesteVirksomhedsform", {}).get("langBeskrivelse", ""),
        "status": meta.get("sammensatStatus", "AKTIV"),
        "stiftelsesdato": v.get("stiftelsesDato", ""),
        "antal_ansatte_interval": meta.get("nyesteAntalAnsatte", {}).get("intervalKodeAntalAnsatte", ""),
        "seneste_omsaetning": None,
        "seneste_regnskabsaar": None,
    }


def lookup_single(cvr_nummer):
    """Slår et enkelt CVR-nummer op via det gratis cvrapi.dk (til berigelse/verificering)."""
    try:
        resp = requests.get(
            CVRAPI_URL,
            params={"search": cvr_nummer, "country": "dk"},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None
