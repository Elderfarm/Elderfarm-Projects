import os
import base64
import bcrypt
import stripe
import anthropic
import requests
import uuid
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
        user = User(email=email, password_hash=pw_hash, name=name, company=company)
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


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
