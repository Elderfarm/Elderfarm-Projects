"""
Tools tilgængelige for AI Company Builder-agenten.
"""

import json
import smtplib
import os
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

try:
    from duckduckgo_search import DDGS
    HAS_SEARCH = True
except ImportError:
    HAS_SEARCH = False

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Tool-definitioner (sendes til Claude) ──────────────────────────────────

TOOLS = [
    {
        "name": "web_search",
        "description": "Søg på internettet efter markedsinformation, konkurrenter, trends, prissætning osv.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Søgeforespørgsel"},
                "max_results": {"type": "integer", "description": "Maks antal resultater (default 5)", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_idea",
        "description": "Gem den valgte virksomhedsidé og gå videre til VALIDATE-fasen.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string", "description": "Virksomhedens navn"},
                "idea": {"type": "string", "description": "Beskrivelse af idéen (2-4 sætninger)"},
                "target_market": {"type": "string", "description": "Primær målgruppe"},
                "value_proposition": {"type": "string", "description": "Hvad er den unikke værdi?"},
            },
            "required": ["company_name", "idea", "target_market", "value_proposition"],
        },
    },
    {
        "name": "advance_phase",
        "description": "Gå videre til næste fase. Brug kun når den nuværende fase er fuldt gennemført.",
        "input_schema": {
            "type": "object",
            "properties": {
                "next_phase": {
                    "type": "string",
                    "enum": ["VALIDATE", "BUILD", "OUTREACH", "ITERATE", "DONE"],
                    "description": "Næste fase",
                },
                "reason": {"type": "string", "description": "Kort begrundelse for at gå videre"},
            },
            "required": ["next_phase", "reason"],
        },
    },
    {
        "name": "build_landing_page",
        "description": "Generer en professionel HTML landing page for virksomheden.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "tagline": {"type": "string", "description": "Kort slogan (maks 10 ord)"},
                "description": {"type": "string", "description": "Produktbeskrivelse (2-3 afsnit)"},
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Liste af 3-5 nøglefunktioner",
                },
                "cta_text": {"type": "string", "description": "Call-to-action knap tekst"},
                "price": {"type": "string", "description": "Pris f.eks. '99 kr/md'"},
            },
            "required": ["company_name", "tagline", "description", "features", "cta_text"],
        },
    },
    {
        "name": "write_outreach_email",
        "description": "Skriv en personlig outreach-email til en potentiel kunde og gem den.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient_type": {"type": "string", "description": "Hvem skrives til? F.eks. 'freelance grafiker', 'lille e-commerce butik'"},
                "subject": {"type": "string", "description": "Email emne"},
                "body": {"type": "string", "description": "Email brødtekst (personlig, ikke generisk)"},
                "send_to": {"type": "string", "description": "Email-adresse at sende til (valgfrit — kræver SMTP-konfiguration)"},
            },
            "required": ["recipient_type", "subject", "body"],
        },
    },
    {
        "name": "add_note",
        "description": "Tilføj en strategisk note eller observation til virksomhedens log.",
        "input_schema": {
            "type": "object",
            "properties": {
                "note": {"type": "string", "description": "Noten der skal gemmes"},
            },
            "required": ["note"],
        },
    },
]


# ── Tool-eksekvering ────────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict, state: dict) -> str:
    handlers = {
        "web_search": _web_search,
        "save_idea": _save_idea,
        "advance_phase": _advance_phase,
        "build_landing_page": _build_landing_page,
        "write_outreach_email": _write_outreach_email,
        "add_note": _add_note,
    }
    handler = handlers.get(name)
    if not handler:
        return f"Ukendt tool: {name}"
    return handler(inputs, state)


