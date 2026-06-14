"""
app.py — Makroinvestor Web App
Kør med: python app.py  (åbn http://localhost:5000)
"""

from flask import Flask, render_template, jsonify, request
from data import hent_alle_data, match_profil, parse_fordeling
import json

app = Flask(__name__)

# Cache data ved opstart (undgå at læse Excel ved hvert kald)
_cache = {}

def get_data():
    if not _cache:
        _cache.update(hent_alle_data())
    return _cache


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/dashboard")
def api_dashboard():
    d = get_data()
    return jsonify({
        "makro_fase":   d["makro_fase"],
        "sektorer":     d["sektorer"],
        "afstemning":   d["afstemning"],
        "opdateret":    d["opdateret"],
        "data_kvartal": d["data_kvartal"],
        "historik":     d["historik"],
        "fremtid":      d["fremtid"],
    })


@app.route("/api/spoergeskema")
def api_spoergeskema():
    d = get_data()
    return jsonify(d["spoergeskema"])


@app.route("/api/profil", methods=["POST"])
def api_profil():
    """
    POST { "svar": [score1, score2, ...] }
    Returnerer risikoprofil + porteføljeanbefaling.
    """
    d = get_data()
    body = request.get_json()
    svar = body.get("svar", [])

    total = sum(svar)
    maks  = sum(max(s["score"] for s in q["svar"]) for q in d["spoergeskema"])
    ratio = total / maks if maks else 0

    profil = match_profil(d["profiler"], ratio)
    fordeling = parse_fordeling(profil["fordeling"])

    beloeb = body.get("beloeb", 0)
    beloeb_fordeling = {k: round(v / 100 * beloeb) for k, v in fordeling.items()}

    # Top sektorer matchet til ETF + aktier
    top_sektorer = []
    for s in d["sektorer"][:5]:
        sektor = s["sektor"]
        etfs = d["etf_liste"].get(sektor, [])[:2]
        aktier_pr_region = {}
        for region, liste in d["aktier"].items():
            matches = sorted(
                [a for a in liste if a["sektor"] == sektor],
                key=lambda x: x["market_cap"], reverse=True
            )[:3]
            if matches:
                aktier_pr_region[region] = matches
        top_sektorer.append({**s, "etfs": etfs, "aktier": aktier_pr_region})

    return jsonify({
        "profil":            profil,
        "score_ratio":       round(ratio, 3),
        "total_score":       total,
        "maks_score":        maks,
        "fordeling":         fordeling,
        "beloeb_fordeling":  beloeb_fordeling,
        "top_sektorer":      top_sektorer,
    })


@app.route("/api/sektor/<navn>")
def api_sektor(navn):
    """Detaljeview for en sektor."""
    d = get_data()
    sektor = next((s for s in d["sektorer"] if s["sektor"].lower() == navn.lower()), None)
    if not sektor:
        return jsonify({"fejl": "Sektor ikke fundet"}), 404

    etfs = d["etf_liste"].get(sektor["sektor"], [])
    aktier = {}
    for region, liste in d["aktier"].items():
        matches = sorted(
            [a for a in liste if a["sektor"] == sektor["sektor"]],
            key=lambda x: x["market_cap"], reverse=True
        )
        if matches:
            aktier[region] = matches

    historisk_score = next(
        (a for a in d["afstemning"] if a["sektor"] == sektor["sektor"]), None
    )

    return jsonify({
        **sektor,
        "etfs": etfs,
        "aktier": aktier,
        "historisk": historisk_score,
    })


if __name__ == "__main__":
    print("\n  🚀 Makroinvestor Web starter...")
    print("  📊 Åbn http://localhost:5000 i din browser\n")
    get_data()  # Forvarm cache
    app.run(debug=False, host="0.0.0.0", port=5000)
