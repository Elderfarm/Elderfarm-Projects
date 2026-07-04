"""
Streamlit-app: Kursregulering af noterede aktier (lagerprincip).

Denne fil binder de andre moduler sammen til en brugerflade:
1. Upload af Excel-fil med transaktioner (parser.py)
2. Validering, vist som en tabel brugeren skal godkende (validering.py)
3. Beregning af realiseret/urealiseret gevinst-tab (beregning.py)
4. Eksport til en CSV-fil klar til e-conomics kassekladde (csv_eksport.py)

Kør appen med:
    streamlit run app.py
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

st.set_page_config(page_title="Kursregulering af aktier", layout="wide")
st.title("Kursregulering af noterede aktier")
st.caption(
    "Beregner realiseret og urealiseret kursgevinst/-tab efter lagerprincippet "
    "og genererer en CSV-fil klar til import i e-conomics kassekladde. "
    "Scope: noterede aktier — ikke obligationer eller finansielle kontrakter."
)

# ---------------------------------------------------------------------------
# 1. Upload
# ---------------------------------------------------------------------------
st.header("1. Upload transaktionsdata")
uploaded = st.file_uploader("Excel-fil med transaktioner pr. værdipapir", type=["xlsx", "xls"])

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

with st.expander("Kolonnegenkendelse", expanded=False):
    st.write("Disse kolonner i din fil blev genkendt:")
    mapping_df = pd.DataFrame(
        [{"Standardfelt": k, "Kolonne i filen": v} for k, v in parse_resultat.kolonne_mapping.items()]
    )
    st.dataframe(mapping_df, hide_index=True, use_container_width=True)
    for besked in parse_resultat.info:
        st.info(besked)

data = parse_resultat.data

# ---------------------------------------------------------------------------
# 2. Validering
# ---------------------------------------------------------------------------
st.header("2. Validering")
fund = valider_transaktioner(data)
oversigt = opsummer_pr_papir(data, fund)

st.dataframe(
    oversigt,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Status": st.column_config.TextColumn(help="OK / Advarsel / Fejl for det enkelte værdipapir"),
    },
)

detaljer = fund_til_dataframe(fund)
if not detaljer.empty:
    with st.expander(f"Se alle {len(detaljer)} valideringsfund", expanded=True):
        st.dataframe(detaljer, hide_index=True, use_container_width=True)
else:
    st.success("Ingen fejl eller advarsler fundet.")

blokeret = har_fejl(fund)
if blokeret:
    st.error(
        "Der er 'Fejl' på mindst ét værdipapir. Ret fejlene i din Excel-fil og upload den igen, "
        "før beregningen kan køres."
    )
elif not detaljer.empty:
    st.warning("Der er kun advarsler — du kan vælge at beregne alligevel, men tjek dem gerne først.")

# ---------------------------------------------------------------------------
# 3. Beregning
# ---------------------------------------------------------------------------
st.header("3. Beregning af realiseret og urealiseret gevinst/tab")
st.caption(
    "Lagerprincip: Primo kurs er sidste års ultimo-kurs (allerede beskattet), ikke den "
    "oprindelige anskaffelsessum. FIFO afgør om et solgt stykke stammer fra primo-beholdningen "
    "eller fra en tilgang i året."
)

kan_beregne = st.button("Beregn kursregulering", type="primary", disabled=blokeret)

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
        "Kontrolsum for hvert papir (indbygget i beregningen): "
        "Ultimoværdi + Salgssum − Primoværdi − Købesum = Realiseret + Urealiseret."
    )

    # -----------------------------------------------------------------------
    # 4. CSV-eksport
    # -----------------------------------------------------------------------
    st.header("4. Eksport til e-conomics kassekladde")

    seneste_ultimo = data.loc[data["type"] == "ultimo", "dato"].max()
    standard_dato = seneste_ultimo.date() if pd.notna(seneste_ultimo) else date.today()

    col1, col2 = st.columns(2)
    with col1:
        resultatkonto = st.text_input("Resultatkonto (kursregulering)", value="7220")
        bogfoeringsdato = st.date_input("Bogføringsdato", value=standard_dato)
        bilagstype = st.text_input("Bilagstype", value="Finansbilag")
    with col2:
        balancekonto = st.text_input("Balancekonto (værdipapirer)", value="6820")
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
            st.info("Ingen af værdipapirerne har en resultatpåvirkning (alle beløb er 0) — der er ikke noget at eksportere.")
        else:
            st.subheader("Preview af CSV-fil")
            st.dataframe(linjer_til_dataframe(linjer), hide_index=True, use_container_width=True)

            csv_tekst = generer_csv(linjer)
            filnavn = f"kursregulering_kassekladde_{bogfoeringsdato.strftime('%Y%m%d')}.csv"
            st.download_button(
                "Download CSV til e-conomic",
                data=csv_tekst.encode("utf-8"),
                file_name=filnavn,
                mime="text/csv",
                type="primary",
            )
    else:
        st.info("Udfyld resultatkonto og balancekonto for at generere CSV-filen.")
