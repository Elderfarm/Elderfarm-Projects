import os
import base64
import bcrypt
import stripe
import anthropic
import requests
import uuid
import string
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from pathlib import Path
from models import db, User, Post, SmsLog

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "postmester-dev-secret-change-in-prod")

# Brug absolut sti til SQLite så Railway kan finde den
_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "postmester.db")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", f"sqlite:///{_db_path}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

db.init_app(app)

with app.app_context():
    db.create_all()

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log ind for at generere opslag"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
PLATFORMS = {"facebook": "Facebook", "instagram": "Instagram", "both": "Facebook og Instagram"}
TONES = {"professionel": "professionel og tillidsfuld", "venlig": "venlig og uformel", "salgsorienteret": "salgsorienteret og overbevisende"}


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_post_ai(description, platform, tone, image_data, image_media_type, company_name=None):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY ikke sat"}

    client = anthropic.Anthropic(api_key=api_key)
    platform_label = PLATFORMS.get(platform, "Facebook")
    tone_label = TONES.get(tone, "professionel og tillidsfuld")
    company_line = f"Virksomhedsnavn: {company_name}. Nævn det naturligt i opslaget." if company_name else ""

    system = f"""Du er en ekspert i dansk social media markedsføring for håndværksvirksomheder.
Du skriver {platform_label}-opslag der er korte, engagerende og lokale.
{company_line}
Regler: Skriv på naturligt uformelt dansk. Max 3-4 afsnit. 2-4 emojis. Slut med call-to-action. Tone: {tone_label}. Skriv KUN selve opslaget."""

    parts = []
    if image_data:
        parts.append({"type": "image", "source": {"type": "base64", "media_type": image_media_type, "data": base64.standard_b64encode(image_data).decode()}})
    parts.append({"type": "text", "text": f"Skriv et {platform_label}-opslag til en dansk håndværksvirksomhed:\n\n{description}"})

    resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=600, system=system, messages=[{"role": "user", "content": parts}])
    post_text = resp.content[0].text.strip()

    tag_resp = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=100,
        messages=[{"role": "user", "content": f"5-8 relevante hashtags til håndværker-opslag om: {description}. Kun hashtags adskilt af mellemrum."}]
    )
    hashtags = tag_resp.content[0].text.strip()

    return {"post": post_text, "hashtags": hashtags, "platform": platform_label}


# ── Auth routes ────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()
        company = request.form.get("company", "").strip()

        if not email or not password or len(password) < 6:
            flash("Udfyld alle felter (password min. 6 tegn)", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Den email er allerede i brug", "error")
            return render_template("register.html")

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        ref_code = _make_referral_code()
        user = User(email=email, password_hash=pw_hash, name=name, company=company, referral_code=ref_code)

        # Handle referral cookie
        ref = request.cookies.get("ref")
        if ref:
            referrer = User.query.filter_by(referral_code=ref).first()
            if referrer and referrer.email != email:
                user.referred_by = referrer.id
                # Give referrer 3 bonus posts
                referrer.referral_bonus_posts = (referrer.referral_bonus_posts or 0) + 3

        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            login_user(user, remember=True)
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Forkert email eller password", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ── Main routes ────────────────────────────────────────

@app.before_request
def redirect_www():
    from flask import request, redirect
    host = request.host
    if host and host.startswith("www."):
        url = request.url.replace("://www.", "://", 1)
        return redirect(url, code=301)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
@login_required
def dashboard():
    posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.created_at.desc()).limit(20).all()
    now = datetime.utcnow()
    posts_month_count = Post.query.filter(
        Post.user_id == current_user.id,
        db.extract("month", Post.created_at) == now.month,
        db.extract("year", Post.created_at) == now.year,
    ).count()
    scheduled_count = Post.query.filter(
        Post.user_id == current_user.id,
        Post.scheduled_at != None,
        Post.is_published == False,
    ).count()
    sms_count = SmsLog.query.filter_by(user_id=current_user.id).count()
    month_name = ["januar","februar","marts","april","maj","juni","juli","august","september","oktober","november","december"][now.month - 1]
    return render_template(
        "dashboard.html",
        posts=posts,
        posts_month_count=posts_month_count,
        scheduled_count=scheduled_count,
        sms_count=sms_count,
        month_name=month_name,
    )


