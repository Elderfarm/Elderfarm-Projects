# AI Company Builder 🤖

En autonom AI-agent der forsøger at bygge en virksomhed fra bunden.

## Hvordan det virker

Agenten kører i en loop med fire faser:

```
RESEARCH → VALIDATE → BUILD → OUTREACH → ITERATE → DONE
```

| Fase | Hvad agenten gør |
|------|-----------------|
| **RESEARCH** | Søger på nettet efter lovende virksomhedsidéer og markeder |
| **VALIDATE** | Undersøger konkurrenter, målgruppe og prissætning |
| **BUILD** | Genererer en professionel HTML landing page |
| **OUTREACH** | Skriver personlige outreach-emails til potentielle kunder |
| **ITERATE** | Evaluerer fremskridt og justér strategi |

## Kom i gang

### 1. Installer dependencies

```bash
pip install -r requirements.txt
```

### 2. Sæt API-nøgle

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Kør agenten

```bash
python agent.py
```

## Output

Alt output gemmes i mappen `output/`:
- `landing_page_<navn>.html` — Den genererede landing page
- `email_01_<type>.txt` — Outreach-emails

State gemmes i `company_state.json` — agenten fortsætter fra samme sted hvis du genstarter.

## Valgfri: Send rigtige emails

Sæt disse miljøvariabler for at sende emails via SMTP (f.eks. Gmail):

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_FROM=din@email.com
export SMTP_PASSWORD=dit-app-password
```

## Arkitektur

```
agent.py       — Hoved-loop, kalder Claude og håndterer tool-svar
tools.py       — Tool-definitioner og -eksekvering
output/        — Genererede filer (landing pages, emails)
company_state.json — Persistent state på tværs af kørelser
```
