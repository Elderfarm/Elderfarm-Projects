import os
import base64
import bcrypt
import anthropic
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from pathlib import Path
from models import db, User, Post

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "postmester-dev-secret-change-in-prod")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///postmester.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log ind for at generere opslag"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
PLATFORMS = {"facebook": "Facebook", "instagram": "Instagram", "both": "Facebook og Instagram"}
TONES = {"professionel": "professionel og tillidsfuld", "venlig": "venlig og uformel", "salgsorienteret": "salgsorienteret og overbevisende"}


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_post_ai(description, platform, tone, image_data, image_media_type):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY ikke sat"}

    client = anthropic.Anthropic(api_key=api_key)
    platform_label = PLATFORMS.get(platform, "Facebook")
    tone_label = TONES.get(tone, "professionel og tillidsfuld")

    system = f"""Du er en ekspert i dansk social media markedsføring for håndværksvirksomheder.
Du skriver {platform_label}-opslag der er korte, engagerende og lokale.
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
    return render_template("dashboard.html", posts=posts)


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
    if "photo" in request.files:
        file = request.files["photo"]
        if file and file.filename and allowed_file(file.filename):
            image_data = file.read()
            ext = file.filename.rsplit(".", 1)[1].lower()
            image_media_type = f"image/{'jpeg' if ext == 'jpg' else ext}"

    try:
        result = generate_post_ai(description, platform, tone, image_data, image_media_type)
        if "error" in result:
            return jsonify(result), 500

        post = Post(
            user_id=current_user.id,
            description=description,
            platform=platform,
            tone=tone,
            post_text=result["post"],
            hashtags=result.get("hashtags", ""),
        )
        db.session.add(post)
        db.session.commit()

        result["posts_remaining"] = current_user.posts_remaining()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.filter_by(id=post_id, user_id=current_user.id).first_or_404()
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
