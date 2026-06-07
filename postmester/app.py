import os
import base64
import anthropic
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from pathlib import Path

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB
app.config["UPLOAD_FOLDER"] = "uploads"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

PLATFORMS = {
    "facebook": "Facebook",
    "instagram": "Instagram",
    "both": "Facebook og Instagram",
}

TONES = {
    "professionel": "professionel og tillidsfuld",
    "venlig": "venlig og uformel",
    "salgsorienteret": "salgsorienteret og overbevisende",
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_post(description: str, platform: str, tone: str, image_data: bytes | None, image_media_type: str | None) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY ikke sat"}

    client = anthropic.Anthropic(api_key=api_key)

    platform_label = PLATFORMS.get(platform, "Facebook")
    tone_label = TONES.get(tone, "professionel og tillidsfuld")

    system = f"""Du er en ekspert i dansk social media markedsføring for håndværksvirksomheder.
Du skriver {platform_label}-opslag der er korte, engagerende og lokale.

Regler:
- Skriv på naturligt, uformelt dansk
- Max 3-4 afsnit
- Inkludér relevante emojis (2-4 stk)
- Slut ALTID med en call-to-action (ring, skriv, book)
- Tonen skal være: {tone_label}
- Skriv KUN selve opslaget — ingen forklaringer eller meta-kommentarer"""

    user_parts = []

    if image_data:
        user_parts.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_media_type,
                "data": base64.standard_b64encode(image_data).decode("utf-8"),
            },
        })

    user_parts.append({
        "type": "text",
        "text": f"Skriv et {platform_label}-opslag til en dansk håndværksvirksomhed baseret på dette:\n\n{description}\n\n{'Brug billedet som inspiration til at beskrive arbejdet konkret.' if image_data else ''}",
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": user_parts}],
    )

    post_text = response.content[0].text.strip()

    hashtags = generate_hashtags(description, client)

    return {
        "post": post_text,
        "hashtags": hashtags,
        "platform": platform_label,
    }


def generate_hashtags(description: str, client: anthropic.Anthropic) -> str:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"Generer 5-8 relevante danske og engelske hashtags til et håndværker-opslag om: {description}. Kun hashtags, adskilt af mellemrum.",
        }],
    )
    return response.content[0].text.strip()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
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
        result = generate_post(description, platform, tone, image_data, image_media_type)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    Path("uploads").mkdir(exist_ok=True)
    app.run(debug=True, port=5000)
