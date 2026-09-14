import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Risk Model Hambatan Energi Primer Batubara",
    page_icon="⚡",
    layout="wide",
)


SPREADSHEET_ID = "1NGn-bwo12bGiksqKzyZ1J1968w3ILORv-Pr49OnZHG0"

SHEET_GID = {
    "Loss_Event_Model": "982468318",
    "HOP_Harian": "550714475",
}


@st.cache_data(ttl=900)
def load_google_sheet(gid: str) -> pd.DataFrame:
    url = (
        f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
        f"/export?format=csv&gid={gid}"
    )
    return pd.read_csv(url)


st.title("Risk Model Hambatan Energi Primer Batubara")
st.caption(
    "Uji koneksi data Loss Event dan HOP dari Google Sheets publik."
)

try:
    loss_event = load_google_sheet(SHEET_GID["Loss_Event_Model"])
    hop_harian = load_google_sheet(SHEET_GID["HOP_Harian"])

    loss_event["Loss_Production_MWh"] = pd.to_numeric(
        loss_event["Loss_Production_MWh"],
        errors="coerce",
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Episode Loss",
        f"{len(loss_event):,}",
    )

    col2.metric(
        "Total Loss Production",
        f"{loss_event['Loss_Production_MWh'].sum():,.3f} MWh",
    )

    col3.metric(
        "Data HOP Harian",
        f"{len(hop_harian):,}",
    )

    st.success("Google Sheet publik berhasil dibaca.")

    st.subheader("Contoh Loss Event Model")
    st.dataframe(
        loss_event.head(10),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Contoh HOP Harian")
    st.dataframe(
        hop_harian.head(10),
        use_container_width=True,
        hide_index=True,
    )

except Exception as error:
    st.error("Data Google Sheet belum berhasil dibaca.")
    st.code(str(error))
