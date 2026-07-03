import csv
import io
import json
import os
from datetime import datetime
from functools import wraps

import bcrypt
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from models import db, User, Company, ExportLog, CollectionRun, PLAN_LIMITS
from cvr_client import HAS_LIVE_CVR

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "leadscanner-dev-secret-change-in-prod")

_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leadscanner.db")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", f"sqlite:///{_db_path}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log ind for at søge i virksomhedsdata"

BRANCHER = [
    ("412000", "Opførelse af bygninger"),
    ("433410", "Malerarbejde"),
    ("432100", "El-installation"),
    ("432200", "VVS- og blikkenslagerforretning"),
    ("433200", "Tømrer- og bygningssnedkervirksomhed"),
    ("620200", "IT-konsulentbistand"),
    ("702200", "Virksomhedsrådgivning"),
    ("479110", "Detailhandel via internet"),
]


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()
        company = request.form.get("company", "").strip()

        if not email or not password:
            flash("Udfyld email og adgangskode", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Der findes allerede en bruger med denne email", "error")
            return render_template("register.html")

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user = User(email=email, password_hash=password_hash, name=name, company=company)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Forkert email eller adgangskode", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


def _apply_filters(query):
    q = request.args.get("q", "").strip()
    branche = request.args.get("branche", "").strip()
    by = request.args.get("by", "").strip()
    min_ansatte = request.args.get("min_ansatte", "").strip()
    status = request.args.get("status", "aktiv").strip()

    if q:
        query = query.filter(Company.navn.ilike(f"%{q}%"))
    if branche:
        query = query.filter(Company.branchekode == branche)
    if by:
        query = query.filter(Company.by.ilike(f"%{by}%"))
    if status == "aktiv":
        query = query.filter(Company.status == "AKTIV")
    if min_ansatte:
        # antal_ansatte_interval er tekst ("10-19" osv.) — simpelt prefix-filter på nedre grænse
        query = query.filter(Company.antal_ansatte_interval.isnot(None))

    return query


@app.route("/dashboard")
@login_required
def dashboard():
    query = Company.query
    query = _apply_filters(query)
    total_matches = query.count()
    companies = query.order_by(Company.data_quality_score.desc()).limit(100).all()

    return render_template(
        "dashboard.html",
        companies=companies,
        total_matches=total_matches,
        total_in_db=Company.query.count(),
        brancher=BRANCHER,
        has_live_cvr=HAS_LIVE_CVR,
        current_filters=request.args,
    )


@app.route("/company/<cvr_nummer>")
@login_required
def company_detail(cvr_nummer):
    company = Company.query.filter_by(cvr_nummer=cvr_nummer).first_or_404()
    return render_template("company_detail.html", company=company)


@app.route("/export", methods=["POST"])
@login_required
def export_csv():
    cvr_numre = request.form.getlist("cvr_nummer")
    if not cvr_numre:
        flash("Vælg mindst én virksomhed at eksportere", "error")
        return redirect(url_for("dashboard"))

    companies = Company.query.filter(Company.cvr_nummer.in_(cvr_numre)).all()

    if not current_user.can_export(len(companies)):
        flash(f"Din {current_user.plan}-plan har nået eksportgrænsen for denne måned. Opgrader for flere.", "error")
        return redirect(url_for("dashboard"))

    output = io.StringIO()
    if companies:
        fieldnames = list(companies[0].to_export_dict().keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for c in companies:
            writer.writerow(c.to_export_dict())

    log = ExportLog(
        user_id=current_user.id,
        row_count=len(companies),
        filters_used=json.dumps(dict(request.args), ensure_ascii=False),
    )
    db.session.add(log)
    db.session.commit()

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leadscanner_export_{datetime.utcnow().date()}.csv"},
    )


@app.route("/collect", methods=["GET", "POST"])
@login_required
def collect():
    if request.method == "POST":
        from pipeline import run_collection

        branchekoder = request.form.getlist("branchekoder") or None
        postnr_raw = request.form.get("postnumre", "").strip()
        postnumre = [p.strip() for p in postnr_raw.split(",") if p.strip()] or None
        limit = int(request.form.get("limit", 25))
        enrich = request.form.get("enrich") == "on"

        run = run_collection(
            branchekoder=branchekoder, postnumre=postnumre,
            limit=limit, enrich=enrich,
        )
        flash(
            f"Indsamling færdig ({run.source_mode}): {run.companies_found} virksomheder fundet "
            f"({run.companies_new} nye, {run.companies_updated} opdateret).",
            "success",
        )
        return redirect(url_for("dashboard"))

    recent_runs = CollectionRun.query.order_by(CollectionRun.started_at.desc()).limit(10).all()
    return render_template("collect.html", brancher=BRANCHER, recent_runs=recent_runs, has_live_cvr=HAS_LIVE_CVR)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
