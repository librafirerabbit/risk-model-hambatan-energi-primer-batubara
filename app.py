from urllib.parse import quote

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# KONFIGURASI APLIKASI
# ============================================================

st.set_page_config(
    page_title="Risk Model Hambatan Energi Primer Batubara",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# KONFIGURASI SUMBER DATA
# ============================================================

SPREADSHEET_ID = (
    "1NGn-bwo12bGiksqKzyZ1J1968w3ILORv-Pr49OnZHG0"
)

SHEET_LOSS = "Loss_Event_Model"
SHEET_HOP = "HOP_Harian"

LOSS_ID_COLUMN = "Kejadian_Loss_ID"


def google_sheet_csv_url(sheet_name: str) -> str:
    """Membentuk URL CSV untuk tab Google Sheet publik."""

    encoded_sheet = quote(sheet_name)

    return (
        f"https://docs.google.com/spreadsheets/d/"
        f"{SPREADSHEET_ID}/gviz/tq"
        f"?tqx=out:csv&sheet={encoded_sheet}"
    )


# ============================================================
# FORMAT ANGKA
# ============================================================

def format_number(value, decimals: int = 0) -> str:
    """Format angka: koma ribuan dan titik desimal."""

    if pd.isna(value):
        return "-"

    return f"{float(value):,.{decimals}f}"


def format_compact_rupiah(value) -> str:
    """Format nilai Rupiah menjadi juta, miliar, atau triliun."""

    if pd.isna(value):
        return "Rp0"

    value = float(value)

    if abs(value) >= 1_000_000_000_000:
        return (
            f"Rp{value / 1_000_000_000_000:,.2f} T"
        )

    if abs(value) >= 1_000_000_000:
        return (
            f"Rp{value / 1_000_000_000:,.2f} B"
        )

    if abs(value) >= 1_000_000:
        return (
            f"Rp{value / 1_000_000:,.2f} M"
        )

    return f"Rp{value:,.0f}"


# ============================================================
# PEMBERSIHAN DATA
# ============================================================

def clean_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Membersihkan nama kolom dan membuang kolom kosong."""

    data = data.copy()

    data.columns = [
        str(column).strip()
        for column in data.columns
    ]

    unnamed_columns = [
        column
        for column in data.columns
        if str(column).startswith("Unnamed:")
    ]

    if unnamed_columns:
        data = data.drop(columns=unnamed_columns)

    return data


def convert_numeric(
    data: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """Mengubah kolom terpilih menjadi numerik."""

    data = data.copy()

    for column in columns:
        if column not in data.columns:
            continue

        cleaned = (
            data[column]
            .astype(str)
            .str.replace("Rp", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )

        data[column] = pd.to_numeric(
            cleaned,
            errors="coerce",
        )

    return data


def convert_dates(
    data: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """Mengubah kolom terpilih menjadi format tanggal."""

    data = data.copy()

    for column in columns:
        if column in data.columns:
            data[column] = pd.to_datetime(
                data[column],
                errors="coerce",
                dayfirst=True,
            )

    return data


# ============================================================
# MEMBACA GOOGLE SHEET
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def load_google_sheet(
    sheet_name: str,
) -> pd.DataFrame:
    """Membaca satu tab Google Sheet publik."""

    url = google_sheet_csv_url(sheet_name)

    data = pd.read_csv(url)
    data = clean_columns(data)

    return data


@st.cache_data(ttl=600, show_spinner=False)
def load_all_data():
    """Membaca dan membersihkan data Kejadian Loss dan HOP."""

    loss = load_google_sheet(SHEET_LOSS)
    hop = load_google_sheet(SHEET_HOP)

    loss = convert_numeric(
        loss,
        [
            "Tahun",
            "Jumlah_Segmen",
            "Loss_Production_MWh",
            "Loss_Opportunity_Rp",
            "Nilai_HOP",
            "Batas_HOP_P20",
        ],
    )

    loss = convert_dates(
        loss,
        [
            "Start_DateTime",
            "End_DateTime",
        ],
    )

    hop = convert_numeric(
        hop,
        [
            "Tahun",
            "Nilai_HOP",
        ],
    )

    hop = convert_dates(
        hop,
        [
            "Tanggal",
        ],
    )

    return loss, hop


# ============================================================
# VALIDASI DATA
# ============================================================

def validate_required_columns(
    data: pd.DataFrame,
    required_columns: list[str],
    table_name: str,
):
    """Menghentikan aplikasi jika kolom utama tidak ditemukan."""

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:
        st.error(
            f"Kolom berikut tidak ditemukan pada "
            f"{table_name}: {', '.join(missing_columns)}"
        )

        st.info(
            f"Kolom yang tersedia: "
            f"{', '.join(data.columns)}"
        )

        st.stop()


# ============================================================
# MEMUAT DATA
# ============================================================

try:
    with st.spinner(
        "Membaca data Google Sheet publik..."
    ):
        loss_data, hop_data = load_all_data()

except Exception as error:
    st.error(
        "Google Sheet publik belum berhasil dibaca."
    )

    st.exception(error)

    st.info(
        "Pastikan Google Sheet telah diatur sebagai "
        "'Anyone with the link' dan setiap tab "
        "masih tersedia."
    )

    st.stop()


validate_required_columns(
    loss_data,
    [
        LOSS_ID_COLUMN,
        "Tahun",
        "Regional",
        "HOP_Unit_Key",
        "Kategori_Final",
        "Loss_Production_MWh",
        "Loss_Opportunity_Rp",
    ],
    SHEET_LOSS,
)

validate_required_columns(
    hop_data,
    [
        "Tanggal",
        "HOP_Unit_Key",
        "Nilai_HOP",
    ],
    SHEET_HOP,
)


# ============================================================
# SIDEBAR FILTER
# ============================================================

st.sidebar.title("Filter Dashboard")

st.sidebar.caption(
    "Sumber data: Google Sheet publik"
)

st.sidebar.divider()


available_years = sorted(
    loss_data["Tahun"]
    .dropna()
    .astype(int)
    .unique()
    .tolist()
)

selected_years = st.sidebar.multiselect(
    "Tahun",
    options=available_years,
    default=available_years,
)


regional_options = sorted(
    loss_data["Regional"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

selected_regionals = st.sidebar.multiselect(
    "Regional",
    options=regional_options,
    default=regional_options,
)


unit_options = sorted(
    loss_data["HOP_Unit_Key"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

selected_units = st.sidebar.multiselect(
    "Unit",
    options=unit_options,
    default=unit_options,
)


category_options = sorted(
    loss_data["Kategori_Final"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

selected_categories = st.sidebar.multiselect(
    "Kategori final",
    options=category_options,
    default=category_options,
)


readiness_options = []

if "Kesiapan_Model" in loss_data.columns:
    readiness_options = sorted(
        loss_data["Kesiapan_Model"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

selected_readiness = st.sidebar.multiselect(
    "Kesiapan model",
    options=readiness_options,
    default=readiness_options,
)


if st.sidebar.button(
    "Muat ulang data",
    use_container_width=True,
):
    st.cache_data.clear()
    st.rerun()


st.sidebar.divider()

st.sidebar.caption(
    "Sumber aktif: Google Sheet Publik"
)


# ============================================================
# PENERAPAN FILTER KEJADIAN LOSS
# ============================================================

filtered = loss_data.copy()

if selected_years:
    filtered = filtered[
        filtered["Tahun"].isin(selected_years)
    ]

if selected_regionals:
    filtered = filtered[
        filtered["Regional"].isin(selected_regionals)
    ]

if selected_units:
    filtered = filtered[
        filtered["HOP_Unit_Key"].isin(selected_units)
    ]

if selected_categories:
    filtered = filtered[
        filtered["Kategori_Final"].isin(
            selected_categories
        )
    ]

if (
    selected_readiness
    and "Kesiapan_Model" in filtered.columns
):
    filtered = filtered[
        filtered["Kesiapan_Model"].isin(
            selected_readiness
        )
    ]


# ============================================================
# PENERAPAN FILTER HOP
# ============================================================

filtered_hop = hop_data.copy()

if selected_years and "Tahun" in filtered_hop.columns:
    filtered_hop = filtered_hop[
        filtered_hop["Tahun"].isin(
            selected_years
        )
    ]

if selected_units:
    filtered_hop = filtered_hop[
        filtered_hop["HOP_Unit_Key"].isin(
            selected_units
        )
    ]


# ============================================================
# HEADER DASHBOARD
# ============================================================

st.title(
    "Risk Model Hambatan Energi Primer Batubara"
)

st.caption(
    "Pemodelan risiko berbasis Kejadian Loss, "
    "HOP harian, frekuensi kejadian, "
    "dan severity kerugian."
)


# ============================================================
# KPI UTAMA
# ============================================================

total_loss_events = (
    filtered[LOSS_ID_COLUMN].nunique()
)

total_loss_production = (
    filtered["Loss_Production_MWh"].sum()
)

total_loss_opportunity = (
    filtered["Loss_Opportunity_Rp"].sum()
)

# Seluruh observasi HOP pada sumber data
total_hop_records = len(hop_data)

# Observasi HOP yang sesuai dengan filter tahun dan unit
filtered_hop_records = len(filtered_hop)

average_hop = filtered_hop["Nilai_HOP"].mean()

minimum_hop = filtered_hop["Nilai_HOP"].min()


kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

kpi1.metric(
    "Kejadian Loss",
    format_number(total_loss_events),
    help=(
        "Jumlah kejadian loss setelah segmen "
        "KKP/PLO yang berkesinambungan digabungkan."
    ),
)

kpi2.metric(
    "Loss Production",
    f"{format_number(total_loss_production, 3)} MWh",
)

kpi3.metric(
    "Loss Opportunity",
    format_compact_rupiah(
        total_loss_opportunity
    ),
)

kpi4.metric(
    "Total Data HOP",
    format_number(total_hop_records),
    help=(
        "Seluruh observasi HOP harian yang tersedia "
        "pada Google Sheet sebelum filter diterapkan."
    ),
)

kpi5.metric(
    "HOP Sesuai Filter",
    format_number(filtered_hop_records),
    help=(
        "Observasi HOP harian yang sesuai dengan "
        "filter tahun dan unit."
    ),
)


if filtered.empty:
    st.warning(
        "Tidak ada data yang sesuai dengan "
        "kombinasi filter."
    )

    st.stop()


st.success(
    f"Google Sheet publik berhasil dibaca. "
    f"Terdapat {total_loss_events:,} kejadian loss "
    f"sesuai filter."
)


# ============================================================
# TAB DASHBOARD
# ============================================================

(
    tab_summary,
    tab_loss,
    tab_hop,
    tab_quality,
    tab_method,
) = st.tabs(
    [
        "Ringkasan",
        "Kejadian Loss",
        "HOP Harian",
        "Kualitas Data",
        "Metodologi",
    ]
)


# ============================================================
# TAB RINGKASAN
# ============================================================

with tab_summary:
    st.subheader(
        "Ringkasan Risiko Hambatan Energi Primer"
    )

    col1, col2 = st.columns(2)

    with col1:
        monthly_loss = filtered.copy()

        if "Start_DateTime" in monthly_loss.columns:
            monthly_loss["Periode"] = (
                monthly_loss["Start_DateTime"]
                .dt.to_period("M")
                .astype(str)
            )

            monthly_summary = (
                monthly_loss
                .dropna(subset=["Periode"])
                .groupby(
                    "Periode",
                    as_index=False,
                )
                .agg(
                    Loss_Production_MWh=(
                        "Loss_Production_MWh",
                        "sum",
                    ),
                    Jumlah_Kejadian=(
                        LOSS_ID_COLUMN,
                        "nunique",
                    ),
                )
            )

            figure_monthly = px.line(
                monthly_summary,
                x="Periode",
                y="Loss_Production_MWh",
                markers=True,
                title=(
                    "Tren Loss Production Bulanan"
                ),
                labels={
                    "Periode": "Periode",
                    "Loss_Production_MWh": (
                        "Loss Production (MWh)"
                    ),
                },
                color_discrete_sequence=[
                    "#0F6CBD"
                ],
            )

            figure_monthly.update_layout(
                template="plotly_white",
                height=420,
                margin=dict(
                    l=20,
                    r=20,
                    t=60,
                    b=20,
                ),
            )

            st.plotly_chart(
                figure_monthly,
                use_container_width=True,
            )

    with col2:
        regional_summary = (
            filtered
            .groupby(
                "Regional",
                as_index=False,
            )
            .agg(
                Loss_Opportunity_Rp=(
                    "Loss_Opportunity_Rp",
                    "sum",
                )
            )
            .sort_values(
                "Loss_Opportunity_Rp",
                ascending=False,
            )
        )

        figure_regional = px.bar(
            regional_summary,
            x="Regional",
            y="Loss_Opportunity_Rp",
            title=(
                "Loss Opportunity per Regional"
            ),
            labels={
                "Regional": "Regional",
                "Loss_Opportunity_Rp": (
                    "Loss Opportunity (Rp)"
                ),
            },
            color_discrete_sequence=[
                "#00A6A6"
            ],
        )

        figure_regional.update_layout(
            template="plotly_white",
            height=420,
            margin=dict(
                l=20,
                r=20,
                t=60,
                b=20,
            ),
        )

        st.plotly_chart(
            figure_regional,
            use_container_width=True,
        )


    col3, col4 = st.columns(2)

    with col3:
        category_summary = (
            filtered
            .groupby(
                "Kategori_Final",
                as_index=False,
            )
            .agg(
                Loss_Opportunity_Rp=(
                    "Loss_Opportunity_Rp",
                    "sum",
                ),
                Jumlah_Kejadian=(
                    LOSS_ID_COLUMN,
                    "nunique",
                ),
            )
            .sort_values(
                "Loss_Opportunity_Rp",
                ascending=True,
            )
        )

        figure_category = px.bar(
            category_summary,
            x="Loss_Opportunity_Rp",
            y="Kategori_Final",
            orientation="h",
            title=(
                "Loss Opportunity per Kategori"
            ),
            labels={
                "Kategori_Final": "Kategori",
                "Loss_Opportunity_Rp": (
                    "Loss Opportunity (Rp)"
                ),
                "Jumlah_Kejadian": (
                    "Jumlah Kejadian Loss"
                ),
            },
            color="Jumlah_Kejadian",
            color_continuous_scale="Blues",
        )

        figure_category.update_layout(
            template="plotly_white",
            height=460,
            margin=dict(
                l=20,
                r=20,
                t=60,
                b=20,
            ),
        )

        st.plotly_chart(
            figure_category,
            use_container_width=True,
        )

    with col4:
        unit_summary = (
            filtered
            .groupby(
                "HOP_Unit_Key",
                as_index=False,
            )
            .agg(
                Loss_Production_MWh=(
                    "Loss_Production_MWh",
                    "sum",
                )
            )
            .sort_values(
                "Loss_Production_MWh",
                ascending=False,
            )
            .head(10)
        )

        figure_unit = px.bar(
            unit_summary.sort_values(
                "Loss_Production_MWh"
            ),
            x="Loss_Production_MWh",
            y="HOP_Unit_Key",
            orientation="h",
            title=(
                "Top 10 Unit Berdasarkan "
                "Loss Production"
            ),
            labels={
                "HOP_Unit_Key": "Unit",
                "Loss_Production_MWh": (
                    "Loss Production (MWh)"
                ),
            },
            color_discrete_sequence=[
                "#F59E0B"
            ],
        )

        figure_unit.update_layout(
            template="plotly_white",
            height=460,
            margin=dict(
                l=20,
                r=20,
                t=60,
                b=20,
            ),
        )

        st.plotly_chart(
            figure_unit,
            use_container_width=True,
        )


# ============================================================
# TAB KEJADIAN LOSS
# ============================================================

with tab_loss:
    st.subheader("Data Kejadian Loss")

    st.caption(
        "Satu Kejadian Loss dapat terdiri dari "
        "satu atau beberapa segmen KKP/PLO yang "
        "berkesinambungan."
    )

    display_columns = [
        LOSS_ID_COLUMN,
        "Tahun",
        "Bulan",
        "Regional",
        "Unit_Asli",
        "HOP_Unit_Key",
        "Kategori_Final",
        "Subkategori_Event",
        "Start_DateTime",
        "End_DateTime",
        "Jenis_Kejadian_Loss",
        "Jumlah_Segmen",
        "Penyebab_Source",
        "Loss_Production_MWh",
        "Loss_Opportunity_Rp",
        "Nilai_HOP",
        "Batas_HOP_P20",
        "Status_HOP",
        "Sumber_HOP",
        "Kesiapan_Model",
        "Penggunaan_Model",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in filtered.columns
    ]

    loss_display = filtered[
        display_columns
    ].copy()

    sort_columns = [
        column
        for column in [
            "Start_DateTime",
            LOSS_ID_COLUMN,
        ]
        if column in loss_display.columns
    ]

    if sort_columns:
        loss_display = loss_display.sort_values(
            sort_columns,
            ascending=False,
        )

    st.dataframe(
        loss_display,
        use_container_width=True,
        hide_index=True,
        height=620,
        column_config={
            LOSS_ID_COLUMN: (
                st.column_config.TextColumn(
                    "Kejadian Loss ID",
                    width="medium",
                )
            ),
            "Jenis_Kejadian_Loss": (
                st.column_config.TextColumn(
                    "Jenis Kejadian Loss"
                )
            ),
            "Loss_Production_MWh": (
                st.column_config.NumberColumn(
                    "Loss Production MWh",
                    format="%.3f",
                )
            ),
            "Loss_Opportunity_Rp": (
                st.column_config.NumberColumn(
                    "Loss Opportunity Rp",
                    format="Rp %,.0f",
                )
            ),
            "Nilai_HOP": (
                st.column_config.NumberColumn(
                    "Nilai HOP",
                    format="%.2f",
                )
            ),
            "Batas_HOP_P20": (
                st.column_config.NumberColumn(
                    "Batas HOP P20",
                    format="%.2f",
                )
            ),
            "Start_DateTime": (
                st.column_config.DatetimeColumn(
                    "Waktu Mulai",
                    format="DD-MMM-YYYY HH:mm",
                )
            ),
            "End_DateTime": (
                st.column_config.DatetimeColumn(
                    "Waktu Selesai",
                    format="DD-MMM-YYYY HH:mm",
                )
            ),
        },
    )

    csv_loss = loss_display.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Unduh Kejadian Loss (CSV)",
        data=csv_loss,
        file_name=(
            "kejadian_loss_terfilter.csv"
        ),
        mime="text/csv",
    )


# ============================================================
# TAB HOP HARIAN
# ============================================================

with tab_hop:
    st.subheader("Data HOP Harian")

    hop_metric1, hop_metric2, hop_metric3 = (
        st.columns(3)
    )

    hop_metric1.metric(
        "HOP Sesuai Filter",
        format_number(filtered_hop_records),
        help=(
            "Jumlah observasi HOP setelah filter "
            "tahun dan unit diterapkan."
        ),
    )

    hop_metric2.metric(
        "Rata-rata HOP",
        format_number(average_hop, 2),
        help=(
            "Rata-rata nilai HOP dari seluruh "
            "observasi yang sesuai filter."
        ),
    )

    hop_metric3.metric(
        "Minimum HOP",
        format_number(minimum_hop, 2),
        help=(
            "Nilai HOP terendah dari observasi "
            "yang sesuai filter."
        ),
    )

    hop_col1, hop_col2 = st.columns([2, 1])

    with hop_col1:
        if not filtered_hop.empty:
            hop_trend = (
                filtered_hop
                .dropna(
                    subset=[
                        "Tanggal",
                        "Nilai_HOP",
                    ]
                )
                .groupby(
                    "Tanggal",
                    as_index=False,
                )
                .agg(
                    Nilai_HOP=(
                        "Nilai_HOP",
                        "mean",
                    )
                )
            )

            figure_hop = px.line(
                hop_trend,
                x="Tanggal",
                y="Nilai_HOP",
                title=(
                    "Tren Rata-rata HOP Harian"
                ),
                labels={
                    "Tanggal": "Tanggal",
                    "Nilai_HOP": "HOP",
                },
                color_discrete_sequence=[
                    "#0F6CBD"
                ],
            )

            figure_hop.update_layout(
                template="plotly_white",
                height=430,
                margin=dict(
                    l=20,
                    r=20,
                    t=60,
                    b=20,
                ),
            )

            st.plotly_chart(
                figure_hop,
                use_container_width=True,
            )

        else:
            st.info(
                "Tidak ada data HOP sesuai filter."
            )

    with hop_col2:
        hop_by_unit = (
            filtered_hop
            .groupby(
                "HOP_Unit_Key",
                as_index=False,
            )
            .agg(
                Rata_Rata_HOP=(
                    "Nilai_HOP",
                    "mean",
                ),
                Minimum_HOP=(
                    "Nilai_HOP",
                    "min",
                ),
                Jumlah_Data=(
                    "Nilai_HOP",
                    "count",
                ),
            )
            .sort_values(
                "Rata_Rata_HOP",
                ascending=True,
            )
        )

        st.dataframe(
            hop_by_unit,
            use_container_width=True,
            hide_index=True,
            height=430,
            column_config={
                "Rata_Rata_HOP": (
                    st.column_config.NumberColumn(
                        "Rata-rata HOP",
                        format="%.2f",
                    )
                ),
                "Minimum_HOP": (
                    st.column_config.NumberColumn(
                        "Minimum HOP",
                        format="%.2f",
                    )
                ),
                "Jumlah_Data": (
                    st.column_config.NumberColumn(
                        "Jumlah Data",
                        format="%d",
                    )
                ),
            },
        )

    st.subheader(
        "Detail Observasi HOP Harian"
    )

    st.dataframe(
        filtered_hop,
        use_container_width=True,
        hide_index=True,
        height=480,
        column_config={
            "Tanggal": (
                st.column_config.DateColumn(
                    "Tanggal",
                    format="DD-MMM-YYYY",
                )
            ),
            "Nilai_HOP": (
                st.column_config.NumberColumn(
                    "Nilai HOP",
                    format="%.2f",
                )
            ),
        },
    )


# ============================================================
# TAB KUALITAS DATA
# ============================================================

with tab_quality:
    st.subheader(
        "Kualitas dan Kesiapan Data"
    )

    readiness_count = pd.DataFrame()

    if "Kesiapan_Model" in filtered.columns:
        readiness_count = (
            filtered["Kesiapan_Model"]
            .fillna(
                "BELUM DIKLASIFIKASIKAN"
            )
            .value_counts()
            .rename_axis("Kesiapan_Model")
            .reset_index(
                name="Jumlah_Kejadian"
            )
        )

    if not readiness_count.empty:
        figure_readiness = px.bar(
            readiness_count,
            x="Kesiapan_Model",
            y="Jumlah_Kejadian",
            color="Kesiapan_Model",
            title=(
                "Status Kesiapan Data untuk Model"
            ),
            labels={
                "Kesiapan_Model": (
                    "Kesiapan Model"
                ),
                "Jumlah_Kejadian": (
                    "Jumlah Kejadian Loss"
                ),
            },
        )

        figure_readiness.update_layout(
            template="plotly_white",
            showlegend=False,
            height=420,
        )

        st.plotly_chart(
            figure_readiness,
            use_container_width=True,
        )

    missing_hop = 0

    if "Nilai_HOP" in filtered.columns:
        missing_hop = (
            filtered["Nilai_HOP"]
            .isna()
            .sum()
        )

    duplicate_loss_id = (
        filtered[LOSS_ID_COLUMN]
        .duplicated()
        .sum()
    )

    quality1, quality2, quality3 = (
        st.columns(3)
    )

    quality1.metric(
        "Kejadian Loss Tanpa HOP",
        format_number(missing_hop),
    )

    quality2.metric(
        "Duplikasi Kejadian Loss ID",
        format_number(duplicate_loss_id),
    )

    quality3.metric(
        "Total Kejadian Tersaring",
        format_number(total_loss_events),
    )


# ============================================================
# TAB METODOLOGI
# ============================================================

with tab_method:
    st.subheader(
        "Metodologi Data dan Pemodelan"
    )

    st.markdown(
        """
### Definisi Kejadian Loss

**Kejadian Loss** adalah satu rangkaian kejadian risiko
yang menimbulkan kehilangan produksi atau kehilangan
peluang pendapatan.

Beberapa segmen KKP/PLO yang masih merupakan satu
rangkaian kejadian dapat digabungkan menjadi satu
Kejadian Loss. Tujuannya adalah mencegah penghitungan
frekuensi secara berlebihan atau *double counting*.

### Struktur data

1. `Loss_Event_Detail` berfungsi sebagai data rinci
   dan audit trail.
2. `Loss_Event_Model` berfungsi sebagai data utama
   untuk pemodelan.
3. `HOP_Harian` berisi kondisi Hari Operasi
   Persediaan per unit.
4. `Kejadian_Loss_ID` menjadi identitas unik setiap
   Kejadian Loss.
5. Awalan identitas menggunakan format
   `LOSS-TAHUN-NOMOR`.

### Hubungan HOP dan Kejadian Loss

Nilai HOP digunakan untuk menguji apakah penurunan
persediaan energi primer meningkatkan kemungkinan
terjadinya Kejadian Loss.

Model dapat memisahkan frekuensi kejadian berdasarkan:

- HOP rendah;
- HOP normal;
- unit pembangkit;
- regional;
- kategori risiko; dan
- periode waktu.

### Pengembangan model berikutnya

Data ini dapat digunakan untuk:

- estimasi frekuensi Kejadian Loss;
- distribusi severity;
- simulasi Monte Carlo annual loss;
- P50, P90, dan P95;
- probability of exceedance;
- risk heat map; dan
- rekomendasi mitigasi berbasis HOP.
"""
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Risk Model Hambatan Energi Primer Batubara · "
    "Sumber data Google Sheet publik"
)