@app.route("/generate", methods=["POST"])
@login_required
def generate():
    if not current_user.can_generate():
        return jsonify({"error": f"Du har brugt dine {2} opslag denne måned. Opgradér til Starter for ubegrænsede opslag."}), 403

    description = request.form.get("description", "").strip()
    platform = request.form.get("platform", "facebook")
    tone = request.form.get("tone", "professionel")

    if not description:
        return jsonify({"error": "Beskriv venligst jobbet"}), 400

    image_data = None
    image_media_type = None
    saved_filename = None
    if "photo" in request.files:
        file = request.files["photo"]
        if file and file.filename and allowed_file(file.filename):
            image_data = file.read()
            ext = file.filename.rsplit(".", 1)[1].lower()
            image_media_type = f"image/{'jpeg' if ext == 'jpg' else ext}"
            saved_filename = f"{uuid.uuid4().hex}.{ext}"
            image_path = os.path.join(UPLOAD_FOLDER, saved_filename)
            with open(image_path, "wb") as f:
                f.write(image_data)

    try:
        result = generate_post_ai(description, platform, tone, image_data, image_media_type, company_name=current_user.company or None)
        if "error" in result:
            return jsonify(result), 500

        post = Post(
            user_id=current_user.id,
            description=description,
            platform=platform,
            tone=tone,
            post_text=result["post"],
            hashtags=result.get("hashtags", ""),
            image_filename=saved_filename,
        )
        db.session.add(post)
        db.session.commit()

        result["posts_remaining"] = current_user.posts_remaining()
        result["post_id"] = post.id
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/sms", methods=["POST"])
@login_required
def send_sms():
    if current_user.plan != "pro":
        return jsonify({"error": "SMS-funktion kræver Pro-plan."}), 403

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")

    if not account_sid or not auth_token or not from_number:
        return jsonify({"error": "Twilio er ikke sat op — tilføj TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN og TWILIO_FROM_NUMBER i Railway"}), 500

    customer_name = request.form.get("customer_name", "").strip()
    phone = request.form.get("phone", "").strip()
    google_url = request.form.get("google_url", "").strip() or "https://g.page/r/review"

    if not customer_name or not phone:
        return jsonify({"error": "Navn og telefonnummer er påkrævet"}), 400

    message_body = f"Hej {customer_name}, tusind tak for opgaven! Vi vil blive super glade hvis du vil give os en anmeldelse på Google 🙏 {google_url}"

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        client.messages.create(body=message_body, from_=from_number, to=phone)

        log = SmsLog(
            user_id=current_user.id,
            customer_name=customer_name,
            phone=phone,
            message=message_body,
            status="sent",
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({"success": True, "message": f"SMS sendt til {phone}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/tilbud")
@login_required
def quote_page():
    if current_user.plan not in ("starter", "pro"):
        flash("Tilbudsgenerator kræver Starter eller Pro", "error")
        return redirect(url_for("dashboard"))
    return render_template("quote.html")


@app.route("/tilbud/generer", methods=["POST"])
@login_required
def generate_quote():
    if current_user.plan not in ("starter", "pro"):
        return jsonify({"error": "Tilbudsgenerator kræver Starter eller Pro"}), 403

    client_name = request.form.get("client_name", "").strip()
    client_email = request.form.get("client_email", "").strip()
    client_address = request.form.get("client_address", "").strip()
    description = request.form.get("description", "").strip()
    price = request.form.get("price", "").strip()
    validity_days = request.form.get("validity_days", "14").strip()
    tone = request.form.get("tone", "professionel").strip()

    if not client_name or not description:
        return jsonify({"error": "Kundenavn og opgavebeskrivelse er påkrævet"}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY ikke sat"}), 500

    tone_map = {
        "professionel": "professionel og præcis",
        "venlig": "venlig og personlig",
        "kortfattet": "kortfattet og direkte",
    }
    tone_label = tone_map.get(tone, "professionel og præcis")
    company = current_user.company or current_user.name or "vores firma"

    prompt = f"""Du er en erfaren dansk håndværksmester der skriver professionelle tilbud til kunder.

Skriv brødteksten til et tilbud med følgende detaljer:
- Kunde: {client_name}
- Virksomhed der sender tilbud: {company}
- Opgave: {description}
{f'- Adresse: {client_address}' if client_address else ''}
{f'- Pris: {price} kr ekskl. moms' if price else ''}
- Gyldighed: {validity_days} dage
- Tone: {tone_label}

Skriv KUN brødteksten (ikke overskrift, ikke pris-tabel, ikke signatur).
Strukturér med: 1) Kort tak for henvendelsen 2) Hvad tilbuddet dækker 3) Hvad der er inkluderet 4) Eventuelle forbehold 5) Opfordring til at acceptere.
Max 200 ord. Naturligt dansk."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        body = resp.content[0].text.strip()
        return jsonify({"body": body})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/review-request", methods=["POST"])
@login_required
def review_request():
    if current_user.plan != "pro":
        return jsonify({"error": "Anmeldelsesanmodninger kræver Pro-plan."}), 403

    customer_name = request.form.get("customer_name", "").strip()
    send_method = request.form.get("send_method", "sms")
    review_platform = request.form.get("review_platform", "google")
    review_url = request.form.get("review_url", "").strip()
    phone = request.form.get("phone", "").strip()
    email_to = request.form.get("email", "").strip()

    if not customer_name:
        return jsonify({"error": "Kundens navn er påkrævet"}), 400

    platform_label = "Google" if review_platform == "google" else "Trustpilot"
    fallback_url = review_url or ("https://g.page/r/review" if review_platform == "google" else "https://dk.trustpilot.com")
    company = current_user.company or "os"

    message_body = (
        f"Hej {customer_name}, tusind tak for opgaven! "
        f"Vi ville blive super glade hvis du vil give {company} en anmeldelse på {platform_label} 🙏 "
        f"{fallback_url}"
    )

    if send_method == "sms":
        if not phone:
            return jsonify({"error": "Telefonnummer er påkrævet"}), 400

        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        from_number = os.environ.get("TWILIO_FROM_NUMBER")

        if not account_sid or not auth_token or not from_number:
            return jsonify({"error": "Twilio er ikke sat op — tilføj TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN og TWILIO_FROM_NUMBER i Railway"}), 500

        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            client.messages.create(body=message_body, from_=from_number, to=phone)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        log = SmsLog(user_id=current_user.id, customer_name=customer_name, phone=phone, message=message_body, status="sent")
        db.session.add(log)
        db.session.commit()
        return jsonify({"success": True, "message": f"SMS sendt til {phone}"})

    elif send_method == "email":
        if not email_to:
            return jsonify({"error": "Email er påkrævet"}), 400

        smtp_host = os.environ.get("SMTP_HOST")
        smtp_port = int(os.environ.get("SMTP_PORT", 587))
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASS")
        from_email = os.environ.get("SMTP_FROM", smtp_user or "hej@postmester.dk")

        if not smtp_host or not smtp_user or not smtp_pass:
            return jsonify({"error": "Email er ikke sat op — tilføj SMTP_HOST, SMTP_USER og SMTP_PASS i Railway"}), 500

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Tak for opgaven, {customer_name} — vil du give os en anmeldelse?"
            msg["From"] = from_email
            msg["To"] = email_to

            html = f"""
            <div style="font-family:sans-serif;max-width:500px;margin:0 auto;padding:24px">
              <p style="font-size:1rem;line-height:1.6">Hej {customer_name},</p>
              <p style="font-size:1rem;line-height:1.6">
                Tusind tak for opgaven! Vi håber du er glad for resultatet.<br><br>
                Vi ville blive <strong>super glade</strong> hvis du vil tage 2 minutter
                og give os en anmeldelse på {platform_label} 🙏
              </p>
              <a href="{fallback_url}" style="display:inline-block;margin:20px 0;padding:14px 28px;background:#FF6B2B;color:white;border-radius:8px;text-decoration:none;font-weight:700;font-size:1rem">
                Giv os en anmeldelse →
              </a>
              <p style="font-size:0.85rem;color:#888">Mange tak — det betyder meget for os!</p>
            </div>"""

            msg.attach(MIMEText(message_body, "plain"))
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, email_to, msg.as_string())
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        log = SmsLog(user_id=current_user.id, customer_name=customer_name, phone=email_to, message=message_body, status="email_sent")
        db.session.add(log)
        db.session.commit()
        return jsonify({"success": True, "message": f"Email sendt til {email_to}"})

    return jsonify({"error": "Ukendt send-metode"}), 400


@app.route("/schedule", methods=["POST"])
@login_required
def schedule_post():
    if current_user.plan not in ("starter", "pro"):
        return jsonify({"error": "Planlægning kræver Starter eller Pro-plan."}), 403

    post_id = request.form.get("post_id")
    scheduled_at_str = request.form.get("scheduled_at", "").strip()

    if not post_id or not scheduled_at_str:
        return jsonify({"error": "post_id og scheduled_at er påkrævet"}), 400

    post = Post.query.filter_by(id=post_id, user_id=current_user.id).first_or_404()

    try:
        scheduled_at = datetime.fromisoformat(scheduled_at_str)
    except ValueError:
        return jsonify({"error": "Ugyldigt datoformat"}), 400

    post.scheduled_at = scheduled_at
    post.is_published = False
    db.session.commit()

    return jsonify({"success": True})


@app.route("/schedule/<int:post_id>/cancel", methods=["POST"])
@login_required
def cancel_schedule(post_id):
    post = Post.query.filter_by(id=post_id, user_id=current_user.id).first_or_404()
    post.scheduled_at = None
    post.is_published = True
    db.session.commit()
    return jsonify({"success": True})


@app.route("/reply", methods=["POST"])
@login_required
def reply():
    if current_user.plan != "pro":
        return jsonify({"error": "AI kommentar-svar kræver Pro-plan."}), 403

    comment = request.form.get("comment", "").strip()
    context = request.form.get("context", "").strip()
    if not comment:
        return jsonify({"error": "Indsæt en kommentar"}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY ikke sat"}), 500

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""Du er en venlig håndværksmester der svarer på en kommentar på Facebook/Instagram.
{f'Kontekst om virksomheden: {context}' if context else ''}

Kommentar fra følger: "{comment}"

Skriv 3 korte, professionelle og venlige svar på dansk. Hvert svar må max være 2-3 sætninger.
Format: Svar 1: ...\nSvar 2: ...\nSvar 3: ..."""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text.strip()
    replies = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("Svar"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                replies.append(parts[1].strip())
    if not replies:
        replies = [text]
    return jsonify({"replies": replies})


@app.route("/report")
@login_required
def report():
    if current_user.plan == "gratis":
        flash("Månedlig rapport kræver Starter eller Pro", "error")
        return redirect(url_for("dashboard"))

    now = datetime.utcnow()
    posts_month = Post.query.filter(
        Post.user_id == current_user.id,
        db.extract("month", Post.created_at) == now.month,
        db.extract("year", Post.created_at) == now.year,
    ).all()

    total = Post.query.filter_by(user_id=current_user.id).count()

    platform_counts = {}
    tone_counts = {}
    for p in posts_month:
        platform_counts[p.platform] = platform_counts.get(p.platform, 0) + 1
        tone_counts[p.tone] = tone_counts.get(p.tone, 0) + 1

    top_platform = max(platform_counts, key=platform_counts.get) if platform_counts else "—"
    top_tone = max(tone_counts, key=tone_counts.get) if tone_counts else "—"

    platform_labels = {"facebook": "Facebook", "instagram": "Instagram", "both": "Begge"}
    tone_labels = {"professionel": "Professionel", "venlig": "Venlig", "salgsorienteret": "Salgsorienteret"}

    stats = {
        "posts_this_month": len(posts_month),
        "total_posts": total,
        "top_platform": platform_labels.get(top_platform, top_platform),
        "top_tone": tone_labels.get(top_tone, top_tone),
        "platform_counts": {platform_labels.get(k, k): v for k, v in platform_counts.items()},
        "tone_counts": {tone_labels.get(k, k): v for k, v in tone_counts.items()},
        "month_name": ["januar","februar","marts","april","maj","juni","juli","august","september","oktober","november","december"][now.month - 1],
    }
    return render_template("report.html", stats=stats)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        company = request.form.get("company", "").strip()
        google_review_url = request.form.get("google_review_url", "").strip()
        trustpilot_url = request.form.get("trustpilot_url", "").strip()
        default_platform = request.form.get("default_platform", "facebook")
        default_tone = request.form.get("default_tone", "professionel")

        new_password = request.form.get("new_password", "").strip()
        current_password = request.form.get("current_password", "").strip()

        if new_password:
            if not current_password or not bcrypt.checkpw(current_password.encode(), current_user.password_hash.encode()):
                flash("Nuværende adgangskode er forkert", "error")
                return redirect(url_for("settings"))
            if len(new_password) < 6:
                flash("Ny adgangskode skal være mindst 6 tegn", "error")
                return redirect(url_for("settings"))
            current_user.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

        current_user.name = name
        current_user.company = company
        current_user.google_review_url = google_review_url
        current_user.trustpilot_url = trustpilot_url
        current_user.default_platform = default_platform if default_platform in PLATFORMS else "facebook"
        current_user.default_tone = default_tone if default_tone in TONES else "professionel"
        db.session.commit()
        flash("Dine indstillinger er gemt ✅", "success")
        return redirect(url_for("settings"))

    return render_template("settings.html")


@app.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.filter_by(id=post_id, user_id=current_user.id).first_or_404()
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for("dashboard"))


# ── Admin ──────────────────────────────────────────────

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@postmester.dk")

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.email != ADMIN_EMAIL:
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


@app.route("/admin")
@login_required
@admin_required
def admin():
    users = User.query.order_by(User.created_at.desc()).all()
    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(20).all()

    paid = [u for u in users if u.plan != "gratis"]
    mrr = sum(79 if u.plan == "starter" else 149 for u in paid)

    today = datetime.utcnow().date()
    users_today = sum(1 for u in users if u.created_at.date() == today)

    stats = {
        "total_users": len(users),
        "users_today": users_today,
        "total_posts": Post.query.count(),
        "paid_users": len(paid),
        "mrr": mrr,
    }
    return render_template("admin.html", users=users, recent_posts=recent_posts, stats=stats)


# ── Stripe payment ────────────────────────────────────

STRIPE_PLANS = {
    "starter": os.environ.get("STRIPE_PRICE_STARTER", ""),
    "pro":     os.environ.get("STRIPE_PRICE_PRO", ""),
}

@app.route("/upgrade/<plan>")
@login_required
def upgrade(plan):
    if plan not in STRIPE_PLANS or not stripe.api_key:
        flash("Betaling er ikke sat op endnu — kontakt os på hej@postmester.dk", "error")
        return redirect(url_for("dashboard"))

    price_id = STRIPE_PLANS[plan]
    if not price_id:
        flash("Betaling er ikke sat op endnu — kontakt os på hej@postmester.dk", "error")
        return redirect(url_for("dashboard"))

    try:
        checkout = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=current_user.email,
            metadata={"user_id": current_user.id, "plan": plan},
            success_url=url_for("upgrade_success", plan=plan, _external=True),
            cancel_url=url_for("dashboard", _external=True),
            locale="da",
        )
        return redirect(checkout.url)
    except Exception as e:
        flash(f"Betalingsfejl: {str(e)}", "error")
        return redirect(url_for("dashboard"))


@app.route("/upgrade/success/<plan>")
@login_required
def upgrade_success(plan):
    if plan in ("starter", "pro"):
        current_user.plan = plan
        db.session.commit()
    flash(f"Tillykke! Du er nu opgraderet til {plan.capitalize()} 🎉", "success")
    return redirect(url_for("dashboard"))


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, webhook_secret)
    except Exception:
        return "", 400

    if event["type"] == "checkout.session.completed":
        session_obj = event["data"]["object"]
        user_id = int(session_obj["metadata"].get("user_id", 0))
        plan = session_obj["metadata"].get("plan", "")
        user = db.session.get(User, user_id)
        if user and plan in ("starter", "pro"):
            user.plan = plan
            db.session.commit()

    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.paused"):
        session_obj = event["data"]["object"]
        email = session_obj.get("customer_email", "")
        user = User.query.filter_by(email=email).first()
        if user:
            user.plan = "gratis"
            db.session.commit()

    return "", 200


@app.route("/admin/set-plan", methods=["POST"])
@login_required
@admin_required
def admin_set_plan():
    user = db.session.get(User, int(request.form["user_id"]))
    if user:
        user.plan = request.form["plan"]
        db.session.commit()
    return redirect(url_for("admin"))


@app.route("/setup/<token>")
def setup_admin(token):
    expected = os.environ.get("SETUP_TOKEN", "")
    if not expected or token != expected:
        return "Ikke tilladt", 403

    EMAIL = "antont16@gmail.com"
    PASSWORD = "PostMester2025!"
    NAME = "Anton"

    existing = User.query.filter_by(email=EMAIL).first()
    pw_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    if existing:
        existing.plan = "pro"
        existing.password_hash = pw_hash
        db.session.commit()
        return f"✅ Opdateret: {EMAIL} → plan=pro"
    else:
        user = User(email=EMAIL, password_hash=pw_hash, name=NAME, plan="pro")
        db.session.add(user)
        db.session.commit()
        return f"✅ Oprettet: {EMAIL} → plan=pro<br>Log ind med: {EMAIL} / {PASSWORD}"




def _make_referral_code():
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(chars, k=8))
        if not User.query.filter_by(referral_code=code).first():
            return code


