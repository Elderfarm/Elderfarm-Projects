# PostMester 🔨

AI-drevet social media portal til danske håndværkere.

## Kom i gang

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python app.py
```

Åbn derefter http://localhost:5000

## Features

- Upload foto af dit arbejde (valgfrit)
- Beskriv jobbet med et par ord
- Vælg platform (Facebook / Instagram / Begge)
- Vælg tone (Professionel / Venlig / Salg)
- Få et færdigt opslag + hashtags på 10 sekunder
- Kopiér med ét klik

## Deploy

```bash
# Eksempel med gunicorn
pip install gunicorn
gunicorn app:app -w 2 -b 0.0.0.0:8000
```
