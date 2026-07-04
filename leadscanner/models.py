import secrets
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

CONSENT_KONKURRENCE_VERSION = "v1"
CONSENT_DATADELING_VERSION = "v1"

PLAN_LIMITS = {
    "gratis": 25,
    "pro": 1000,
    "enterprise": 999999,
}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100))
    company = db.Column(db.String(100))
    plan = db.Column(db.String(20), default="gratis")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    exports = db.relationship("ExportLog", backref="user", lazy=True, order_by="ExportLog.created_at.desc()")

    def exports_this_month(self):
        now = datetime.utcnow()
        return sum(
            e.row_count for e in self.exports
            if e.created_at.month == now.month and e.created_at.year == now.year
        )

    def export_limit(self):
        return PLAN_LIMITS.get(self.plan, 25)

    def rows_remaining(self):
        limit = self.export_limit()
        if limit >= 999999:
            return "∞"
        return max(0, limit - self.exports_this_month())

    def can_export(self, row_count):
        limit = self.export_limit()
        if limit >= 999999:
            return True
        return self.exports_this_month() + row_count <= limit


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cvr_nummer = db.Column(db.String(20), unique=True, nullable=False, index=True)
    navn = db.Column(db.String(200), nullable=False)
    adresse = db.Column(db.String(200))
    postnr = db.Column(db.String(10), index=True)
    by = db.Column(db.String(100))
    branchekode = db.Column(db.String(10), index=True)
    branchetekst = db.Column(db.String(200))
    virksomhedsform = db.Column(db.String(100))
    status = db.Column(db.String(50), default="AKTIV", index=True)
    stiftelsesdato = db.Column(db.String(20))
    antal_ansatte_interval = db.Column(db.String(50))
    seneste_omsaetning = db.Column(db.Integer)
    seneste_regnskabsaar = db.Column(db.Integer)
    website = db.Column(db.String(300))
    email = db.Column(db.String(200))
    telefon = db.Column(db.String(50))
    data_quality_score = db.Column(db.Integer, default=0)
    last_verified_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_export_dict(self):
        return {
            "CVR-nummer": self.cvr_nummer,
            "Navn": self.navn,
            "Adresse": self.adresse or "",
            "Postnr": self.postnr or "",
            "By": self.by or "",
            "Branchekode": self.branchekode or "",
            "Branche": self.branchetekst or "",
            "Virksomhedsform": self.virksomhedsform or "",
            "Status": self.status or "",
            "Ansatte": self.antal_ansatte_interval or "",
            "Omsætning (seneste år)": self.seneste_omsaetning or "",
            "Regnskabsår": self.seneste_regnskabsaar or "",
            "Website": self.website or "",
            "Email": self.email or "",
            "Telefon": self.telefon or "",
            "Datakvalitet": f"{self.data_quality_score}%",
            "Sidst verificeret": self.last_verified_at.strftime("%Y-%m-%d") if self.last_verified_at else "",
        }


class ExportLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    row_count = db.Column(db.Integer, default=0)
    filters_used = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CollectionRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filters_used = db.Column(db.Text)
    companies_found = db.Column(db.Integer, default=0)
    companies_new = db.Column(db.Integer, default=0)
    companies_updated = db.Column(db.Integer, default=0)
    source_mode = db.Column(db.String(20), default="simuleret")
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="running")
    error = db.Column(db.Text)


class CompetitionRound(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(200), nullable=False)
    praemie_beskrivelse = db.Column(db.String(300), nullable=False)
    starter_at = db.Column(db.DateTime, default=datetime.utcnow)
    slutter_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="aktiv")  # aktiv | afsluttet
    vinder_participant_id = db.Column(db.Integer, db.ForeignKey("participant.id"), nullable=True)
    trukket_at = db.Column(db.DateTime)
    participants = db.relationship(
        "Participant", backref="competition_round", lazy=True,
        foreign_keys="Participant.competition_round_id",
    )

    def participant_count(self):
        return len(self.participants)

    def datadeling_count(self):
        return sum(1 for p in self.participants if p.samtykke_datadeling)


class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    competition_round_id = db.Column(db.Integer, db.ForeignKey("competition_round.id"), nullable=False)
    navn = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), nullable=False, index=True)
    telefon = db.Column(db.String(50))
    spin_result = db.Column(db.String(100))
    ip_address = db.Column(db.String(64))

    samtykke_konkurrence = db.Column(db.Boolean, default=True, nullable=False)
    samtykke_konkurrence_version = db.Column(db.String(10), default=CONSENT_KONKURRENCE_VERSION)
    samtykke_konkurrence_at = db.Column(db.DateTime, default=datetime.utcnow)

    samtykke_datadeling = db.Column(db.Boolean, default=False, nullable=False)
    samtykke_datadeling_version = db.Column(db.String(10))
    samtykke_datadeling_at = db.Column(db.DateTime)

    unsubscribe_token = db.Column(db.String(64), unique=True, default=lambda: secrets.token_urlsafe(24))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("competition_round_id", "email", name="uq_participant_round_email"),
    )

    def to_export_dict(self):
        return {
            "Navn": self.navn,
            "Email": self.email,
            "Telefon": self.telefon or "",
            "Tilmeldt": self.created_at.strftime("%Y-%m-%d %H:%M"),
            "Samtykke datadeling (version)": self.samtykke_datadeling_version or "",
            "Samtykke datadeling givet": self.samtykke_datadeling_at.strftime("%Y-%m-%d %H:%M") if self.samtykke_datadeling_at else "",
        }