# ── Referral ──────────────────────────────────────────

@app.route("/ref/<code>")
def referral_landing(code):
    resp = redirect(url_for("register"))
    resp.set_cookie("ref", code, max_age=30*24*3600, httponly=True, samesite="Lax")
    return resp


@app.route("/invite")
@login_required
def invite():
    if not current_user.referral_code:
        current_user.referral_code = _make_referral_code()
        db.session.commit()
    return render_template("invite.html")


# ── Blog / SEO ────────────────────────────────────────

BLOG_POSTS = [
    {
        "slug": "facebook-opslag-haandvaerker",
        "title": "Sådan skriver du gode Facebook-opslag som håndværker (uden at bruge tid på det)",
        "meta": "Lær hvad der virker på Facebook for tømrere, malere og elektrikere. Konkrete eksempler og gratis skabeloner.",
        "date": "2025-05-15",
        "category": "Social media tips",
        "read_time": "4 min",
        "intro": "De fleste håndværkere ved godt, at de burde være mere aktive på Facebook. Men hvem har tid til det, når der er job der venter?",
        "content": """<p>Du har podset en frisk malet stue. Du er på vej ud ad døren. Det ser flot ud — men 30 sekunder efter lukker du bilen og kører videre til næste opgave.</p>

<p>Det billede du ikke tog? Det opslag du ikke lavede? Det var 3-5 potentielle kunder der aldrig fandt ud af at du eksisterer.</p>

<h2>Hvad virker på Facebook som håndværker?</h2>

<p><strong>Før/efter billeder</strong> — Det er den bedste content-type for håndværkere. Folk elsker at se transformationen. Tag et billede inden du starter og et når du er færdig. Det tager 10 sekunder.</p>

<p><strong>Lokale referencer</strong> — "Vi har netop renoveret et badeværelse i Aarhus N" performer bedre end generiske tekster. Folk søger håndværkere i deres nærområde.</p>

<p><strong>Kort og konkret</strong> — 3-4 afsnit er nok. De fleste scroller på mobilen — lange tekster bliver ikke læst.</p>

<p><strong>Slut med et spørgsmål eller CTA</strong> — "Har du brug for en tømrer i Odense? Ring på XX XX XX XX" — simpelt og effektivt.</p>

<h2>Eksempel: et godt opslag vs. et dårligt</h2>

<p><strong>Dårligt:</strong> "Vi tilbyder kvalitetsmaling til fornuftige priser. Ring for tilbud."</p>

<p><strong>Godt:</strong> "✅ Nymalet stue i Horsens — kunden ville have en varm farve der stadig lyste rummet op. Vi valgte Jotun 'Warm Sand' og resultatet taler for sig selv 🎨 Hvad er dit næste maleprojekt? Skriv til os og få et uforpligtende tilbud."</p>

<h2>Brug AI til at skrive opslaget</h2>

<p>Du behøver ikke bruge 20 minutter på at finde på de rigtige ord. Med PostMester skriver du 2-3 ord om jobbet, og AI genererer et komplet opslag klar til Facebook — på under 10 sekunder.</p>

<p>Prøv det gratis — ingen kreditkort kræves.</p>""",
        "cta_text": "Prøv PostMester gratis",
        "cta_url": "/register",
    },
    {
        "slug": "anmeldelser-haandvaerker-google",
        "title": "Sådan får du flere Google-anmeldelser som håndværker",
        "meta": "5-stjernede Google-anmeldelser er guld for håndværkere. Lær den nemmeste måde at bede om anmeldelser på — og hvad du skriver.",
        "date": "2025-05-22",
        "category": "Anmeldelser",
        "read_time": "3 min",
        "intro": "En håndværker med 50 Google-anmeldelser vinder over en med 5 — selvom kvaliteten er den samme. Sådan samler du dem effektivt.",
        "content": """<p>Tænk på hvad du selv gør, når du skal finde en VVS'er, elektriker eller tømrer. Du googler. Du kigger på anmeldelserne. Dem med mange stjerner og kommentarer — dem ringer du til.</p>

<p>Det gør dine potentielle kunder præcis det samme.</p>

<h2>Problemet: kunderne glemmer det</h2>

<p>Du leverer et flot stykke arbejde. Kunden er tilfreds. Du siger "endelig du gerne skrive en anmeldelse". De nikker. Og glemmer det helt.</p>

<p>Løsningen er at gøre det utrolig nemt — og spørge på det rigtige tidspunkt.</p>

<h2>Det rigtige tidspunkt er inden du kører</h2>

<p>Mens kunden stadig har dig foran sig og er begejstret — der er det nemmest at få en "ja selvfølgelig". Send dem et link direkte på SMS eller email, mens du pakker dine ting.</p>

<p>Besked der virker:<br>
<em>"Hej [navn], tusind tak for opgaven! Vil du give os en anmeldelse på Google? Det tager kun 2 minutter og hjælper os enormt 🙏 [link]"</em></p>

<h2>Gør linket kortere</h2>

<p>Det lange Google-link afskrækker folk. Gå til din Google My Business profil → Del → Kopiér anmeldelseslink. Det er kortere og går direkte til anmeldelsesformularen.</p>

<h2>Automatisér det med PostMester</h2>

<p>Med PostMester Pro sender du anmeldelsesanmodninger på SMS og email med ét klik — direkte fra dashboardet. Du behøver kun spare 2-3 ekstra anmeldelser om måneden for at det er pengene værd.</p>""",
        "cta_text": "Prøv PostMester gratis",
        "cta_url": "/register",
    },
    {
        "slug": "instagram-haandvaerker-guide",
        "title": "Instagram for håndværkere: Hvad der virker i 2025",
        "meta": "Instagram kan give håndværkere nye kunder — men kun hvis du bruger det rigtigt. Her er den korte guide til hvad der faktisk virker.",
        "date": "2025-06-01",
        "category": "Social media tips",
        "read_time": "5 min",
        "intro": "Instagram er billedernes platform — og det er perfekt for håndværkere. Problemet er bare at de fleste poster forkert.",
        "content": """<p>Instagram er faktisk bedre egnet til håndværkere end Facebook — fordi det er en visuel platform. Dit arbejde taler for sig selv. Du behøver ikke bruge mange ord.</p>

<h2>Det der virker på Instagram</h2>

<p><strong>Reel af arbejdsprocessen</strong> — 15-30 sekunder hvor du viser hvad du laver. Time-lapse af et murerarbejde, en montage af badeværelsesrenovering. Disse får organisk rækkevidde.</p>

<p><strong>Før/efter i carousel</strong> — Swipe-opslag med 2-5 billeder. Læg "SWIPE →" på første billede. Algoritmen belønner opslag folk interagerer med.</p>

<p><strong>Lokale hashtags</strong> — #tømreraarhus #malerkøbenhavn #vvsodense. Folk søger lokalt på Instagram.</p>

<h2>Hvad du IKKE skal gøre</h2>

<ul>
<li>Poste det samme som på Facebook — Instagram er kortere og mere visuelt</li>
<li>For mange tekster i billedet — Instagram er et visuelt medie</li>
<li>Købe følgere — det skader din rækkevidde</li>
</ul>

<h2>Hvor tit skal du poste?</h2>

<p>3 gange om ugen er ideelt. Men 1 gang om ugen er bedre end aldrig. Konsistens slår kvalitet på lang sigt.</p>

<p>Brug PostMester til at generere både Facebook- og Instagram-opslag på én gang — du skriver beskrivelsen én gang og får tekst tilpasset begge platforme.</p>""",
        "cta_text": "Prøv PostMester gratis",
        "cta_url": "/register",
    },
    {
        "slug": "tilbud-haandvaerker-skabelon",
        "title": "Sådan skriver du et professionelt tilbud som håndværker (med skabelon)",
        "meta": "Et godt tilbud vinder opgaven. Her er hvad der skal med, hvad du skal undgå, og en gratis AI-tilbudsgenerator til håndværkere.",
        "date": "2025-06-08",
        "category": "Forretning",
        "read_time": "4 min",
        "intro": "Et sloppy tilbud på en SMS taber mod et professionelt PDF-tilbud — selvom din pris er bedre. Her er hvad der gør forskellen.",
        "content": """<p>Kunder sammenligner tilbud. Det første de kigger på er prisen. Men det der afgør hvem de vælger — det er professionalisme og tillid.</p>

<p>Et tilbud der ser professionelt ud, signalerer at du også laver professionelt arbejde.</p>

<h2>Hvad skal et godt håndværkertilbud indeholde?</h2>

<ul>
<li><strong>Dit navn / virksomhed</strong> og kontaktoplysninger</li>
<li><strong>Kundens navn og adresse</strong></li>
<li><strong>Dato og tilbudsnummer</strong> — giver det et officielt præg</li>
<li><strong>Præcis beskrivelse af arbejdet</strong> — hvad er inkluderet og hvad er IKKE inkluderet</li>
<li><strong>Pris ekskl. moms</strong>, momsbeløb og totalpris inkl. moms</li>
<li><strong>Gyldighed</strong> — 14 eller 30 dage</li>
<li><strong>Signatur</strong></li>
</ul>

<h2>Hvad du skal undgå</h2>

<p><strong>Vag beskrivelse</strong> — "Renovering af badeværelse" er ikke nok. Skriv "Ny bruseniche 120x80cm med fliser, nyt toilet, ny håndvask, alt VVS inkluderet. Eksisterende fliser fjernes og bortskaffes."</p>

<p><strong>Manglende forbehold</strong> — Tilføj altid "Eventuelle skjulte fejl og skader der opdages undervejs faktureres separat efter aftale."</p>

<h2>Spar 30 minutter per tilbud</h2>

<p>Med PostMester Starter og Pro kan du generere et komplet, professionelt tilbud på under 1 minut. Beskriv opgaven, angiv prisen — AI skriver det hele og du printer det som PDF.</p>""",
        "cta_text": "Prøv tilbudsgeneratoren gratis",
        "cta_url": "/register",
    },
]

