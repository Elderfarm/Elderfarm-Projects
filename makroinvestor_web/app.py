import os
from flask import Flask, render_template, jsonify, request
from data import (hent_alle_data, match_profil, parse_fordeling,
                  simuler_sektorer, sektor_ind_scores, INDIKATORER, SEKTOR_RÆKKEFØLGE,
                  DEFAULT_MAKRO, FASE_META, INDIKATOR_TYPE)

app = Flask(__name__)
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
        "makro_fase":    d["makro_fase"],
        "sektorer":      d["sektorer"],
        "afstemning":    d["afstemning"],
        "historik":      d["historik"],
        "fremtid":       d["fremtid"],
        "opdateret":     d["opdateret"],
        "data_kvartal":  d["data_kvartal"],
        "pillars":       d.get("pillars", {}),
    })


@app.route("/api/heatmap")
def api_heatmap():
    d = get_data()
    return jsonify({
        "heatmap":        d["heatmap"],
        "alle_kvartaler": d["alle_kvartaler"],
        "sektorer":       SEKTOR_RÆKKEFØLGE,
        "makro_analyse":  d["makro_analyse"],
        "indikatorer":    d["indikatorer"],
        "indikator_vaegter": d["indikator_vaegter"],
    })


@app.route("/api/template")
def api_template():
    d = get_data()
    return jsonify({
        "default_makro":    d["default_makro"],
        "seneste_makro":    d["seneste_makro"],
        "seneste_kvartal":  d["seneste_kvartal"],
        "indikatorer":      d["indikatorer"],
        "indikator_vaegter":d["indikator_vaegter"],
        "indikator_type":   INDIKATOR_TYPE,
        "fase_meta":        FASE_META,
        "pillars":          d.get("pillars", {}),
    })


@app.route("/api/simuler", methods=["POST"])
def api_simuler():
    """POST {makro: {region: {indikator: vaerdi}}} → sektorscorer + fase."""
    body = request.get_json()
    makro = body.get("makro", DEFAULT_MAKRO)
    # Udtræk kun numeriske værdier
    inputs = {}
    for region, inds in makro.items():
        inputs[region] = {}
        for ind, val in inds.items():
            if isinstance(val, dict): v = val.get("vaerdi")
            else: v = val
            try: inputs[region][ind] = float(v)
            except: pass
    body_prev = body.get("prev_makro")
    prev_inputs = None
    if body_prev:
        prev_inputs = {}
        for region, inds in body_prev.items():
            prev_inputs[region] = {}
            for ind, val in inds.items():
                try: prev_inputs[region][ind] = float(val)
                except: pass
    return jsonify(simuler_sektorer(inputs, prev_inputs))


@app.route("/api/spoergeskema")
def api_spoergeskema():
    return jsonify(get_data()["spoergeskema"])


@app.route("/api/profil", methods=["POST"])
def api_profil():
    d = get_data()
    body = request.get_json()
    svar = body.get("svar", [])
    total = sum(svar)
    maks = sum(max(s["score"] for s in q["svar"]) for q in d["spoergeskema"])
    ratio = total / maks if maks else 0
    profil = match_profil(d["profiler"], ratio)
    fordeling = parse_fordeling(profil["fordeling"])
    beloeb = body.get("beloeb", 0)
    beloeb_fordeling = {k: round(v/100*beloeb) for k,v in fordeling.items()}

    top_sektorer = []
    for s in d["sektorer"][:5]:
        sektor = s["sektor"]
        etfs = d["etf_liste"].get(sektor, [])[:2]
        aktier = {}
        for region, liste in d["aktier"].items():
            m = sorted([a for a in liste if a["sektor"]==sektor],
                       key=lambda x: x["market_cap"], reverse=True)[:3]
            if m: aktier[region] = m
        top_sektorer.append({**s, "etfs":etfs, "aktier":aktier})

    return jsonify({"profil":profil,"score_ratio":round(ratio,3),"total_score":total,
                    "maks_score":maks,"fordeling":fordeling,"beloeb_fordeling":beloeb_fordeling,
                    "top_sektorer":top_sektorer})


@app.route("/api/sektor_inds/<navn>")
def api_sektor_inds(navn):
    d = get_data()
    s = next((x for x in d["sektorer"] if x["sektor"].lower()==navn.lower()), None)
    if not s: return jsonify({"fejl":"ikke fundet"}), 404
    return jsonify(sektor_ind_scores(d["seneste_makro"], s["sektor"]))


@app.route("/api/sektor/<navn>")
def api_sektor(navn):
    d = get_data()
    s = next((x for x in d["sektorer"] if x["sektor"].lower()==navn.lower()), None)
    if not s: return jsonify({"fejl":"ikke fundet"}), 404
    etfs = d["etf_liste"].get(s["sektor"],[])
    aktier = {r: sorted([a for a in l if a["sektor"]==s["sektor"]],
                         key=lambda x:x["market_cap"],reverse=True)
              for r,l in d["aktier"].items()}
    aktier = {r:v for r,v in aktier.items() if v}
    hist = next((a for a in d["afstemning"] if a["sektor"]==s["sektor"]),None)
    ma = {region: d["makro_analyse"].get(region,{}).get(s["sektor"],{})
          for region in ["Europa","USA"]}
    return jsonify({**s,"etfs":etfs,"aktier":aktier,"historisk":hist,"makro_analyse":ma})


@app.route("/api/live_status")
def api_live_status():
    """Status på live datahentning + hvilke felter der er live vs. estimat."""
    d = get_data()
    status = {"fred_key": bool(os.environ.get("FRED_API_KEY")), "regioner": {}}
    for region, inds in d["seneste_makro"].items():
        status["regioner"][region] = {
            ind: v.get("kilde","?") for ind, v in inds.items()
        }
    return jsonify(status)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Ryd cache og hent friske data (live + Excel)."""
    _cache.clear()
    d = get_data()
    live_count = sum(
        1 for rg in d["seneste_makro"].values()
        for v in rg.values() if isinstance(v, dict) and v.get("kilde") == "live"
    )
    return jsonify({"status": "ok", "live_felter": live_count, "opdateret": d["opdateret"]})


if __name__ == "__main__":
    print("\n  🚀 Makroinvestor Web")
    print("  📊 http://localhost:5000\n")
    get_data()
    app.run(debug=False, host="0.0.0.0", port=5000)
