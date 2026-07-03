"""
Berigelse af virksomhedsdata:
- data_quality_score: hvor komplet/frisk er profilen?
- find_website_and_contact: best-effort opslag af officiel hjemmeside + offentlig kontaktinfo
"""

import re
import urllib.robotparser
from urllib.parse import urlparse

import requests

try:
    from duckduckgo_search import DDGS
    HAS_SEARCH = True
except ImportError:
    HAS_SEARCH = False

USER_AGENT = "leadscanner/1.0 (+dataindsamling til B2B-leads)"

QUALITY_FIELDS = [
    "navn", "adresse", "postnr", "by", "branchekode", "branchetekst",
    "virksomhedsform", "status", "antal_ansatte_interval",
    "seneste_omsaetning", "website", "email", "telefon",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+45\s?)?(?:\d{2}\s?){3,4}\d{2}")


def data_quality_score(company_dict):
    filled = sum(1 for f in QUALITY_FIELDS if company_dict.get(f))
    return round(100 * filled / len(QUALITY_FIELDS))


def _robots_allow(url):
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def find_website_and_contact(company_navn, by=None):
    """
    Best-effort: finder virksomhedens officielle hjemmeside via websøgning og
    udtrækker offentligt telefonnummer/email fra forsiden, hvis robots.txt tillader det.
    Fejler blødt (returnerer tomme felter) — bruges kun som ekstra berigelse.
    """
    result = {"website": None, "email": None, "telefon": None}
    if not HAS_SEARCH:
        return result

    query = f"{company_navn} {by or ''} officiel hjemmeside".strip()
    try:
        with DDGS() as ddgs:
            hits = list(ddgs.text(query, max_results=3))
    except Exception:
        return result

    for hit in hits:
        url = hit.get("href", "")
        if not url or not url.startswith("http"):
            continue
        if any(bad in url for bad in ("facebook.com", "linkedin.com", "krak.dk", "proff.dk", "cvr.dk")):
            continue
        result["website"] = url
        if not _robots_allow(url):
            break
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=8)
            if resp.status_code == 200:
                text = resp.text
                email_match = EMAIL_RE.search(text)
                phone_match = PHONE_RE.search(text)
                if email_match:
                    result["email"] = email_match.group(0)
                if phone_match:
                    result["telefon"] = phone_match.group(0).strip()
        except requests.RequestException:
            pass
        break

    return result
