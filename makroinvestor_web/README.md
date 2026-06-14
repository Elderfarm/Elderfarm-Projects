# Makroinvestor Web

Webbaseret makroinvesteringsanalyse — Flask + Chart.js

## Kør lokalt

```bash
cd makroinvestor_web
pip install -r requirements.txt
python app.py
# Åbn http://localhost:5000
```

## Angiv anden Excel-fil

```bash
MAKRO_EXCEL=/sti/til/din/fil.xlsx python app.py
```

## Deploy (eksempel med Gunicorn)

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```
