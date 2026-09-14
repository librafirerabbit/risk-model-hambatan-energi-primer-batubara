import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


# =========================================================
# KONFIGURASI APLIKASI
# =========================================================
st.set_page_config(
    page_title="Risk Model Hambatan Energi Primer Batubara",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


SPREADSHEET_ID = "1NGn-bwo12bGiksqKzyZ1J1968w3ILORv-Pr49OnZHG0"

SHEET_GID = {
    "Loss_Event_Model": "982468318",
    "HOP_Harian": "550714475",
}

MONTH_ORDER = [
    "Jan", "Feb", "Mar", "Apr",
    "May", "Jun", "Jul", "Aug",
    "Sep", "Oct", "Nov", "Dec",
]

MONTH_NUMBER = {
    month: number
    for number, month in enumerate(MONTH_ORDER, start=1)
}


# =========================================================
# WARNA DAN TAMPILAN
# =========================================================
PLN_BLUE = "#0072CE"
PLN_NAVY = "#17365D"
PLN_TEAL = "#00A2B8"
PLN_GREEN = "#2E8B57"
PLN_AMBER = "#F4B942"
PLN_RED = "#D64545"

CATEGORY_COLORS = {
    "Pasokan Energi Primer": "#0072CE",
    "Kualitas Energi Primer": "#00A2B8",
    "Infrastruktur Energi Primer": "#F4B942",
    "Peralatan Pengumpan/Pembakaran": "#D96C3D",
}

st.markdown(
    """
    <style>
    .stApp {
        background-color: #F5F7FA;
    }

    [data-testid="stSidebar"] {
        background-color: #E8EEF5;
        border-right: 1px solid #D1D9E6;
    }

    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #D9E2EC;
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 2px 8px rgba(23, 54, 93, 0.06);
    }

    [data-testid="stMetricLabel"] {
        color: #52667A;
        font-weight: 600;
    }

    [data-testid="stMetricValue"] {
        color: #17365D;
    }

    div[data-baseweb="select"] > div {
        background-color: #FFFFFF;
        border-color: #B8C5D6;
    }

    .dashboard-note {
        background: #E8F4FD;
        border-left: 5px solid #0072CE;
        border-radius: 8px;
        color: #17365D;
        padding: 14px 18px;
        margin: 8px 0 20px 0;
    }

    .quality-warning {
        background: #FFF5D9;
        border-left: 5px solid #F4B942;
        border-radius: 8px;
        color: #5C4700;
        padding: 14px 18px;
        margin: 10px 0;
    }

    .section-title {
        color: #17365D;
        font-size: 1.45rem;
        font-weight: 700;
        margin-top: 16px;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# FUNGSI DATA
# =========================================================
@st.cache_data(ttl=900)
def load_google_sheet(gid: str) -> pd.DataFrame:
    url = (
        f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
        f"/export?format=csv&gid={gid}"
    )
    return pd.read_csv(url)


def clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace("Rp", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


def format_number(value: float, decimals: int = 0) -> str:
    if pd.isna(value):
        value = 0
    return f"{value:,.{decimals}f}"


def format_rupiah_short(value: float) -> str:
    if pd.isna(value):
        return "Rp0"

    value = float(value)

    if abs(value) >= 1_000_000_000_000:
        return f"Rp{value / 1_000_000_000_000:,.2f} T"
    if abs(value) >= 1_000_000_000:
        return f"Rp{value / 1_000_000_000:,.2f} B"
    if abs(value) >= 1_000_000:
        return f"Rp{value / 1_000_000:,.2f} M"

    return f"Rp{value:,.0f}"


def safe_multiselect(label: str, options: list, key: str) -> list:
    return st.sidebar.multiselect(
        label=label,
        options=options,
        default=options,
        key=key,
    )


# =========================================================
# MEMUAT DAN MEMBERSIHKAN DATA
# =========================================================
try:
    loss_event = load_google_sheet(SHEET_GID["Loss_Event_Model"])
    hop_harian = load_google_sheet(SHEET_GID["HOP_Harian"])

except Exception as error:
    st.error("Google Sheet publik belum berhasil dibaca.")
    st.code(str(error))
    st.stop()


required_loss_columns = [
    "Episode_ID",
    "Tahun",
    "Bulan",
    "Regional",
    "Unit_Asli",
    "HOP_Unit_Key",
    "Kategori_Final",
    "Episode_Type",
    "Loss_Production_MWh",
    "Loss_Opportunity_Rp",
    "Kesiapan_Model",
]

missing_columns = [
    column
    for column in required_loss_columns
    if column not in loss_event.columns
]

if missing_columns:
    st.error(
        "Kolom berikut belum ditemukan pada sheet Loss_Event_Model: "
        + ", ".join(missing_columns)
    )
    st.stop()


for column in [
    "Tahun",
    "Jumlah_Segmen",
    "Loss_Production_MWh",
    "Loss_Opportunity_Rp",
    "Nilai_HOP",
    "Batas_HOP_P20",
]:
    if column in loss_event.columns:
        loss_event[column] = clean_numeric(loss_event[column])


if "Start_DateTime" in loss_event.columns:
    loss_event["Start_DateTime"] = pd.to_datetime(
        loss_event["Start_DateTime"],
        errors="coerce",
        dayfirst=True,
    )

if "End_DateTime" in loss_event.columns:
    loss_event["End_DateTime"] = pd.to_datetime(
        loss_event["End_DateTime"],
        errors="coerce",
        dayfirst=True,
    )


for column in ["Tahun", "Bulan", "Nilai_HOP"]:
    if column in hop_harian.columns:
        if column in ["Tahun", "Bulan", "Nilai_HOP"]:
            hop_harian[column] = clean_numeric(hop_harian[column])

if "Tanggal" in hop_harian.columns:
    hop_harian["Tanggal"] = pd.to_datetime(
        hop_harian["Tanggal"],
        errors="coerce",
        dayfirst=True,
    )


loss_event["Bulan_No"] = (
    loss_event["Bulan"]
    .astype(str)
    .str.strip()
    .map(MONTH_NUMBER)
)

loss_event["Kategori_Final"] = (
    loss_event["Kategori_Final"]
    .fillna("Belum Diklasifikasikan")
    .astype(str)
    .str.strip()
)

loss_event["Regional"] = (
    loss_event["Regional"]
    .fillna("Belum Teridentifikasi")
    .astype(str)
    .str.strip()
)

loss_event["Unit_Asli"] = (
    loss_event["Unit_Asli"]
    .fillna("Belum Teridentifikasi")
    .astype(str)
    .str.strip()
)


# =========================================================
# SIDEBAR FILTER
# =========================================================
st.sidebar.title("Filter Dashboard")
st.sidebar.caption("Sumber: Google Sheet MODEL READY")

year_options = sorted(
    loss_event["Tahun"].dropna().astype(int).unique().tolist()
)

selected_years = safe_multiselect(
    "Tahun",
    year_options,
    "filter_year",
)

year_filtered = loss_event[
    loss_event["Tahun"].isin(selected_years)
].copy()

regional_options = sorted(
    year_filtered["Regional"].dropna().unique().tolist()
)

selected_regionals = safe_multiselect(
    "Regional",
    regional_options,
    "filter_regional",
)

regional_filtered = year_filtered[
    year_filtered["Regional"].isin(selected_regionals)
].copy()

unit_options = sorted(
    regional_filtered["Unit_Asli"].dropna().unique().tolist()
)

selected_units = safe_multiselect(
    "Unit",
    unit_options,
    "filter_unit",
)

unit_filtered = regional_filtered[
    regional_filtered["Unit_Asli"].isin(selected_units)
].copy()

category_options = sorted(
    unit_filtered["Kategori_Final"].dropna().unique().tolist()
)

selected_categories = safe_multiselect(
    "Kategori Risiko",
    category_options,
    "filter_category",
)

filtered = unit_filtered[
    unit_filtered["Kategori_Final"].isin(selected_categories)
].copy()

st.sidebar.divider()
st.sidebar.caption(
    f"{len(filtered):,} episode sesuai filter"
)


# =========================================================
# JUDUL DASHBOARD
# =========================================================
st.title("Risk Model Hambatan Energi Primer Batubara")

st.markdown(
    """
    <div class="dashboard-note">
        Dashboard mengolah episode loss production, loss opportunity,
        kondisi HOP, dan kesiapan data untuk pemodelan risiko.
    </div>
    """,
    unsafe_allow_html=True,
)


if filtered.empty:
    st.warning("Tidak ada data yang sesuai dengan kombinasi filter.")
    st.stop()


# =========================================================
# KPI UTAMA
# =========================================================
total_episode = filtered["Episode_ID"].nunique()

event_count = filtered.loc[
    filtered["Episode_Type"].eq("EVENT"),
    "Episode_ID",
].nunique()

monthly_aggregate_count = filtered.loc[
    filtered["Episode_Type"].eq("AGREGAT BULANAN"),
    "Episode_ID",
].nunique()

total_loss_mwh = filtered["Loss_Production_MWh"].sum()
total_loss_rp = filtered["Loss_Opportunity_Rp"].sum()

daily_hop_ready = filtered.loc[
    filtered["Kesiapan_Model"].eq("READY - HOP HARIAN"),
    "Episode_ID",
].nunique()

hop_pending = filtered.loc[
    filtered["Kesiapan_Model"].eq("LOSS READY - HOP PENDING"),
    "Episode_ID",
].nunique()


kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric(
    "Episode Model",
    format_number(total_episode),
    help="Jumlah episode setelah penggabungan segmen yang berkesinambungan.",
)

kpi2.metric(
    "Loss Production",
    f"{format_number(total_loss_mwh, 3)} MWh",
)

kpi3.metric(
    "Loss Opportunity",
    format_rupiah_short(total_loss_rp),
)

kpi4.metric(
    "Siap Analisis HOP Harian",
    format_number(daily_hop_ready),
    help="Episode yang memiliki pasangan data HOP pada tanggal kejadian.",
)


st.write("")

detail1, detail2, detail3 = st.columns(3)

detail1.metric(
    "Event Bertanggal",
    format_number(event_count),
)

detail2.metric(
    "Agregat Bulanan",
    format_number(monthly_aggregate_count),
)

detail3.metric(
    "Loss Menunggu Data HOP",
    format_number(hop_pending),
)


if hop_pending > 0:
    st.markdown(
        f"""
        <div class="quality-warning">
            Terdapat <b>{hop_pending:,} episode</b> yang dapat digunakan
            untuk analisis frequency–severity, tetapi belum memiliki
            pasangan HOP harian.
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# TREN BULANAN
# =========================================================
st.markdown(
    '<div class="section-title">Tren Loss Production Bulanan</div>',
    unsafe_allow_html=True,
)

monthly_summary = (
    filtered.groupby(
        ["Bulan_No", "Bulan"],
        as_index=False,
        observed=True,
    )
    .agg(
        Episode=("Episode_ID", "nunique"),
        Loss_Production_MWh=("Loss_Production_MWh", "sum"),
        Loss_Opportunity_Rp=("Loss_Opportunity_Rp", "sum"),
    )
    .sort_values("Bulan_No")
)

fig_monthly = px.bar(
    monthly_summary,
    x="Bulan",
    y="Loss_Production_MWh",
    color="Loss_Production_MWh",
    color_continuous_scale=[
        [0.00, "#9DD9E5"],
        [0.50, "#0072CE"],
        [1.00, "#17365D"],
    ],
    text_auto=".3s",
    custom_data=[
        "Episode",
        "Loss_Opportunity_Rp",
    ],
)

fig_monthly.update_traces(
    hovertemplate=(
        "<b>%{x}</b><br>"
        "Loss Production: %{y:,.3f} MWh<br>"
        "Episode: %{customdata[0]:,.0f}<br>"
        "Loss Opportunity: Rp%{customdata[1]:,.0f}"
        "<extra></extra>"
    )
)

fig_monthly.update_layout(
    height=430,
    margin=dict(l=20, r=20, t=20, b=20),
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#FFFFFF",
    coloraxis_showscale=False,
    xaxis_title="Bulan",
    yaxis_title="Loss Production (MWh)",
    font=dict(color=PLN_NAVY),
)

fig_monthly.update_xaxes(
    showgrid=False,
)

fig_monthly.update_yaxes(
    gridcolor="#DCE3EC",
    zeroline=False,
)

st.plotly_chart(
    fig_monthly,
    use_container_width=True,
)


# =========================================================
# KATEGORI DAN REGIONAL
# =========================================================
chart_left, chart_right = st.columns(2)

with chart_left:
    st.markdown(
        '<div class="section-title">Loss per Kategori Risiko</div>',
        unsafe_allow_html=True,
    )

    category_summary = (
        filtered.groupby(
            "Kategori_Final",
            as_index=False,
            observed=True,
        )
        .agg(
            Episode=("Episode_ID", "nunique"),
            Loss_Production_MWh=("Loss_Production_MWh", "sum"),
        )
        .sort_values(
            "Loss_Production_MWh",
            ascending=True,
        )
    )

    fig_category = px.bar(
        category_summary,
        x="Loss_Production_MWh",
        y="Kategori_Final",
        orientation="h",
        color="Kategori_Final",
        color_discrete_map=CATEGORY_COLORS,
        text_auto=".3s",
        custom_data=["Episode"],
    )

    fig_category.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Loss Production: %{x:,.3f} MWh<br>"
            "Episode: %{customdata[0]:,.0f}"
            "<extra></extra>"
        )
    )

    fig_category.update_layout(
        height=440,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        showlegend=False,
        xaxis_title="Loss Production (MWh)",
        yaxis_title="",
        font=dict(color=PLN_NAVY),
    )

    fig_category.update_xaxes(
        gridcolor="#DCE3EC",
        zeroline=False,
    )

    fig_category.update_yaxes(
        showgrid=False,
    )

    st.plotly_chart(
        fig_category,
        use_container_width=True,
    )


