"""
Streamlit-side: Kursregulering af noterede aktier (lagerprincip).

Denne fil binder de andre moduler sammen til en brugerflade:
1. Upload af Excel-fil med transaktioner (parser.py)
2. Validering, vist som en tabel brugeren skal godkende (validering.py)
3. Beregning af realiseret/urealiseret gevinst-tab (beregning.py)
4. Eksport til en CSV-fil klar til e-conomics kassekladde (csv_eksport.py)
"""
from __future__ import annotations

from datetime import date

import openpyxl
import pandas as pd
import streamlit as st

from beregning import beregn_alle, resultater_til_dataframe
from csv_eksport import byg_kassekladde_linjer, generer_csv, linjer_til_dataframe
from parser import indlaes_excel
from validering import fund_til_dataframe, har_fejl, opsummer_pr_papir, valider_transaktioner

st.set_page_config(page_title="Kursregulering af aktier", page_icon="📈", layout="wide")
st.title("📈 Kursregulering af aktier")
st.caption(
    "Regner ud, hvor meget I skal beskattes af, fordi jeres aktier er steget eller "
    "faldet i værdi i år (lagerprincippet). Gælder kun noterede aktier."
)

# ---------------------------------------------------------------------------
# 1. Upload
# ---------------------------------------------------------------------------
st.header("1️⃣ Upload jeres køb/salg-liste")
st.caption("Én linje pr. handling: Primo (start af året), Tilgang (køb), Afgang (salg), Ultimo (slut af året).")
uploaded = st.file_uploader("Vælg Excel-fil", type=["xlsx", "xls"])

if uploaded is None:
    st.info("Upload en Excel-fil for at komme i gang. Der ligger et eksempel i `test_data/eksempel_transaktioner.xlsx`.")
    st.stop()

# Find arknavne, så brugeren kan vælge et andet ark end det første, hvis filen
# (ligesom mange rigtige kunde-filer) indeholder flere faner.
try:
    arknavne = openpyxl.load_workbook(uploaded, read_only=True).sheetnames
except Exception as e:  # noqa: BLE001
    st.error(f"Kunne ikke åbne filen som en Excel-fil: {e}")
    st.stop()
uploaded.seek(0)

valgt_ark = arknavne[0]
if len(arknavne) > 1:
    valgt_ark = st.selectbox("Vælg ark", arknavne, index=0)
uploaded.seek(0)

parse_resultat = indlaes_excel(uploaded, ark=valgt_ark)

if not parse_resultat.er_gyldig:
    st.error("Filen kunne ikke læses korrekt:")
    for fejl in parse_resultat.kritiske_fejl:
        st.error(f"- {fejl}")
    st.stop()

with st.expander("Hvilke kolonner fandt vi i din fil?", expanded=False):
    mapping_df = pd.DataFrame(
        [{"Felt": k, "Kolonne i din fil": v} for k, v in parse_resultat.kolonne_mapping.items()]
    )
    st.dataframe(mapping_df, hide_index=True, use_container_width=True)
    for besked in parse_resultat.info:
        st.info(besked)

data = parse_resultat.data

# ---------------------------------------------------------------------------
# 2. Validering
# ---------------------------------------------------------------------------
st.header("2️⃣ Tjek af data")
st.caption("Vi tjekker automatisk, om tallene hænger sammen, før vi regner videre.")
fund = valider_transaktioner(data)
oversigt = opsummer_pr_papir(data, fund)

st.dataframe(
    oversigt,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Status": st.column_config.TextColumn(help="OK = alt i orden. Advarsel = tjek lige. Fejl = skal rettes."),
    },
)

detaljer = fund_til_dataframe(fund)
if not detaljer.empty:
    with st.expander(f"Se detaljer om de {len(detaljer)} ting vi bemærkede", expanded=True):
        st.dataframe(detaljer, hide_index=True, use_container_width=True)
else:
    st.success("✅ Alt ser fint ud — ingen fejl eller advarsler.")

blokeret = har_fejl(fund)
if blokeret:
    st.error(
        "🚫 Der er mindst én fejl, der skal rettes først. Ret filen og upload den igen, "
        "så kan I komme videre til beregningen."
    )
elif not detaljer.empty:
    st.warning("Der er kun advarsler — I kan godt regne videre, men kig lige på dem først.")

# ---------------------------------------------------------------------------
# 3. Beregning
# ---------------------------------------------------------------------------
st.header("3️⃣ Beregn gevinst og tab")
st.caption(
    "Kort fortalt: værdien ved årets start er allerede beskattet sidste år, så det er kun "
    "ændringen i år, der beskattes nu. Vi finder selv ud af, hvilke stykker der er solgt fra "
    "gammel beholdning, og hvilke der er fra årets køb."
)

kan_beregne = st.button("Beregn", type="primary", disabled=blokeret)

if kan_beregne:
    try:
        st.session_state["resultater"] = beregn_alle(data)
    except (ValueError, AssertionError) as e:
        st.error(f"Beregningen kunne ikke gennemføres: {e}")
        st.session_state.pop("resultater", None)

resultater = st.session_state.get("resultater")

if resultater:
    resultat_df = resultater_til_dataframe(resultater)
    st.dataframe(resultat_df, hide_index=True, use_container_width=True)
    st.caption(
        "Kontroltjek (indbygget): Slutværdi + Salgssum − Startværdi − Købesum = Realiseret + Urealiseret."
    )

    # -----------------------------------------------------------------------
    # 4. CSV-eksport
    # -----------------------------------------------------------------------
    st.header("4️⃣ Hent fil til e-conomic")

    seneste_ultimo = data.loc[data["type"] == "ultimo", "dato"].max()
    standard_dato = seneste_ultimo.date() if pd.notna(seneste_ultimo) else date.today()

    col1, col2 = st.columns(2)
    with col1:
        resultatkonto = st.text_input("Konto til kursregulering (resultatopgørelse)", value="7220")
        bogfoeringsdato = st.date_input("Bogføringsdato", value=standard_dato)
        bilagstype = st.text_input("Bilagstype", value="Finansbilag")
    with col2:
        balancekonto = st.text_input("Konto til værdipapirer (balance)", value="6820")
        start_bilagsnummer = st.number_input("Start bilagsnummer", min_value=1, value=1, step=1)

    if resultatkonto and balancekonto:
        linjer = byg_kassekladde_linjer(
            resultater,
            resultatkonto=resultatkonto,
            balancekonto=balancekonto,
            bogfoeringsdato=bogfoeringsdato,
            bilagstype=bilagstype,
            start_bilagsnummer=int(start_bilagsnummer),
        )

        if not linjer:
            st.info("Ingen af aktierne har givet gevinst eller tab (alle beløb er 0) — der er ikke noget at hente.")
        else:
            st.subheader("Sådan kommer filen til at se ud")
            st.dataframe(linjer_til_dataframe(linjer), hide_index=True, use_container_width=True)

            csv_tekst = generer_csv(linjer)
            filnavn = f"kursregulering_kassekladde_{bogfoeringsdato.strftime('%Y%m%d')}.csv"
            st.download_button(
                "⬇️ Download CSV til e-conomic",
                data=csv_tekst.encode("utf-8"),
                file_name=filnavn,
                mime="text/csv",
                type="primary",
            )
    else:
        st.info("Udfyld de to kontonumre for at kunne hente filen.")