TRADE_PAGES = {
    "toemrer": {
        "title": "PostMester til tømrere",
        "emoji": "🪚",
        "trade": "tømrer",
        "trade_plural": "tømrere",
        "examples": [
            "Ny terrassedæk på 30 kvm i Silkeborg — her er resultatet 💪",
            "Udskiftet alle vinduer i et parcelhus fra 70'erne. Kunden sparer nu 30% på varmen 🏠",
            "Carport færdig! 6x6m med integreret redskabsrum — kunden elsker det ✅",
        ],
    },
    "elektriker": {
        "title": "PostMester til elektrikere",
        "emoji": "⚡",
        "trade": "elektriker",
        "trade_plural": "elektrikere",
        "examples": [
            "EV-lader monteret på villa i Aarhus N ⚡ Fremtidssikret og klar til elbilen",
            "Komplet eltavle udskiftet — gammelt sikringsanlæg moderniseret ✅",
            "Smart home installation: lys, varme og sikkerhed styret fra mobilen 📱",
        ],
    },
    "maler": {
        "title": "PostMester til malere",
        "emoji": "🎨",
        "trade": "maler",
        "trade_plural": "malere",
        "examples": [
            "Nymalet stue i Horsens — fra slidt gul til varm grå 🎨 Kunden er vild med det",
            "Facademaling på rækkehus færdig — huset ser 20 år yngre ud ✨",
            "Komplet maling af lejlighed inden salg — kunden fik 80.000 mere end forventet 💰",
        ],
    },
    "vvs": {
        "title": "PostMester til VVS-firmaer",
        "emoji": "🔧",
        "trade": "VVS-firma",
        "trade_plural": "VVS-firmaer",
        "examples": [
            "Nyt badeværelse på 7 kvm — fra gulv til loft inkl. al VVS 🚿",
            "Udskiftet 40 år gammelt fjernvarmesystem — kunden sparer nu 4.000 kr/år 💧",
            "Rørskade udbedret samme dag — vi er klar til akutte opgaver ⚡",
        ],
    },
}


