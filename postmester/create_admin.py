"""Kør dette script én gang for at oprette admin-bruger med Pro-adgang."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("SECRET_KEY", "setup")
os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")

from app import app, db
from models import User
import bcrypt

EMAIL    = "antont16@gmail.com"
PASSWORD = "PostMester2025!"
NAME     = "Anton"
PLAN     = "pro"

with app.app_context():
    db.create_all()
    existing = User.query.filter_by(email=EMAIL).first()
    if existing:
        existing.plan = PLAN
        existing.password_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
        db.session.commit()
        print(f"✅ Opdateret: {EMAIL} → plan={PLAN}")
    else:
        pw = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
        user = User(email=EMAIL, password_hash=pw, name=NAME, plan=PLAN)
        db.session.add(user)
        db.session.commit()
        print(f"✅ Oprettet: {EMAIL} → plan={PLAN}")

print(f"\nLog ind med:\n  Email:    {EMAIL}\n  Password: {PASSWORD}")