with chart_right:
    st.markdown(
        '<div class="section-title">Loss per Regional</div>',
        unsafe_allow_html=True,
    )

    regional_summary = (
        filtered.groupby(
            "Regional",
            as_index=False,
            observed=True,
        )
        .agg(
            Episode=("Episode_ID", "nunique"),
            Loss_Production_MWh=("Loss_Production_MWh", "sum"),
        )
        .sort_values(
            "Loss_Production_MWh",
            ascending=False,
        )
    )

    fig_regional = px.bar(
        regional_summary,
        x="Regional",
        y="Loss_Production_MWh",
        color="Regional",
        color_discrete_sequence=[
            PLN_BLUE,
            PLN_TEAL,
            PLN_AMBER,
        ],
        text_auto=".3s",
        custom_data=["Episode"],
    )

    fig_regional.update_traces(
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Loss Production: %{y:,.3f} MWh<br>"
            "Episode: %{customdata[0]:,.0f}"
            "<extra></extra>"
        )
    )

    fig_regional.update_layout(
        height=440,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        showlegend=False,
        xaxis_title="Regional",
        yaxis_title="Loss Production (MWh)",
        font=dict(color=PLN_NAVY),
    )

    fig_regional.update_xaxes(
        showgrid=False,
    )

    fig_regional.update_yaxes(
        gridcolor="#DCE3EC",
        zeroline=False,
    )

    st.plotly_chart(
        fig_regional,
        use_container_width=True,
    )


