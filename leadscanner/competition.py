"""
Konkurrence-modul: "Spin & vind" leadgenerering.

Lykkehjulet er et rent engagement-mekanisme (ingen instant-gevinst) — den
faktiske præmie findes ved en tilfældig lodtrækning blandt alle gyldige
tilmeldinger (se /admin/konkurrence). Det holder mekanikken fri af
spilleretlige spørgsmål, da deltagelse er gratis og gevinsten trækkes
uafhængigt af selve spinnet.

Samtykke er opdelt i to felter, jf. GDPR-krav om specifikt/informeret
samtykke: konkurrence-deltagelse (påkrævet) og datadeling med
samarbejdspartnere (valgfrit, og det ENESTE der styrer hvem der må med i
/admin/konkurrence/export).
"""

import csv
import io
import random
from datetime import datetime

from flask import Blueprint, request, render_template, redirect, url_for, flash, Response
from flask_login import login_required

from models import db, CompetitionRound, Participant, CONSENT_KONKURRENCE_VERSION, CONSENT_DATADELING_VERSION

competition_bp = Blueprint("competition", __name__)

DEFAULT_TITEL = "Sommerkonkurrence"
DEFAULT_PRAEMIE = "5.000 kr. gavekort til Rema 1000"


def get_active_round():
    """Bruges af de offentlige sider — sikrer der altid er en runde man kan tilmelde sig."""
    round_ = CompetitionRound.query.filter_by(status="aktiv").order_by(CompetitionRound.starter_at.desc()).first()
    if round_ is None:
        round_ = CompetitionRound(titel=DEFAULT_TITEL, praemie_beskrivelse=DEFAULT_PRAEMIE, status="aktiv")
        db.session.add(round_)
        db.session.commit()
    return round_


def get_latest_round():
    """Bruges af admin-siderne — viser altid den seneste runde (uanset status),
    så admin-visningen ikke overskrives af en tom ny runde, når den nuværende
    afsluttes (fx efter en lodtrækning)."""
    round_ = CompetitionRound.query.order_by(CompetitionRound.starter_at.desc()).first()
    if round_ is None:
        round_ = get_active_round()
    return round_


@competition_bp.route("/vind")
def landing():
    round_ = get_active_round()
    return render_template("competition/landing.html", round=round_)


@competition_bp.route("/vind/tilmeld", methods=["POST"])
def tilmeld():
    round_ = get_active_round()

    navn = request.form.get("navn", "").strip()
    email = request.form.get("email", "").strip().lower()
    telefon = request.form.get("telefon", "").strip()
    spin_result = request.form.get("spin_result", "").strip()
    samtykke_konkurrence = request.form.get("samtykke_konkurrence") == "on"
    samtykke_datadeling = request.form.get("samtykke_datadeling") == "on"

    if not navn or not email:
        flash("Udfyld navn og email for at deltage", "error")
        return redirect(url_for("competition.landing"))

    if not samtykke_konkurrence:
        flash("Du skal acceptere deltagerbetingelserne for at deltage i konkurrencen", "error")
        return redirect(url_for("competition.landing"))

    existing = Participant.query.filter_by(competition_round_id=round_.id, email=email).first()
    if existing:
        flash("Denne email er allerede tilmeldt konkurrencen", "error")
        return redirect(url_for("competition.landing"))

    participant = Participant(
        competition_round_id=round_.id,
        navn=navn,
        email=email,
        telefon=telefon or None,
        spin_result=spin_result or None,
        ip_address=request.remote_addr,
        samtykke_konkurrence=True,
        samtykke_konkurrence_version=CONSENT_KONKURRENCE_VERSION,
        samtykke_konkurrence_at=datetime.utcnow(),
        samtykke_datadeling=samtykke_datadeling,
        samtykke_datadeling_version=CONSENT_DATADELING_VERSION if samtykke_datadeling else None,
        samtykke_datadeling_at=datetime.utcnow() if samtykke_datadeling else None,
    )
    db.session.add(participant)
    db.session.commit()

    return redirect(url_for("competition.tak"))


@competition_bp.route("/vind/tak")
def tak():
    return render_template("competition/tak.html")


@competition_bp.route("/vind/vilkaar")
def vilkaar():
    return render_template("competition/vilkaar.html", praemie=DEFAULT_PRAEMIE)


@competition_bp.route("/vind/privatliv")
def privatliv():
    return render_template("competition/privatliv.html")


@competition_bp.route("/vind/afmeld/<token>")
def afmeld(token):
    participant = Participant.query.filter_by(unsubscribe_token=token).first()
    if participant is None:
        flash("Linket er ugyldigt eller allerede brugt", "error")
        return redirect(url_for("competition.landing"))

    participant.samtykke_datadeling = False
    db.session.commit()
    flash("Dit samtykke til datadeling er nu trukket tilbage. Du er stadig med i konkurrencen.", "success")
    return redirect(url_for("competition.landing"))


# ── Admin ────────────────────────────────────────────────────────────────

@competition_bp.route("/admin/konkurrence")
@login_required
def admin_overview():
    round_id = request.args.get("round_id", type=int)
    round_ = db.session.get(CompetitionRound, round_id) if round_id else None
    if round_ is None:
        round_ = get_latest_round()

    all_rounds = CompetitionRound.query.order_by(CompetitionRound.starter_at.desc()).all()
    recent = Participant.query.filter_by(competition_round_id=round_.id).order_by(Participant.created_at.desc()).limit(50).all()
    return render_template("competition/admin.html", round=round_, participants=recent, all_rounds=all_rounds)


def _round_from_request():
    round_id = request.form.get("round_id", type=int)
    round_ = db.session.get(CompetitionRound, round_id) if round_id else None
    return round_ if round_ is not None else get_latest_round()


@competition_bp.route("/admin/konkurrence/traek-vinder", methods=["POST"])
@login_required
def traek_vinder():
    round_ = _round_from_request()
    if not round_.participants:
        flash("Ingen deltagere at trække blandt endnu", "error")
        return redirect(url_for("competition.admin_overview", round_id=round_.id))

    vinder = random.choice(round_.participants)
    round_.vinder_participant_id = vinder.id
    round_.trukket_at = datetime.utcnow()
    round_.status = "afsluttet"
    db.session.commit()

    flash(f"Vinder trukket: {vinder.navn} ({vinder.email})", "success")
    return redirect(url_for("competition.admin_overview", round_id=round_.id))


@competition_bp.route("/admin/konkurrence/export", methods=["POST"])
@login_required
def export_participants():
    round_ = _round_from_request()
    consenting = [p for p in round_.participants if p.samtykke_datadeling]

    output = io.StringIO()
    if consenting:
        fieldnames = list(consenting[0].to_export_dict().keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for p in consenting:
            writer.writerow(p.to_export_dict())

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=konkurrence_leads_{datetime.utcnow().date()}.csv"},
    )