def _web_search(inputs: dict, state: dict) -> str:
    query = inputs["query"]
    max_results = inputs.get("max_results", 5)

    if not HAS_SEARCH:
        return (
            "SIMULERET SØGNING (installer duckduckgo-search for rigtige resultater)\n"
            f"Søgeord: '{query}'\n"
            "Eksempel-resultater:\n"
            "1. Stor efterspørgsel på AI-drevne tools til SMV'er\n"
            "2. Konkurrenter: mange, men ingen dominerer det danske marked\n"
            "3. Typisk pris: 99-499 kr/md for SaaS-tools\n"
            "4. Målgruppe: selvstændige og små teams (2-10 ansatte)"
        )

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "Ingen resultater fundet."
        lines = []
        for r in results:
            lines.append(f"**{r.get('title', '')}**\n{r.get('body', '')}\nURL: {r.get('href', '')}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Søgefejl: {e}"


def _save_idea(inputs: dict, state: dict) -> str:
    state["company_name"] = inputs["company_name"]
    state["idea"] = inputs["idea"]
    state["target_market"] = inputs["target_market"]
    state["value_proposition"] = inputs.get("value_proposition", "")
    return f"✅ Idé gemt: '{inputs['company_name']}' — {inputs['idea'][:100]}"


def _advance_phase(inputs: dict, state: dict) -> str:
    next_phase = inputs["next_phase"]
    reason = inputs["reason"]
    old_phase = state["phase"]
    state["phase"] = next_phase
    state["notes"].append(f"Fase skiftet: {old_phase} → {next_phase}. {reason}")
    return f"✅ Fase avanceret: {old_phase} → {next_phase}"


def _build_landing_page(inputs: dict, state: dict) -> str:
    company_name = inputs["company_name"]
    tagline = inputs["tagline"]
    description = inputs["description"]
    features = inputs.get("features", [])
    cta_text = inputs.get("cta_text", "Kom i gang gratis")
    price = inputs.get("price", "")

    features_html = "\n".join(
        '<li class="feature-item">✓ ' + f + '</li>' for f in features
    )

    price_html = f'<p class="price">{price}</p>' if price else ""

    desc_html = "".join(f"<p>{para.strip()}</p>" for para in description.split("\n") if para.strip())
    year = datetime.now().year

    html = f"""<!DOCTYPE html>
<html lang="da">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{company_name}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #1a1a1a; }}
    .hero {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 80px 20px; text-align: center; }}
    .hero h1 {{ font-size: 3rem; font-weight: 800; margin-bottom: 16px; }}
    .hero p {{ font-size: 1.3rem; opacity: 0.9; max-width: 600px; margin: 0 auto 32px; }}
    .cta-btn {{ background: white; color: #667eea; padding: 16px 40px; border-radius: 50px; font-size: 1.1rem; font-weight: 700; text-decoration: none; display: inline-block; transition: transform 0.2s; }}
    .cta-btn:hover {{ transform: scale(1.05); }}
    .description {{ padding: 60px 20px; max-width: 800px; margin: 0 auto; }}
    .description p {{ font-size: 1.1rem; line-height: 1.8; color: #444; margin-bottom: 16px; }}
    .features {{ background: #f9f9f9; padding: 60px 20px; text-align: center; }}
    .features h2 {{ font-size: 2rem; margin-bottom: 40px; }}
    .feature-list {{ list-style: none; display: inline-block; text-align: left; }}
    .feature-item {{ font-size: 1.1rem; padding: 10px 0; color: #333; }}
    .pricing {{ padding: 60px 20px; text-align: center; }}
    .price {{ font-size: 2.5rem; font-weight: 800; color: #667eea; margin: 20px 0; }}
    footer {{ background: #1a1a1a; color: #aaa; text-align: center; padding: 30px; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <section class="hero">
    <h1>{company_name}</h1>
    <p>{tagline}</p>
    <a href="#" class="cta-btn">{cta_text}</a>
  </section>

  <section class="description">
    {desc_html}
  </section>

  <section class="features">
    <h2>Hvad får du?</h2>
    <ul class="feature-list">
      {features_html}
    </ul>
  </section>

  <section class="pricing">
    <h2>Simpel, gennemsigtig pris</h2>
    {price_html}
    <a href="#" class="cta-btn" style="background: #667eea; color: white;">{cta_text}</a>
  </section>

  <footer>
    <p>© {year} {company_name}. Alle rettigheder forbeholdes.</p>
  </footer>
</body>
</html>"""

    filename = OUTPUT_DIR / f"landing_page_{company_name.lower().replace(' ', '_')}.html"
    filename.write_text(html, encoding="utf-8")
    state["landing_page_path"] = str(filename)
    return f"✅ Landing page bygget og gemt: {filename}"


def _write_outreach_email(inputs: dict, state: dict) -> str:
    recipient_type = inputs["recipient_type"]
    subject = inputs["subject"]
    body = inputs["body"]
    send_to = inputs.get("send_to", "")

    email_record = {
        "recipient_type": recipient_type,
        "subject": subject,
        "body": body,
        "written_at": datetime.now().isoformat(),
    }

    # Gem email som fil
    idx = len(state.get("emails_written", [])) + 1
    email_file = OUTPUT_DIR / f"email_{idx:02d}_{recipient_type.replace(' ', '_')[:30]}.txt"
    email_file.write_text(
        f"TIL: {recipient_type}\nEMNE: {subject}\n\n{body}",
        encoding="utf-8",
    )

    state.setdefault("emails_written", []).append(email_record)

    # Send via SMTP hvis konfigureret og modtager angivet
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_from = os.environ.get("SMTP_FROM")
    smtp_pass = os.environ.get("SMTP_PASSWORD")

    if send_to and smtp_host and smtp_from and smtp_pass:
        try:
            msg = MIMEMultipart()
            msg["From"] = smtp_from
            msg["To"] = send_to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))
            with smtplib.SMTP_SSL(smtp_host, 465) as server:
                server.login(smtp_from, smtp_pass)
                server.sendmail(smtp_from, send_to, msg.as_string())
            return f"✅ Email skrevet og SENDT til {send_to}. Gemt: {email_file}"
        except Exception as e:
            return f"✅ Email skrevet og gemt: {email_file}\n⚠️ Send fejlede: {e}"

    return f"✅ Email skrevet og gemt: {email_file} (Sæt SMTP_HOST/SMTP_FROM/SMTP_PASSWORD for at sende rigtigt)"


def _add_note(inputs: dict, state: dict) -> str:
    note = inputs["note"]
    state.setdefault("notes", []).append(note)
    return f"✅ Note tilføjet: {note[:100]}"
