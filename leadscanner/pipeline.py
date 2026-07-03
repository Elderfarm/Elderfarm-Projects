"""
Indsamlings-pipeline: henter virksomheder fra CVR, beriger dem, og upserter i databasen.

Kør som CLI:
    python pipeline.py --branche 412000,433200 --postnr 2100,8000 --limit 50 --enrich

Eller kald run_collection(...) direkte fra app.py.
"""

import argparse
import json
from datetime import datetime

from cvr_client import search_companies, HAS_LIVE_CVR
from enrichment import data_quality_score, find_website_and_contact
from models import db, Company, CollectionRun


def run_collection(branchekoder=None, postnumre=None, min_ansatte=None, limit=25, enrich=False):
    run = CollectionRun(
        filters_used=json.dumps({
            "branchekoder": branchekoder, "postnumre": postnumre,
            "min_ansatte": min_ansatte, "limit": limit,
        }, ensure_ascii=False),
        source_mode="live" if HAS_LIVE_CVR else "simuleret",
        status="running",
    )
    db.session.add(run)
    db.session.commit()

    try:
        raw_companies, source = search_companies(
            branchekoder=branchekoder, postnumre=postnumre,
            min_ansatte=min_ansatte, limit=limit,
        )
        new_count, updated_count = 0, 0

        for raw in raw_companies:
            if enrich:
                contact = find_website_and_contact(raw["navn"], raw.get("by"))
                raw.update({k: v for k, v in contact.items() if v})

            score = data_quality_score(raw)
            company = Company.query.filter_by(cvr_nummer=raw["cvr_nummer"]).first()

            if company is None:
                company = Company(cvr_nummer=raw["cvr_nummer"])
                db.session.add(company)
                new_count += 1
            else:
                updated_count += 1

            for field in (
                "navn", "adresse", "postnr", "by", "branchekode", "branchetekst",
                "virksomhedsform", "status", "stiftelsesdato", "antal_ansatte_interval",
                "seneste_omsaetning", "seneste_regnskabsaar", "website", "email", "telefon",
            ):
                if raw.get(field) is not None:
                    setattr(company, field, raw[field])

            company.data_quality_score = score
            company.last_verified_at = datetime.utcnow()

        run.companies_found = len(raw_companies)
        run.companies_new = new_count
        run.companies_updated = updated_count
        run.source_mode = source
        run.status = "done"
        run.finished_at = datetime.utcnow()
        db.session.commit()
        return run

    except Exception as e:
        run.status = "failed"
        run.error = str(e)
        run.finished_at = datetime.utcnow()
        db.session.commit()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kør en CVR-dataindsamling")
    parser.add_argument("--branche", type=str, default="", help="Kommasepareret liste af branchekoder")
    parser.add_argument("--postnr", type=str, default="", help="Kommasepareret liste af postnumre")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--enrich", action="store_true", help="Slå website/kontakt op for hver virksomhed")
    args = parser.parse_args()

    from app import app  # sikrer app-context og db-binding

    with app.app_context():
        result = run_collection(
            branchekoder=[b for b in args.branche.split(",") if b] or None,
            postnumre=[p for p in args.postnr.split(",") if p] or None,
            limit=args.limit,
            enrich=args.enrich,
        )
        print(f"Kørsel færdig ({result.source_mode}): {result.companies_found} fundet, "
              f"{result.companies_new} nye, {result.companies_updated} opdateret.")