@app.route("/blog")
def blog_index():
    return render_template("blog_index.html", posts=BLOG_POSTS)


@app.route("/blog/<slug>")
def blog_post(slug):
    post = next((p for p in BLOG_POSTS if p["slug"] == slug), None)
    if not post:
        return redirect(url_for("blog_index"))
    return render_template("blog_post.html", post=post)


@app.route("/haandvaerker/<trade>")
def trade_page(trade):
    page = TRADE_PAGES.get(trade)
    if not page:
        return redirect(url_for("index"))
    return render_template("trade_page.html", page=page, trade=trade)


# In-memory rate limiting for demo
_demo_requests = {}

@app.route("/demo", methods=["POST"])
def demo():
    ip = request.remote_addr
    today = datetime.utcnow().date().isoformat()
    key = f"{ip}:{today}"

    # Clean old entries
    if len(_demo_requests) > 1000:
        _demo_requests.clear()

    count = _demo_requests.get(key, 0)
    if count >= 10:
        return jsonify({"error": "Du har prøvet demo for mange gange i dag. Opret en gratis konto for at fortsætte."}), 429
    _demo_requests[key] = count + 1

    description = request.form.get("description", "").strip()
    if not description or len(description) < 5:
        return jsonify({"error": "Beskriv venligst jobbet kort"}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "API ikke tilgængelig"}), 500

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system="Du er en ekspert i dansk social media markedsføring for håndværksvirksomheder. Skriv et kort, engagerende Facebook-opslag på naturligt dansk. Max 3 afsnit, 2-3 emojis, slut med call-to-action. Skriv KUN selve opslaget.",
            messages=[{"role": "user", "content": f"Skriv et Facebook-opslag til en dansk håndværksvirksomhed om: {description}"}]
        )
        return jsonify({"post": resp.content[0].text.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/sitemap.xml")
def sitemap():
    pages = [
        ("https://postmester.app/", "weekly", "1.0"),
        ("https://postmester.app/register", "monthly", "0.8"),
        ("https://postmester.app/blog", "weekly", "0.8"),
        ("https://postmester.app/blog/facebook-opslag-haandvaerker", "monthly", "0.7"),
        ("https://postmester.app/blog/anmeldelser-haandvaerker-google", "monthly", "0.7"),
        ("https://postmester.app/blog/instagram-haandvaerker-guide", "monthly", "0.7"),
        ("https://postmester.app/blog/tilbud-haandvaerker-skabelon", "monthly", "0.7"),
        ("https://postmester.app/haandvaerker/toemrer", "monthly", "0.6"),
        ("https://postmester.app/haandvaerker/elektriker", "monthly", "0.6"),
        ("https://postmester.app/haandvaerker/maler", "monthly", "0.6"),
        ("https://postmester.app/haandvaerker/vvs", "monthly", "0.6"),
    ]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for loc, freq, pri in pages:
        xml += f"  <url><loc>{loc}</loc><changefreq>{freq}</changefreq><priority>{pri}</priority></url>\n"
    xml += "</urlset>"
    from flask import Response
    return Response(xml, mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    txt = "User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /dashboard\nSitemap: https://postmester.app/sitemap.xml\n"
    from flask import Response
    return Response(txt, mimetype="text/plain")


@app.route("/google25ca0d020d56cb0f.html")
def google_verify():
    from flask import Response
    return Response("google-site-verification: google25ca0d020d56cb0f.html", mimetype="text/html")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