# =========================================================
# PRIORITAS UNIT
# =========================================================
st.markdown(
    '<div class="section-title">Prioritas Unit Berdasarkan Loss Production</div>',
    unsafe_allow_html=True,
)

unit_summary = (
    filtered.groupby(
        ["Regional", "HOP_Unit_Key"],
        as_index=False,
        observed=True,
    )
    .agg(
        Episode=("Episode_ID", "nunique"),
        Loss_Production_MWh=("Loss_Production_MWh", "sum"),
        Loss_Opportunity_Rp=("Loss_Opportunity_Rp", "sum"),
    )
    .sort_values(
        "Loss_Production_MWh",
        ascending=False,
    )
)

unit_summary.insert(
    0,
    "Peringkat",
    np.arange(1, len(unit_summary) + 1),
)

unit_display = unit_summary.copy()

unit_display["Loss Production MWh"] = (
    unit_display["Loss_Production_MWh"]
    .map(lambda value: f"{value:,.3f}")
)

unit_display["Loss Opportunity"] = (
    unit_display["Loss_Opportunity_Rp"]
    .map(format_rupiah_short)
)

unit_display = unit_display.rename(
    columns={
        "Regional": "Regional",
        "HOP_Unit_Key": "Unit",
        "Episode": "Jumlah Episode",
    }
)

unit_display = unit_display[
    [
        "Peringkat",
        "Regional",
        "Unit",
        "Jumlah Episode",
        "Loss Production MWh",
        "Loss Opportunity",
    ]
]

st.dataframe(
    unit_display,
    use_container_width=True,
    hide_index=True,
    height=420,
)


# =========================================================
# PENJELASAN SINGKAT
# =========================================================
with st.expander("Cara membaca halaman Ringkasan Risiko"):
    st.markdown(
        """
        - **Episode Model** merupakan kelompok kejadian setelah segmen
          yang berkesinambungan digabungkan.
        - **Event Bertanggal** dapat digunakan untuk analisis frekuensi.
        - **Agregat Bulanan** digunakan untuk severity dan tren, tetapi
          tidak dianggap sebagai jumlah kejadian.
        - **Siap Analisis HOP Harian** berarti episode mempunyai data HOP
          pada tanggal kejadian.
        - **Loss Menunggu Data HOP** tetap dapat digunakan untuk
          frequency–severity, tetapi belum digunakan dalam analisis
          hubungan HOP dengan kejadian.
        """
    )
