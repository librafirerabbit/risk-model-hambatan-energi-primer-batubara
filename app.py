import math
from datetime import date, timedelta
from io import BytesIO
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


APP_VERSION = "2026.09.23-loss-event-detail-v2-v16.5-dashboard-fix"

PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
}


# ============================================================
# KONFIGURASI APLIKASI
# ============================================================

st.set_page_config(
    page_title="PRIME-RISK | Primary Energy Risk Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# KONFIGURASI SUMBER DATA
# ============================================================

SPREADSHEET_ID = (
    "1NGn-bwo12bGiksqKzyZ1J1968w3ILORv-Pr49OnZHG0"
)

SHEET_LOSS = "Loss_Event_Detail_v2"
SHEET_HOP = "HOP_Harian"
SHEET_PARAMETER = "Parameter_Model"
SHEET_MAPPING = "Mapping_Unit"

LOSS_ID_COLUMN = "Kejadian_Loss_ID"


MONTH_LABELS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


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


def impact_score_from_risk_limit_ratio(ratio: float) -> int:
    """Mengubah rasio loss terhadap Risk Limit menjadi skala 1–5."""

    if ratio <= 0.20:
        return 1
    if ratio <= 0.40:
        return 2
    if ratio <= 0.60:
        return 3
    if ratio <= 0.80:
        return 4
    return 5


def likelihood_score_from_probability(probability: float) -> int:
    """Mengubah probabilitas menjadi skala kemungkinan 1–5."""

    if probability <= 0.05:
        return 1
    if probability <= 0.20:
        return 2
    if probability <= 0.50:
        return 3
    if probability <= 0.80:
        return 4
    return 5


EDIR_RISK_SCORE = {
    (1, 1): 1, (2, 1): 5, (3, 1): 10,
    (4, 1): 15, (5, 1): 20,
    (1, 2): 2, (2, 2): 6, (3, 2): 11,
    (4, 2): 16, (5, 2): 21,
    (1, 3): 3, (2, 3): 8, (3, 3): 13,
    (4, 3): 18, (5, 3): 23,
    (1, 4): 4, (2, 4): 9, (3, 4): 14,
    (4, 4): 19, (5, 4): 24,
    (1, 5): 7, (2, 5): 12, (3, 5): 17,
    (4, 5): 22, (5, 5): 25,
}


def edir_risk_score(
    impact_score: int,
    likelihood_score: int,
) -> int:
    """Nilai risiko sesuai matriks ED 0012.E-2024."""

    return EDIR_RISK_SCORE[
        (int(impact_score), int(likelihood_score))
    ]


def edir_risk_level(score: int) -> str:
    """Mengubah nilai matriks menjadi level risiko."""

    if score <= 5:
        return "Low"
    if score <= 10:
        return "Low to Moderate"
    if score <= 15:
        return "Moderate"
    if score <= 19:
        return "Moderate to High"
    return "High"


def build_prime_risk_pdf(report_data: dict) -> bytes:
    """Membentuk laporan PDF multi-halaman dari hasil dashboard."""

    if not REPORTLAB_AVAILABLE:
        raise RuntimeError(
            "Paket reportlab belum terpasang."
        )

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=16 * mm,
        bottomMargin=15 * mm,
        title=report_data["title"],
        author=report_data["prepared_by"],
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PrimeTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=28,
        textColor=colors.HexColor("#12335B"),
        alignment=TA_LEFT,
        spaceAfter=9,
    )
    subtitle_style = ParagraphStyle(
        "PrimeSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#62748A"),
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "PrimeHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#12335B"),
        spaceBefore=4,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "PrimeBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#24364B"),
    )
    small_style = ParagraphStyle(
        "PrimeSmall",
        parent=body_style,
        fontSize=7.5,
        leading=10,
    )
    table_header_style = ParagraphStyle(
        "PrimeTableHeader",
        parent=small_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
        leading=9,
    )

    def page_header_footer(canvas, doc):
        canvas.saveState()
        page_width, page_height = landscape(A4)
        canvas.setStrokeColor(colors.HexColor("#D7E1EC"))
        canvas.line(
            14 * mm,
            page_height - 11 * mm,
            page_width - 14 * mm,
            page_height - 11 * mm,
        )
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.HexColor("#12335B"))
        canvas.drawString(
            14 * mm,
            page_height - 8 * mm,
            "PRIME-RISK | Primary Energy Risk Intelligence",
        )
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#62748A"))
        canvas.drawRightString(
            page_width - 14 * mm,
            8 * mm,
            f"Halaman {doc.page} | {APP_VERSION}",
        )
        canvas.restoreState()

    def styled_table(data, widths=None, header=True, font_size=7.5):
        wrapped = []
        for row_index, row in enumerate(data):
            wrapped.append(
                [
                    Paragraph(
                        str(value),
                        (
                            table_header_style
                            if header and row_index == 0
                            else small_style
                        ),
                    )
                    for value in row
                ]
            )
        table = Table(
            wrapped,
            colWidths=widths,
            repeatRows=1 if header else 0,
            hAlign="LEFT",
        )
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.35,
             colors.HexColor("#CAD7E6")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ]
        if header:
            commands.extend(
                [
                    ("BACKGROUND", (0, 0), (-1, 0),
                     colors.HexColor("#12335B")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0),
                     "Helvetica-Bold"),
                ]
            )
            if len(data) > 1:
                commands.append(
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [colors.white, colors.HexColor("#F3F7FB")])
                )
        table.setStyle(TableStyle(commands))
        return table

    story = []
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("PRIME-RISK", title_style))
    story.append(
        Paragraph(
            "Primary Energy Risk Intelligence, Modelling & Evaluation",
            heading_style,
        )
    )
    story.append(
        Paragraph(
            report_data["title"],
            subtitle_style,
        )
    )
    cover_data = [
        ["Parameter", "Keterangan"],
        ["Tanggal laporan", report_data["report_date"]],
        ["Disusun oleh", report_data["prepared_by"]],
        ["Filter tahun", report_data["filter_years"]],
        ["Filter unit", report_data["filter_units"]],
        ["Risk Limit aktif", report_data["risk_limit"]],
        ["Sumber data", "Google Sheet publik PRIME-RISK"],
    ]
    story.append(styled_table(cover_data, [52 * mm, 175 * mm]))
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            "Catatan: laporan ini merupakan keluaran model berbasis data "
            "historis dan skenario. Hasil prediksi bukan kepastian kejadian "
            "dan perlu divalidasi bersama pemilik risiko.",
            body_style,
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("1. Ringkasan Eksekutif", heading_style))
    summary_rows = [["Indikator", "Nilai"]]
    summary_rows.extend(report_data["summary_rows"])
    story.append(styled_table(summary_rows, [105 * mm, 95 * mm]))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("2. KRI dan Early Warning HOP", heading_style))
    kri_rows = report_data.get("kri_rows", [])
    if kri_rows:
        story.append(
            styled_table(
                [["Unit", "Tanggal", "HOP", "Status", "Tren 7"]]
                + kri_rows,
                [80 * mm, 34 * mm, 24 * mm, 32 * mm, 28 * mm],
            )
        )
    else:
        story.append(Paragraph("Data KRI tidak tersedia.", body_style))
    story.append(PageBreak())

    story.append(Paragraph("3. Analisis HOP dan Kejadian Loss", heading_style))
    hop_rows = report_data.get("hop_loss_rows", [])
    if hop_rows:
        story.append(
            styled_table(
                [["Status HOP", "Observasi", "Hari Loss", "Kejadian",
                  "Probabilitas", "Loss Opportunity"]]
                + hop_rows,
                [38 * mm, 30 * mm, 30 * mm, 28 * mm,
                 34 * mm, 50 * mm],
            )
        )
    else:
        story.append(Paragraph("Analisis HOP-Loss tidak tersedia.", body_style))
    story.append(Spacer(1, 7 * mm))

    story.append(Paragraph("4. Monte Carlo dan BETA-PERT", heading_style))
    monte_rows = report_data.get("monte_rows", [])
    if monte_rows:
        story.append(
            styled_table(
                [["Parameter", "Nilai"]] + monte_rows,
                [105 * mm, 95 * mm],
            )
        )
    else:
        story.append(Paragraph("Hasil Monte Carlo tidak tersedia.", body_style))
    story.append(PageBreak())

    story.append(Paragraph("5. Prediksi Risiko", heading_style))
    prediction_rows = report_data.get("prediction_rows", [])
    if prediction_rows:
        story.append(
            styled_table(
                [["Parameter", "Nilai"]] + prediction_rows,
                [105 * mm, 95 * mm],
            )
        )
        story.append(Spacer(1, 6 * mm))

        likelihood = report_data.get("prediction_likelihood")
        impact = report_data.get("prediction_impact")
        matrix = [
            [7, 12, 17, 22, 25],
            [4, 9, 14, 19, 24],
            [3, 8, 13, 18, 23],
            [2, 6, 11, 16, 21],
            [1, 5, 10, 15, 20],
        ]
        matrix_data = [["", "1", "2", "3", "4", "5"]]
        for row_number, values in enumerate(matrix):
            likelihood_score = 5 - row_number
            row_label = {5: "E", 4: "D", 3: "C", 2: "B", 1: "A"}[
                likelihood_score
            ]
            formatted_values = []
            for impact_score, value in enumerate(values, start=1):
                marker = (
                    " PRED"
                    if likelihood_score == likelihood
                    and impact_score == impact
                    else ""
                )
                formatted_values.append(f"{value}{marker}")
            matrix_data.append([row_label] + formatted_values)

        heatmap_table = Table(
            matrix_data,
            colWidths=[20 * mm] + [30 * mm] * 5,
            rowHeights=[10 * mm] * 6,
            hAlign="LEFT",
        )
        heatmap_commands = [
            ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#12335B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (0, -1),
             colors.HexColor("#12335B")),
            ("TEXTCOLOR", (0, 1), (0, -1), colors.white),
        ]
        for row_index, values in enumerate(matrix, start=1):
            for column_index, value in enumerate(values, start=1):
                if value <= 5:
                    fill = "#35B24A"
                elif value <= 10:
                    fill = "#8DCC74"
                elif value <= 15:
                    fill = "#FFE31A"
                elif value <= 19:
                    fill = "#F5A623"
                else:
                    fill = "#EF503B"
                heatmap_commands.append(
                    ("BACKGROUND", (column_index, row_index),
                     (column_index, row_index), colors.HexColor(fill))
                )
        heatmap_table.setStyle(TableStyle(heatmap_commands))
        story.append(heatmap_table)
        story.append(Spacer(1, 5 * mm))
        story.append(
            Paragraph(
                "Rekomendasi model: "
                + report_data.get("recommendation", "-"),
                body_style,
            )
        )
    else:
        story.append(Paragraph("Hasil prediksi tidak tersedia.", body_style))
    story.append(PageBreak())

    story.append(Paragraph("6. Profil Kategori Risiko", heading_style))
    category_rows = report_data.get("category_rows", [])
    if category_rows:
        story.append(
            styled_table(
                [["Kode", "Kategori", "Kejadian", "Total Loss",
                  "% Risk Limit", "K", "D", "Nilai", "Level"]]
                + category_rows,
                [18 * mm, 70 * mm, 22 * mm, 40 * mm, 27 * mm,
                 15 * mm, 15 * mm, 18 * mm, 35 * mm],
                font_size=6.8,
            )
        )
    else:
        story.append(Paragraph("Profil kategori tidak tersedia.", body_style))
    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph("7. Metodologi dan Batasan", heading_style))
    story.append(
        Paragraph(
            "Frekuensi Kejadian Loss dimodelkan menggunakan distribusi "
            "Poisson berdasarkan laju kejadian per unit-hari. Severity "
            "dimodelkan menggunakan BETA-PERT dengan parameter P10, P50, "
            "dan P90. Faktor kemungkinan menggunakan peluang minimal satu "
            "kejadian, sedangkan faktor dampak menggunakan P90 dibandingkan "
            "Risk Limit. Nilai risiko mengikuti matriks ED 0012.E-2024. "
            "Kualitas prediksi bergantung pada kelengkapan, konsistensi, "
            "dan representativitas data historis.",
            body_style,
        )
    )

    document.build(
        story,
        onFirstPage=page_header_footer,
        onLaterPages=page_header_footer,
    )
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


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
            parsed = pd.to_datetime(
                data[column],
                errors="coerce",
                dayfirst=True,
                format="mixed",
            )

            # Enam record PLTU Kendari pada sumber tertulis tahun 2000,
            # padahal urutan event dan baris di sekitarnya adalah Des-2025.
            # Koreksi defensif ini mencegah sumbu tren tertarik ke tahun 2000.
            year_2000 = parsed.dt.year.eq(2000)
            parsed.loc[year_2000] = (
                parsed.loc[year_2000] + pd.DateOffset(years=25)
            )

            data[column] = parsed

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


def prepare_loss_event_detail_v2(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Menyiapkan data event-level agar kompatibel dengan model v15.

    Sheet ``Loss_Event_Detail_v2`` merupakan sumber transaksi kejadian.
    Fungsi ini hanya membentuk kolom turunan dan status kesiapan; data
    sumber tidak diagregasikan dan tidak ditulis kembali ke Google Sheet.
    """

    data = data.copy()

    # Hilangkan baris kosong di bagian bawah sheet tanpa mengubah event.
    identity_columns = [
        column
        for column in [
            "Event_ID",
            "Start_DateTime",
            "Unit_Asli",
        ]
        if column in data.columns
    ]

    if identity_columns:
        data = data.loc[
            data[identity_columns].notna().any(axis=1)
        ].copy()

    for column in ["Start_DateTime", "End_DateTime"]:
        if column in data.columns:
            data[column] = pd.to_datetime(
                data[column],
                errors="coerce",
                dayfirst=True,
            )

    start_time = data.get(
        "Start_DateTime",
        pd.Series(pd.NaT, index=data.index),
    )

    # Kolom kalender selalu mengikuti waktu mulai kejadian.
    data["Tanggal_Mulai"] = start_time.dt.normalize()
    data["Tahun"] = start_time.dt.year.astype("Int64")
    data["Bulan"] = start_time.dt.month.map(MONTH_LABELS)

    # Pada v2 satu baris dimaksudkan sebagai satu entry loss event.
    # ID lama tetap dipakai jika tersedia; bila kosong gunakan Event_ID.
    existing_loss_id = data.get(
        LOSS_ID_COLUMN,
        pd.Series("", index=data.index, dtype="object"),
    ).fillna("").astype(str).str.strip()

    event_id = data.get(
        "Event_ID",
        pd.Series("", index=data.index, dtype="object"),
    ).fillna("").astype(str).str.strip()

    data[LOSS_ID_COLUMN] = existing_loss_id.mask(
        existing_loss_id.eq(""),
        event_id,
    )

    # Kolom kompatibilitas yang sebelumnya tersedia di Loss_Event_Model.
    data["Jenis_Kejadian_Loss"] = "EVENT"
    data["Jumlah_Segmen"] = 1

    if "Kategori_Final" not in data.columns:
        data["Kategori_Final"] = ""

    category = (
        data["Kategori_Final"]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    data["Kategori_Final"] = category.mask(
        category.eq(""),
        "Belum Diklasifikasikan",
    )

    if "Subkategori_Event" not in data.columns:
        data["Subkategori_Event"] = ""

    if "Permasalahan" in data.columns:
        subcategory = (
            data["Subkategori_Event"]
            .fillna("")
            .astype(str)
            .str.strip()
        )
        data["Subkategori_Event"] = subcategory.mask(
            subcategory.eq(""),
            data["Permasalahan"],
        )

    required_for_model = [
        LOSS_ID_COLUMN,
        "Start_DateTime",
        "HOP_Unit_Key",
        "Loss_Production_MWh",
        "Loss_Opportunity_Rp",
    ]

    complete = pd.Series(True, index=data.index)
    for column in required_for_model:
        if column not in data.columns:
            complete &= False
        elif column in [
            "Loss_Production_MWh",
            "Loss_Opportunity_Rp",
        ]:
            numeric_value = pd.to_numeric(
                data[column],
                errors="coerce",
            )
            complete &= numeric_value.notna() & numeric_value.ge(0)
        else:
            complete &= data[column].notna()
            if data[column].dtype == "object":
                complete &= data[column].astype(str).str.strip().ne("")

    data["Kesiapan_Model"] = np.where(
        complete,
        "READY - EVENT DETAIL V2",
        "REVIEW - DATA BELUM LENGKAP",
    )
    data["Penggunaan_Model"] = np.where(
        complete,
        "FREQUENCY_SEVERITY",
        "TIDAK DIGUNAKAN",
    )

    return data


@st.cache_data(ttl=600, show_spinner=False)
def load_all_data():
    """Membaca dan membersihkan data Kejadian Loss dan HOP."""

    loss = load_google_sheet(SHEET_LOSS)
    hop = load_google_sheet(SHEET_HOP)
    parameter = load_google_sheet(SHEET_PARAMETER)
    mapping = load_google_sheet(SHEET_MAPPING)

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

    if SHEET_LOSS == "Loss_Event_Detail_v2":
        loss = prepare_loss_event_detail_v2(loss)

        # Regional pada sebagian event SUMKAL masih kosong di tab v2.
        # Isi hanya nilai kosong dengan referensi resmi Mapping_Unit.
        if {
            "Unit_Asli",
            "Regional",
        }.issubset(mapping.columns):
            unit_region = (
                mapping.dropna(subset=["Unit_Asli", "Regional"])
                .drop_duplicates(subset=["Unit_Asli"])
                .set_index("Unit_Asli")["Regional"]
            )
            source_region = loss["Unit_Asli"].map(unit_region)
            current_region = (
                loss["Regional"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
            loss["Regional"] = current_region.mask(
                current_region.eq(""),
                source_region,
            )

            # Fallback kedua untuk variasi penulisan Unit_Asli yang belum
            # persis sama, menggunakan HOP_Unit_Key yang sudah dipetakan.
            if "HOP_Unit_Key" in mapping.columns:
                key_region = (
                    mapping.dropna(
                        subset=["HOP_Unit_Key", "Regional"]
                    )
                    .drop_duplicates(subset=["HOP_Unit_Key"])
                    .set_index("HOP_Unit_Key")["Regional"]
                )
                remaining_region = (
                    loss["Regional"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )
                loss["Regional"] = remaining_region.mask(
                    remaining_region.eq(""),
                    loss["HOP_Unit_Key"].map(key_region),
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

    # Loss_Event_Detail_v2 tidak wajib menyimpan Batas_HOP_P20.
    # Jika kolom tersebut tidak tersedia, turunkan parameter P20
    # langsung dari seluruh observasi HOP harian per unit. Dengan
    # demikian tab KRI, Analisis HOP-Loss, dan laporan tetap kompatibel.
    if {
        "HOP_Unit_Key",
        "Nilai_HOP",
    }.issubset(hop.columns):
        hop_threshold = (
            hop.dropna(
                subset=[
                    "HOP_Unit_Key",
                    "Nilai_HOP",
                ]
            )
            .groupby("HOP_Unit_Key")["Nilai_HOP"]
            .quantile(0.20)
        )

        mapped_threshold = loss["HOP_Unit_Key"].map(
            hop_threshold
        )

        if "Batas_HOP_P20" not in loss.columns:
            loss["Batas_HOP_P20"] = mapped_threshold
        else:
            loss["Batas_HOP_P20"] = pd.to_numeric(
                loss["Batas_HOP_P20"],
                errors="coerce",
            ).fillna(mapped_threshold)

    return loss, hop, parameter


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
        loss_data, hop_data, parameter_data = load_all_data()

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
default_readiness = []

if "Kesiapan_Model" in loss_data.columns:
    readiness_options = sorted(
        loss_data["Kesiapan_Model"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    # Secara default, perhitungan hanya memakai record yang lolos
    # pemeriksaan minimum. Record REVIEW tetap dapat dipilih untuk audit.
    default_readiness = [
        value
        for value in readiness_options
        if str(value).upper().startswith("READY")
    ]

    if not default_readiness:
        default_readiness = readiness_options

selected_readiness = st.sidebar.multiselect(
    "Kesiapan model",
    options=readiness_options,
    default=default_readiness,
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
    "PRIME-RISK"
)

st.subheader(
    "Primary Energy Risk Intelligence, Modelling & Evaluation"
)

st.caption(
    "Model prediktif risiko hambatan energi primer "
    "batubara berbasis HOP, Kejadian Loss, asosiasi "
    "statistik, BETA-PERT, Monte Carlo, probability "
    "of exceedance, dan risk heat map."
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

# Penampung hasil antar-tab untuk laporan PDF.
report_monte_carlo = {}
report_prediction = {}
report_category_risk = pd.DataFrame()


# ============================================================
# TAB DASHBOARD
# ============================================================

(
    tab_summary,
    tab_kri,
    tab_hop_loss,
    tab_monte_carlo,
    tab_prediction,
    tab_heatmap,
    tab_validation,
    tab_loss,
    tab_hop,
    tab_quality,
    tab_method,
    tab_report,
) = st.tabs(
    [
        "Ringkasan",
        "KRI & Early Warning",
        "Analisis HOP–Loss",
        "Monte Carlo & BETA-PERT",
        "Prediksi Risiko",
        "Risk Heat Map",
        "Validasi Model",
        "Kejadian Loss",
        "HOP Harian",
        "Kualitas Data",
        "Metodologi",
        "Laporan PDF",
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
        # Pada Loss_Event_Detail_v2, Kategori_Final masih kosong untuk
        # seluruh record. Untuk ringkasan operasional gunakan subkategori
        # event yang memang tersedia, sehingga grafik tidak menjadi satu
        # batang besar "Belum Diklasifikasikan".
        summary_category_column = (
            "Subkategori_Event"
            if (
                SHEET_LOSS == "Loss_Event_Detail_v2"
                and "Subkategori_Event" in filtered.columns
            )
            else "Kategori_Final"
        )

        category_source = filtered.copy()
        category_source[summary_category_column] = (
            category_source[summary_category_column]
            .fillna("Belum Diklasifikasikan")
            .astype(str)
            .str.strip()
            .replace("", "Belum Diklasifikasikan")
        )

        category_summary = (
            category_source
            .groupby(
                summary_category_column,
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
            .tail(15)
        )

        figure_category = px.bar(
            category_summary,
            x="Loss_Opportunity_Rp",
            y=summary_category_column,
            orientation="h",
            title=(
                "Top 15 Loss Opportunity per Subkategori"
                if summary_category_column == "Subkategori_Event"
                else "Loss Opportunity per Kategori"
            ),
            labels={
                "Kategori_Final": "Kategori",
                "Subkategori_Event": "Subkategori Event",
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
# TAB KRI DAN EARLY WARNING
# ============================================================

with tab_kri:
    st.subheader(
        "KRI & Early Warning Hambatan Energi Primer"
    )

    st.caption(
        "Pemantauan kondisi HOP terakhir setiap unit, "
        "deviasi terhadap batas P20, tren tujuh observasi, "
        "dan durasi HOP rendah berturut-turut."
    )

    kri_hop = filtered_hop[
        [
            "Tanggal",
            "HOP_Unit_Key",
            "Nilai_HOP",
        ]
    ].copy()

    kri_hop = kri_hop.dropna(
        subset=[
            "Tanggal",
            "HOP_Unit_Key",
            "Nilai_HOP",
        ]
    ).sort_values(
        [
            "HOP_Unit_Key",
            "Tanggal",
        ]
    )

    kri_threshold = (
        loss_data[
            [
                "HOP_Unit_Key",
                "Batas_HOP_P20",
            ]
        ]
        .dropna()
        .groupby(
            "HOP_Unit_Key",
            as_index=False,
        )
        .agg(
            Batas_HOP_P20=(
                "Batas_HOP_P20",
                "median",
            )
        )
    )

    kri_hop = kri_hop.merge(
        kri_threshold,
        on="HOP_Unit_Key",
        how="left",
    )

    kri_rows = []

    for unit_name, unit_data in kri_hop.groupby(
        "HOP_Unit_Key"
    ):
        unit_data = unit_data.sort_values(
            "Tanggal"
        ).reset_index(drop=True)

        latest_row = unit_data.iloc[-1]
        latest_hop = float(latest_row["Nilai_HOP"])
        threshold_value = latest_row["Batas_HOP_P20"]

        trend_7 = np.nan
        if len(unit_data) >= 8:
            trend_7 = (
                latest_hop
                - float(unit_data.iloc[-8]["Nilai_HOP"])
            )

        consecutive_low_days = 0
        if pd.notna(threshold_value):
            low_flags = (
                unit_data["Nilai_HOP"]
                <= unit_data["Batas_HOP_P20"]
            )

            for is_low in reversed(
                low_flags.fillna(False).tolist()
            ):
                if is_low:
                    consecutive_low_days += 1
                else:
                    break

        deviation = (
            latest_hop - float(threshold_value)
            if pd.notna(threshold_value)
            else np.nan
        )

        if latest_hop < 10:
            status_kri = "EMERGENCY"
            status_reason = "HOP terakhir < 10 hari"
        elif latest_hop <= 15:
            status_kri = "SIAGA"
            status_reason = (
                "HOP terakhir ≥ 10 dan ≤ 15 hari"
            )
        else:
            status_kri = "NORMAL"
            status_reason = "HOP terakhir > 15 hari"

        kri_rows.append(
            {
                "HOP_Unit_Key": unit_name,
                "Tanggal_Terakhir": latest_row["Tanggal"],
                "HOP_Terakhir": latest_hop,
                "Batas_HOP_P20": threshold_value,
                "Deviasi_dari_P20": deviation,
                "Tren_7_Observasi": trend_7,
                "Durasi_HOP_Rendah": consecutive_low_days,
                "Status_KRI": status_kri,
                "Dasar_Status": status_reason,
            }
        )

    kri_unit = pd.DataFrame(kri_rows)

    if kri_unit.empty:
        st.warning(
            "Data HOP belum tersedia untuk membentuk KRI."
        )
    else:
        kri_status_order = [
            "EMERGENCY",
            "SIAGA",
            "NORMAL",
        ]

        kri_status_colors = {
            "EMERGENCY": "#DC2626",
            "SIAGA": "#FACC15",
            "NORMAL": "#16A34A",
        }

        kri_counts = (
            kri_unit["Status_KRI"]
            .value_counts()
            .reindex(
                kri_status_order,
                fill_value=0,
            )
        )

        kri_metrics = st.columns(3)
        for index, status_name in enumerate(
            kri_status_order
        ):
            kri_metrics[index].metric(
                f"Unit {status_name.title()}",
                format_number(
                    kri_counts[status_name]
                ),
            )

        kri_chart_col1, kri_chart_col2 = st.columns(
            [1, 2]
        )

        with kri_chart_col1:
            status_chart_data = (
                kri_counts
                .rename_axis("Status_KRI")
                .reset_index(name="Jumlah_Unit")
            )
            status_chart_data = status_chart_data[
                status_chart_data["Jumlah_Unit"] > 0
            ]

            kri_status_chart = px.pie(
                status_chart_data,
                names="Status_KRI",
                values="Jumlah_Unit",
                hole=0.55,
                title="Komposisi Status KRI Unit",
                color="Status_KRI",
                color_discrete_map=kri_status_colors,
            )
            kri_status_chart.update_traces(
                textinfo="label+value"
            )
            kri_status_chart.update_layout(
                height=440,
                showlegend=False,
            )
            st.plotly_chart(
                kri_status_chart,
                use_container_width=True,
                theme="streamlit",
            )

        with kri_chart_col2:
            kri_bar_data = kri_unit.melt(
                id_vars=[
                    "HOP_Unit_Key",
                    "Status_KRI",
                ],
                value_vars=[
                    "HOP_Terakhir",
                    "Batas_HOP_P20",
                ],
                var_name="Indikator",
                value_name="HOP",
            ).dropna(subset=["HOP"])

            kri_bar_chart = px.bar(
                kri_bar_data,
                x="HOP_Unit_Key",
                y="HOP",
                color="Indikator",
                barmode="group",
                title=(
                    "HOP Terakhir dibandingkan Batas P20"
                ),
                labels={
                    "HOP_Unit_Key": "Unit",
                    "HOP": "HOP (hari)",
                    "Indikator": "Indikator",
                },
                color_discrete_map={
                    "HOP_Terakhir": "#0F6CBD",
                    "Batas_HOP_P20": "#F59E0B",
                },
            )
            kri_bar_chart.update_xaxes(
                tickangle=-45
            )
            kri_bar_chart.update_layout(
                height=440,
                margin=dict(
                    l=20,
                    r=20,
                    t=70,
                    b=130,
                ),
            )
            st.plotly_chart(
                kri_bar_chart,
                use_container_width=True,
                theme="streamlit",
            )

        kri_unit["Prioritas"] = (
            kri_unit["Status_KRI"]
            .map(
                {
                    "EMERGENCY": 1,
                    "SIAGA": 2,
                    "NORMAL": 3,
                }
            )
        )
        kri_unit = kri_unit.sort_values(
            [
                "Prioritas",
                "Deviasi_dari_P20",
            ]
        ).drop(columns="Prioritas")

        st.dataframe(
            kri_unit,
            use_container_width=True,
            hide_index=True,
            height=520,
            column_config={
                "Tanggal_Terakhir": (
                    st.column_config.DateColumn(
                        "Tanggal Terakhir",
                        format="DD-MMM-YYYY",
                    )
                ),
                "HOP_Terakhir": (
                    st.column_config.NumberColumn(
                        "HOP Terakhir",
                        format="%.2f",
                    )
                ),
                "Batas_HOP_P20": (
                    st.column_config.NumberColumn(
                        "Batas P20",
                        format="%.2f",
                    )
                ),
                "Deviasi_dari_P20": (
                    st.column_config.NumberColumn(
                        "Deviasi dari P20",
                        format="%.2f",
                    )
                ),
                "Tren_7_Observasi": (
                    st.column_config.NumberColumn(
                        "Tren 7 Observasi",
                        format="%+.2f",
                    )
                ),
                "Durasi_HOP_Rendah": (
                    st.column_config.NumberColumn(
                        "Durasi HOP Rendah",
                        format="%d",
                    )
                ),
            },
        )

        st.warning(
            "Status KRI menggunakan batas HOP tetap: "
            "Emergency/Merah untuk HOP < 10 hari; "
            "Siaga/Kuning untuk HOP ≥ 10 sampai dengan "
            "15 hari; dan Normal/Hijau untuk HOP > 15 hari. "
            "Batas P20 tetap ditampilkan sebagai indikator "
            "analitis tambahan."
        )

# ============================================================
# TAB ANALISIS HOP–LOSS
# ============================================================

with tab_hop_loss:
    st.subheader(
        "Analisis Hubungan HOP dan Kejadian Loss"
    )

    st.caption(
        "Analisis membandingkan kemungkinan terjadinya "
        "Kejadian Loss pada kondisi HOP rendah dan normal."
    )

    # --------------------------------------------------------
    # MENYIAPKAN BATAS HOP PER UNIT
    # --------------------------------------------------------

    threshold_source = loss_data[
        [
            "HOP_Unit_Key",
            "Batas_HOP_P20",
        ]
    ].copy()

    threshold_source = threshold_source.dropna(
        subset=[
            "HOP_Unit_Key",
            "Batas_HOP_P20",
        ]
    )

    threshold_by_unit = (
        threshold_source
        .groupby(
            "HOP_Unit_Key",
            as_index=False,
        )
        .agg(
            Batas_HOP_P20=(
                "Batas_HOP_P20",
                "median",
            )
        )
    )

    # --------------------------------------------------------
    # MENYIAPKAN DATA HOP HARIAN
    # --------------------------------------------------------

    hop_analysis = filtered_hop[
        [
            "Tanggal",
            "HOP_Unit_Key",
            "Nilai_HOP",
        ]
    ].copy()

    hop_analysis = hop_analysis.dropna(
        subset=[
            "Tanggal",
            "HOP_Unit_Key",
            "Nilai_HOP",
        ]
    )

    hop_analysis["Tanggal"] = (
        pd.to_datetime(
            hop_analysis["Tanggal"],
            errors="coerce",
        )
        .dt.normalize()
    )

    hop_analysis = (
        hop_analysis
        .groupby(
            [
                "Tanggal",
                "HOP_Unit_Key",
            ],
            as_index=False,
        )
        .agg(
            Nilai_HOP=(
                "Nilai_HOP",
                "mean",
            )
        )
    )

    hop_analysis = hop_analysis.merge(
        threshold_by_unit,
        on="HOP_Unit_Key",
        how="left",
    )

    hop_analysis = hop_analysis.dropna(
        subset=["Batas_HOP_P20"]
    )

    hop_analysis["Status_HOP_Analisis"] = (
        "NORMAL"
    )

    hop_analysis.loc[
        hop_analysis["Nilai_HOP"]
        <= hop_analysis["Batas_HOP_P20"],
        "Status_HOP_Analisis",
    ] = "RENDAH"

    # --------------------------------------------------------
    # MENYIAPKAN KEJADIAN LOSS PER UNIT PER HARI
    # --------------------------------------------------------

    event_daily = filtered[
        [
            LOSS_ID_COLUMN,
            "HOP_Unit_Key",
            "Start_DateTime",
            "Loss_Production_MWh",
            "Loss_Opportunity_Rp",
        ]
    ].copy()

    event_daily = event_daily.dropna(
        subset=[
            LOSS_ID_COLUMN,
            "HOP_Unit_Key",
            "Start_DateTime",
        ]
    )

    event_daily["Tanggal"] = (
        pd.to_datetime(
            event_daily["Start_DateTime"],
            errors="coerce",
        )
        .dt.normalize()
    )

    event_daily = (
        event_daily
        .groupby(
            [
                "Tanggal",
                "HOP_Unit_Key",
            ],
            as_index=False,
        )
        .agg(
            Jumlah_Kejadian_Loss=(
                LOSS_ID_COLUMN,
                "nunique",
            ),
            Loss_Production_MWh=(
                "Loss_Production_MWh",
                "sum",
            ),
            Loss_Opportunity_Rp=(
                "Loss_Opportunity_Rp",
                "sum",
            ),
        )
    )

    # --------------------------------------------------------
    # MENGGABUNGKAN HOP DAN KEJADIAN LOSS
    # --------------------------------------------------------

    hop_loss_daily = hop_analysis.merge(
        event_daily,
        on=[
            "Tanggal",
            "HOP_Unit_Key",
        ],
        how="left",
    )

    fill_zero_columns = [
        "Jumlah_Kejadian_Loss",
        "Loss_Production_MWh",
        "Loss_Opportunity_Rp",
    ]

    for column in fill_zero_columns:
        hop_loss_daily[column] = (
            hop_loss_daily[column]
            .fillna(0)
        )

    hop_loss_daily["Ada_Kejadian_Loss"] = (
        hop_loss_daily[
            "Jumlah_Kejadian_Loss"
        ] > 0
    )

    # --------------------------------------------------------
    # RINGKASAN HOP RENDAH VS NORMAL
    # --------------------------------------------------------

    hop_loss_summary = (
        hop_loss_daily
        .groupby(
            "Status_HOP_Analisis",
            as_index=False,
        )
        .agg(
            Observasi_Hari=(
                "Tanggal",
                "count",
            ),
            Hari_Dengan_Loss=(
                "Ada_Kejadian_Loss",
                "sum",
            ),
            Jumlah_Kejadian_Loss=(
                "Jumlah_Kejadian_Loss",
                "sum",
            ),
            Total_Loss_Production_MWh=(
                "Loss_Production_MWh",
                "sum",
            ),
            Total_Loss_Opportunity_Rp=(
                "Loss_Opportunity_Rp",
                "sum",
            ),
        )
    )

    hop_loss_summary[
        "Probabilitas_Loss"
    ] = (
        hop_loss_summary[
            "Hari_Dengan_Loss"
        ]
        / hop_loss_summary[
            "Observasi_Hari"
        ]
    )

    hop_loss_summary[
        "Frekuensi_per_100_Hari"
    ] = (
        hop_loss_summary[
            "Jumlah_Kejadian_Loss"
        ]
        / hop_loss_summary[
            "Observasi_Hari"
        ]
        * 100
    )

    # --------------------------------------------------------
    # NILAI KPI
    # --------------------------------------------------------

    low_row = hop_loss_summary[
        hop_loss_summary[
            "Status_HOP_Analisis"
        ] == "RENDAH"
    ]

    normal_row = hop_loss_summary[
        hop_loss_summary[
            "Status_HOP_Analisis"
        ] == "NORMAL"
    ]

    probability_low = (
        low_row["Probabilitas_Loss"].iloc[0]
        if not low_row.empty
        else 0
    )

    probability_normal = (
        normal_row["Probabilitas_Loss"].iloc[0]
        if not normal_row.empty
        else 0
    )

    low_loss_events = (
        low_row[
            "Jumlah_Kejadian_Loss"
        ].iloc[0]
        if not low_row.empty
        else 0
    )

    normal_loss_events = (
        normal_row[
            "Jumlah_Kejadian_Loss"
        ].iloc[0]
        if not normal_row.empty
        else 0
    )

    low_observations = (
        int(low_row["Observasi_Hari"].iloc[0])
        if not low_row.empty
        else 0
    )

    normal_observations = (
        int(normal_row["Observasi_Hari"].iloc[0])
        if not normal_row.empty
        else 0
    )

    low_loss_days = (
        int(low_row["Hari_Dengan_Loss"].iloc[0])
        if not low_row.empty
        else 0
    )

    normal_loss_days = (
        int(normal_row["Hari_Dengan_Loss"].iloc[0])
        if not normal_row.empty
        else 0
    )

    if probability_normal > 0:
        relative_risk = (
            probability_low
            / probability_normal
        )
    else:
        relative_risk = None

    rr_ci_low = None
    rr_ci_high = None

    if (
        relative_risk is not None
        and relative_risk > 0
        and low_loss_days > 0
        and normal_loss_days > 0
        and low_observations > 0
        and normal_observations > 0
    ):
        rr_standard_error = math.sqrt(
            (1 / low_loss_days)
            - (1 / low_observations)
            + (1 / normal_loss_days)
            - (1 / normal_observations)
        )

        rr_ci_low = math.exp(
            math.log(relative_risk)
            - 1.96 * rr_standard_error
        )

        rr_ci_high = math.exp(
            math.log(relative_risk)
            + 1.96 * rr_standard_error
        )

    association_significant = (
        rr_ci_low is not None
        and rr_ci_low > 1
    )

    (
        analysis_kpi1,
        analysis_kpi2,
        analysis_kpi3,
        analysis_kpi4,
        analysis_kpi5,
    ) = (
        st.columns(5)
    )

    analysis_kpi1.metric(
        "Probabilitas Loss saat HOP Rendah",
        f"{probability_low:.2%}",
        help=(
            "Persentase hari dengan Kejadian Loss "
            "ketika nilai HOP berada pada atau "
            "di bawah batas P20."
        ),
    )

    analysis_kpi2.metric(
        "Probabilitas Loss saat HOP Normal",
        f"{probability_normal:.2%}",
        help=(
            "Persentase hari dengan Kejadian Loss "
            "ketika nilai HOP berada di atas "
            "batas P20."
        ),
    )

    analysis_kpi3.metric(
        "Relative Risk HOP Rendah",
        (
            f"{relative_risk:.2f}x"
            if relative_risk is not None
            else "-"
        ),
        help=(
            "Perbandingan probabilitas loss pada "
            "HOP rendah terhadap HOP normal."
        ),
    )

    analysis_kpi4.metric(
        "Kejadian dengan Data HOP",
        format_number(
            low_loss_events
            + normal_loss_events
        ),
        help=(
            "Jumlah Kejadian Loss yang berhasil "
            "dipasangkan dengan observasi HOP harian."
        ),
    )

    analysis_kpi5.metric(
        "95% CI Relative Risk",
        (
            f"{rr_ci_low:.2f}–{rr_ci_high:.2f}x"
            if (
                rr_ci_low is not None
                and rr_ci_high is not None
            )
            else "-"
        ),
        help=(
            "Rentang estimasi Relative Risk dengan "
            "tingkat keyakinan 95%. Jika seluruh "
            "rentang berada di atas 1, asosiasi "
            "dinilai signifikan secara statistik."
        ),
    )

    # --------------------------------------------------------
    # NARASI OTOMATIS
    # --------------------------------------------------------

    if relative_risk is None:
        st.info(
            "Relative Risk belum dapat dihitung karena "
            "tidak terdapat Kejadian Loss pada kelompok "
            "HOP normal atau data pembanding belum cukup."
        )

    elif relative_risk > 1:
        if association_significant:
            st.warning(
                f"Kejadian Loss tercatat sekitar "
                f"{relative_risk:.2f} kali lebih mungkin "
                f"pada kondisi HOP rendah dibandingkan "
                f"HOP normal (95% CI "
                f"{rr_ci_low:.2f}–{rr_ci_high:.2f}). "
                f"Rentang confidence interval seluruhnya "
                f"berada di atas 1 sehingga asosiasi ini "
                f"signifikan secara statistik. Hasil ini "
                f"tetap menunjukkan asosiasi dan belum "
                f"membuktikan hubungan sebab-akibat."
            )
        else:
            ci_text = (
                f" (95% CI {rr_ci_low:.2f}–"
                f"{rr_ci_high:.2f})"
                if (
                    rr_ci_low is not None
                    and rr_ci_high is not None
                )
                else ""
            )

            st.warning(
                f"Indikasi awal menunjukkan bahwa kemungkinan "
                f"Kejadian Loss pada kondisi HOP rendah sekitar "
                f"{relative_risk:.2f} kali dibandingkan kondisi "
                f"HOP normal{ci_text}. Karena confidence "
                f"interval masih menyentuh atau melewati 1, "
                f"asosiasi belum signifikan secara statistik "
                f"dan masih memerlukan tambahan data."
            )

    elif relative_risk < 1:
        st.info(
            f"Pada data terfilter, kemungkinan Kejadian Loss "
            f"saat HOP rendah tercatat sekitar "
            f"{relative_risk:.2f} kali dibandingkan kondisi "
            f"HOP normal. Hasil ini belum menunjukkan "
            f"peningkatan risiko pada HOP rendah dan perlu "
            f"ditinjau terhadap kelengkapan data."
        )

    else:
        st.info(
            "Probabilitas Kejadian Loss pada kondisi HOP "
            "rendah dan normal tercatat relatif sama."
        )

    # --------------------------------------------------------
    # GRAFIK
    # --------------------------------------------------------

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        probability_chart = px.bar(
            hop_loss_summary,
            x="Status_HOP_Analisis",
            y="Probabilitas_Loss",
            color="Status_HOP_Analisis",
            title=(
                "Probabilitas Kejadian Loss "
                "berdasarkan Status HOP"
            ),
            labels={
                "Status_HOP_Analisis": (
                    "Status HOP"
                ),
                "Probabilitas_Loss": (
                    "Probabilitas Kejadian Loss"
                ),
            },
            color_discrete_map={
                "RENDAH": "#DC2626",
                "NORMAL": "#16A34A",
            },
            text_auto=".2%",
        )

        probability_chart.update_yaxes(
            tickformat=".1%",
        )

        probability_chart.update_layout(
            showlegend=False,
            height=430,
        )

        st.plotly_chart(
            probability_chart,
            use_container_width=True,
        )

    with chart_col2:
        frequency_chart = px.bar(
            hop_loss_summary,
            x="Status_HOP_Analisis",
            y="Frekuensi_per_100_Hari",
            color="Status_HOP_Analisis",
            title=(
                "Frekuensi Kejadian Loss "
                "per 100 Hari Observasi"
            ),
            labels={
                "Status_HOP_Analisis": (
                    "Status HOP"
                ),
                "Frekuensi_per_100_Hari": (
                    "Kejadian per 100 Hari"
                ),
            },
            color_discrete_map={
                "RENDAH": "#DC2626",
                "NORMAL": "#16A34A",
            },
            text_auto=".2f",
        )

        frequency_chart.update_layout(
            showlegend=False,
            height=430,
        )

        st.plotly_chart(
            frequency_chart,
            use_container_width=True,
        )

    # --------------------------------------------------------
    # TABEL RINGKASAN
    # --------------------------------------------------------

    st.subheader(
        "Ringkasan Perbandingan HOP"
    )

    st.dataframe(
        hop_loss_summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status_HOP_Analisis": (
                st.column_config.TextColumn(
                    "Status HOP"
                )
            ),
            "Observasi_Hari": (
                st.column_config.NumberColumn(
                    "Observasi Unit-Hari",
                    format="%d",
                )
            ),
            "Hari_Dengan_Loss": (
                st.column_config.NumberColumn(
                    "Hari dengan Loss",
                    format="%d",
                )
            ),
            "Jumlah_Kejadian_Loss": (
                st.column_config.NumberColumn(
                    "Jumlah Kejadian Loss",
                    format="%d",
                )
            ),
            "Probabilitas_Loss": (
                st.column_config.NumberColumn(
                    "Probabilitas Loss",
                    format="%.2f%%",
                )
            ),
            "Frekuensi_per_100_Hari": (
                st.column_config.NumberColumn(
                    "Kejadian per 100 Hari",
                    format="%.2f",
                )
            ),
            "Total_Loss_Production_MWh": (
                st.column_config.NumberColumn(
                    "Loss Production MWh",
                    format="%.3f",
                )
            ),
            "Total_Loss_Opportunity_Rp": (
                st.column_config.NumberColumn(
                    "Loss Opportunity Rp",
                    format="Rp %,.0f",
                )
            ),
        },
    )

    # --------------------------------------------------------
    # CATATAN INTERPRETASI
    # --------------------------------------------------------

    with st.expander(
        "Cara membaca Analisis HOP–Loss"
    ):
        st.markdown(
            """
- **Probabilitas Loss** adalah proporsi observasi
  unit-hari yang memiliki minimal satu Kejadian Loss.
- **Frekuensi per 100 hari** menunjukkan perkiraan
  jumlah Kejadian Loss dalam setiap 100 unit-hari.
- **Relative Risk lebih dari 1** menunjukkan Kejadian
  Loss relatif lebih mungkin terjadi saat HOP rendah.
- **Relative Risk sama dengan 1** menunjukkan tingkat
  kemungkinan yang relatif sama.
- **Relative Risk kurang dari 1** menunjukkan data
  aktual belum memperlihatkan kenaikan kemungkinan
  loss pada kondisi HOP rendah.
- **95% Confidence Interval (CI)** menunjukkan rentang
  ketidakpastian Relative Risk. Jika seluruh rentang
  berada di atas 1, asosiasi dinilai signifikan secara
  statistik pada tingkat keyakinan 95%.
- Hasil ini menunjukkan hubungan statistik awal dan
  belum otomatis membuktikan hubungan sebab-akibat.
"""
        )


# ============================================================
# TAB MONTE CARLO DAN BETA-PERT
# ============================================================

with tab_monte_carlo:
    st.subheader(
        "Simulasi Monte Carlo Annual Loss"
    )

    st.caption(
        "Frekuensi kejadian disimulasikan dengan distribusi "
        "Poisson berdasarkan laju kejadian per unit-hari. "
        "Dampak setiap kejadian disimulasikan menggunakan "
        "distribusi BETA-PERT."
    )

    # --------------------------------------------------------
    # RISK LIMIT DINAMIS                    
    # --------------------------------------------------------

    parameter_risk_limit_rp = 0.0

    if {
        "Parameter",
        "Nilai",
    }.issubset(parameter_data.columns):
        parameter_name = (
            parameter_data["Parameter"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
        )
        parameter_value = pd.to_numeric(
            parameter_data.loc[
                parameter_name.eq(
                    "risk limit korporat"
                ),
                "Nilai",
            ],
            errors="coerce",
        ).dropna()

        parameter_value = parameter_value[
            parameter_value > 0
        ]

        if not parameter_value.empty:
            parameter_risk_limit_rp = float(
                parameter_value.iloc[0]
            )

    if parameter_risk_limit_rp <= 0:
        st.error(
            "Risk Limit Korporat pada Parameter_Model belum "
            "tersedia atau nilainya tidak valid."
        )
        st.stop()

    # Risk Limit hanya berasal dari source file. Tidak ada input
    # manual agar satuan dan hasil simulasi selalu konsisten.
    risk_limit_rp = parameter_risk_limit_rp
    risk_limit_miliar = risk_limit_rp / 1_000_000_000

    with st.expander(
        "⚙️ Parameter Risk Limit",
        expanded=False,
    ):
        st.caption(
            "Risk Limit menggunakan nilai "
            "Parameter_Model!B2 pada source file: "
            f"{format_compact_rupiah(risk_limit_rp)} "
            f"({risk_limit_miliar:,.2f} Rp miliar)."
        )

        exceedance_percent = st.slider(
            "Batas Probability of Exceedance "
            "(% Risk Limit)",
            min_value=5,
            max_value=100,
            value=20,
            step=5,
            help=(
                "Peluang dihitung terhadap annual loss "
                "yang melampaui persentase Risk Limit ini."
            ),
            key="risk_limit_exceedance_percent",
        )

        exceedance_ratio = exceedance_percent / 100
        exceedance_limit_rp = (
            risk_limit_rp * exceedance_ratio
        )

        risk_limit_col1, risk_limit_col2 = st.columns(2)

        risk_limit_col1.metric(
            "Risk Limit Aktif",
            format_compact_rupiah(risk_limit_rp),
        )
        risk_limit_col2.metric(
            "Batas Exceedance Aktif",
            format_compact_rupiah(exceedance_limit_rp),
            help=f"{exceedance_percent}% dari Risk Limit",
        )

    simulation_col1, simulation_col2 = st.columns(2)

    with simulation_col1:
        simulation_iterations = st.number_input(
            "Jumlah iterasi",
            min_value=1_000,
            max_value=100_000,
            value=10_000,
            step=1_000,
            help=(
                "Semakin banyak iterasi, hasil semakin stabil "
                "tetapi waktu proses menjadi lebih panjang."
            ),
        )

    with simulation_col2:
        random_seed = st.number_input(
            "Random seed",
            min_value=0,
            max_value=999_999,
            value=2026,
            step=1,
            help=(
                "Gunakan nilai yang sama agar hasil simulasi "
                "dapat direproduksi."
            ),
        )

    severity_source = filtered.copy()

    if "Start_DateTime" in severity_source.columns:
        severity_source = severity_source.dropna(
            subset=["Start_DateTime"]
        )

    severity_values = (
        severity_source["Loss_Opportunity_Rp"]
        .dropna()
        .astype(float)
    )

    severity_values = severity_values[
        severity_values > 0
    ]

    run_monte_carlo = st.button(
        "Jalankan / perbarui simulasi Monte Carlo",
        type="primary",
        key="run_monte_carlo",
        help=(
            "Simulasi dijalankan hanya saat tombol ditekan agar "
            "dashboard tetap cepat dibuka ketika jumlah event besar."
        ),
    )

    if not run_monte_carlo:
        st.info(
            "Parameter siap. Tekan tombol **Jalankan / perbarui "
            "simulasi Monte Carlo** untuk menghitung hasil. "
            "Perhitungan sengaja tidak dijalankan otomatis saat "
            "dashboard dibuka agar halaman tidak berhenti pada layar putih."
        )

    elif (
        hop_loss_daily.empty
        or len(severity_values) < 3
    ):
        st.warning(
            "Simulasi belum dapat dijalankan. Diperlukan "
            "data HOP unit-hari dan minimal tiga Kejadian "
            "Loss dengan nilai Loss Opportunity positif."
        )

    else:
        # Parameter BETA-PERT menggunakan P10, P50, dan P90
        # agar estimasi tidak terlalu dipengaruhi nilai ekstrem.
        pert_minimum = float(
            severity_values.quantile(0.10)
        )
        pert_likely = float(
            severity_values.quantile(0.50)
        )
        pert_maximum = float(
            severity_values.quantile(0.90)
        )

        if pert_maximum <= pert_minimum:
            pert_maximum = float(
                severity_values.max()
            )

        if pert_maximum <= pert_minimum:
            st.warning(
                "Rentang severity belum memadai untuk "
                "membentuk distribusi BETA-PERT."
            )
        else:
            pert_likely = min(
                max(pert_likely, pert_minimum),
                pert_maximum,
            )

            pert_lambda = 4.0
            pert_alpha = 1 + pert_lambda * (
                (pert_likely - pert_minimum)
                / (pert_maximum - pert_minimum)
            )
            pert_beta = 1 + pert_lambda * (
                (pert_maximum - pert_likely)
                / (pert_maximum - pert_minimum)
            )

            total_observations = len(hop_loss_daily)
            total_events_with_hop = float(
                hop_loss_daily[
                    "Jumlah_Kejadian_Loss"
                ].sum()
            )

            selected_unit_count = int(
                hop_loss_daily[
                    "HOP_Unit_Key"
                ].nunique()
            )

            annual_unit_days = (
                selected_unit_count * 365
            )

            event_rate_per_unit_day = (
                total_events_with_hop
                / total_observations
                if total_observations > 0
                else 0
            )

            expected_annual_frequency = (
                event_rate_per_unit_day
                * annual_unit_days
            )

            rng = np.random.default_rng(
                int(random_seed)
            )

            simulated_event_counts = rng.poisson(
                lam=expected_annual_frequency,
                size=int(simulation_iterations),
            )

            total_simulated_events = int(
                simulated_event_counts.sum()
            )

            annual_losses = np.zeros(
                int(simulation_iterations),
                dtype=float,
            )

            if total_simulated_events > 0:
                beta_samples = rng.beta(
                    pert_alpha,
                    pert_beta,
                    size=total_simulated_events,
                )

                simulated_severities = (
                    pert_minimum
                    + beta_samples
                    * (pert_maximum - pert_minimum)
                )

                event_simulation_index = np.repeat(
                    np.arange(
                        int(simulation_iterations)
                    ),
                    simulated_event_counts,
                )

                annual_losses = np.bincount(
                    event_simulation_index,
                    weights=simulated_severities,
                    minlength=int(simulation_iterations),
                )

            p50_annual_loss = float(
                np.percentile(annual_losses, 50)
            )
            p90_annual_loss = float(
                np.percentile(annual_losses, 90)
            )
            p95_annual_loss = float(
                np.percentile(annual_losses, 95)
            )
            mean_annual_loss = float(
                np.mean(annual_losses)
            )
            probability_above_limit = float(
                np.mean(
                    annual_losses > exceedance_limit_rp
                )
            )
            p90_risk_limit_ratio = (
                p90_annual_loss / risk_limit_rp
                if risk_limit_rp > 0
                else 0.0
            )
            report_monte_carlo = {
                "expected_frequency": expected_annual_frequency,
                "mean": mean_annual_loss,
                "p50": p50_annual_loss,
                "p90": p90_annual_loss,
                "p95": p95_annual_loss,
                "p90_ratio": p90_risk_limit_ratio,
                "exceedance_probability": probability_above_limit,
                "exceedance_percent": exceedance_percent,
            }

            (
                monte_kpi1,
                monte_kpi2,
                monte_kpi3,
                monte_kpi4,
                monte_kpi5,
            ) = st.columns(5)

            monte_kpi1.metric(
                "Ekspektasi Frekuensi Tahunan",
                format_number(
                    expected_annual_frequency,
                    1,
                ),
            )
            monte_kpi2.metric(
                "Mean Annual Loss",
                format_compact_rupiah(
                    mean_annual_loss
                ),
            )
            monte_kpi3.metric(
                "P50 Annual Loss",
                format_compact_rupiah(
                    p50_annual_loss
                ),
            )
            monte_kpi4.metric(
                "P90 Annual Loss",
                format_compact_rupiah(
                    p90_annual_loss
                ),
            )
            monte_kpi5.metric(
                "P95 Annual Loss",
                format_compact_rupiah(
                    p95_annual_loss
                ),
            )

            limit_kpi1, limit_kpi2, limit_kpi3 = (
                st.columns(3)
            )
            limit_kpi1.metric(
                "Risk Limit Aktif",
                format_compact_rupiah(risk_limit_rp),
            )
            limit_kpi2.metric(
                "P90 terhadap Risk Limit",
                f"{p90_risk_limit_ratio:.2%}",
            )
            limit_kpi3.metric(
                (
                    "Peluang Loss > "
                    f"{exceedance_percent}% Risk Limit"
                ),
                f"{probability_above_limit:.2%}",
            )

            annual_loss_frame = pd.DataFrame(
                {
                    "Annual_Loss_Rp": annual_losses,
                }
            )

            annual_histogram = px.histogram(
                annual_loss_frame,
                x="Annual_Loss_Rp",
                nbins=50,
                histnorm="probability density",
                title=(
                    "Distribusi Probabilitas "
                    "Monte Carlo Annual Loss"
                ),
                labels={
                    "Annual_Loss_Rp": (
                        "Annual Loss (Rp)"
                    ),
                },
                color_discrete_sequence=[
                    "#00A6A6"
                ],
            )

            percentile_lines = [
                (p50_annual_loss, "P50", "#F59E0B"),
                (p90_annual_loss, "P90", "#EA580C"),
                (p95_annual_loss, "P95", "#DC2626"),
            ]

            for value, label, color in percentile_lines:
                annual_histogram.add_vline(
                    x=value,
                    line_dash="dash",
                    line_color=color,
                    annotation_text=label,
                    annotation_position="top",
                )

            annual_histogram.add_vline(
                x=exceedance_limit_rp,
                line_dash="dot",
                line_color="#111827",
                annotation_text=(
                    f"{exceedance_percent}% Risk Limit"
                ),
                annotation_position="bottom right",
            )

            annual_histogram.update_layout(
                height=470,
                margin=dict(
                    l=20,
                    r=20,
                    t=70,
                    b=20,
                ),
                showlegend=False,
            )

            st.plotly_chart(
                annual_histogram,
                use_container_width=True,
                theme="streamlit",
            )

            sorted_losses = np.sort(annual_losses)
            exceedance_probability = (
                1
                - np.arange(
                    1,
                    len(sorted_losses) + 1,
                )
                / (len(sorted_losses) + 1)
            )

            exceedance_frame = pd.DataFrame(
                {
                    "Annual_Loss_Rp": sorted_losses,
                    "Probability_of_Exceedance": (
                        exceedance_probability
                    ),
                }
            )

            exceedance_chart = px.line(
                exceedance_frame,
                x="Annual_Loss_Rp",
                y="Probability_of_Exceedance",
                title="Probability of Exceedance Curve",
                labels={
                    "Annual_Loss_Rp": (
                        "Annual Loss (Rp)"
                    ),
                    "Probability_of_Exceedance": (
                        "Probability of Exceedance"
                    ),
                },
                color_discrete_sequence=[
                    "#0F6CBD"
                ],
            )

            exceedance_chart.update_yaxes(
                tickformat=".0%",
                range=[0, 1],
            )
            exceedance_chart.add_vline(
                x=exceedance_limit_rp,
                line_dash="dot",
                line_color="#111827",
                annotation_text=(
                    f"Batas {exceedance_percent}% Risk Limit"
                ),
                annotation_position="top right",
            )
            exceedance_chart.update_layout(
                height=440,
                margin=dict(
                    l=20,
                    r=20,
                    t=70,
                    b=20,
                ),
            )

            st.plotly_chart(
                exceedance_chart,
                use_container_width=True,
                theme="streamlit",
            )

            pert_sample_size = min(
                int(simulation_iterations),
                50_000,
            )
            pert_visual_samples = (
                pert_minimum
                + rng.beta(
                    pert_alpha,
                    pert_beta,
                    size=pert_sample_size,
                )
                * (pert_maximum - pert_minimum)
            )

            pert_frame = pd.DataFrame(
                {
                    "Severity_Rp": pert_visual_samples,
                }
            )

            pert_chart = px.histogram(
                pert_frame,
                x="Severity_Rp",
                nbins=45,
                histnorm="probability density",
                title=(
                    "Distribusi BETA-PERT Severity "
                    "per Kejadian Loss"
                ),
                labels={
                    "Severity_Rp": (
                        "Severity per Kejadian (Rp)"
                    ),
                },
                color_discrete_sequence=[
                    "#7C3AED"
                ],
            )

            pert_parameter_lines = [
                (
                    pert_minimum,
                    "P10",
                    "#16A34A",
                    1.10,
                ),
                (
                    pert_likely,
                    "P50",
                    "#F59E0B",
                    1.02,
                ),
                (
                    pert_maximum,
                    "P90",
                    "#DC2626",
                    1.10,
                ),
            ]

            for (
                value,
                label,
                color,
                label_height,
            ) in pert_parameter_lines:
                pert_chart.add_vline(
                    x=value,
                    line_dash="dash",
                    line_color=color,
                )
                pert_chart.add_annotation(
                    x=value,
                    y=label_height,
                    xref="x",
                    yref="paper",
                    text=label,
                    showarrow=False,
                    font=dict(color=color),
                )

            pert_chart.update_layout(
                height=460,
                margin=dict(
                    l=20,
                    r=20,
                    t=95,
                    b=20,
                ),
                showlegend=False,
            )

            st.plotly_chart(
                pert_chart,
                use_container_width=True,
                theme="streamlit",
            )

            parameter_table = pd.DataFrame(
                {
                    "Parameter": [
                        "Minimum severity (P10)",
                        "Most likely severity (P50)",
                        "Maximum severity (P90)",
                        "Alpha BETA-PERT",
                        "Beta BETA-PERT",
                        "Laju kejadian per unit-hari",
                    ],
                    "Nilai": [
                        format_compact_rupiah(
                            pert_minimum
                        ),
                        format_compact_rupiah(
                            pert_likely
                        ),
                        format_compact_rupiah(
                            pert_maximum
                        ),
                        f"{pert_alpha:.4f}",
                        f"{pert_beta:.4f}",
                        f"{event_rate_per_unit_day:.6f}",
                    ],
                }
            )

            st.dataframe(
                parameter_table,
                use_container_width=True,
                hide_index=True,
            )

            with st.expander(
                "Cara membaca Monte Carlo dan BETA-PERT"
            ):
                st.markdown(
                    """
- **Histogram Monte Carlo** menunjukkan kemungkinan
  berbagai nilai kerugian tahunan dari seluruh iterasi.
- **P50** adalah nilai annual loss yang dilampaui oleh
  sekitar 50% hasil simulasi.
- **P90** adalah nilai annual loss yang dilampaui oleh
  sekitar 10% hasil simulasi.
- **P95** adalah nilai annual loss yang dilampaui oleh
  sekitar 5% hasil simulasi.
- Pada **Probability of Exceedance Curve**, sumbu Y
  menunjukkan peluang hasil simulasi melampaui nilai
  kerugian pada sumbu X.
- Distribusi **BETA-PERT** menggambarkan ketidakpastian
  severity setiap Kejadian Loss berdasarkan P10,
  median/P50, dan P90 data aktual terfilter.
"""
                )

            st.info(
                "Model ini merupakan estimasi berbasis data "
                "historis terfilter. Parameter P10–P50–P90 "
                "digunakan untuk mengurangi dominasi outlier. "
                "Hasil perlu divalidasi bersama pemilik risiko "
                "sebelum digunakan sebagai batas keputusan."
            )


# ============================================================
# TAB PREDIKSI RISIKO
# ============================================================

with tab_prediction:
    st.subheader(
        "Prediksi Risiko Hambatan Energi Primer"
    )

    st.caption(
        "Simulasi looking-forward berbasis skenario HOP, "
        "laju Kejadian Loss historis, distribusi BETA-PERT, "
        "dan Risk Limit aktif."
    )

    prediction_history = hop_loss_daily.copy()

    prediction_history["Status_KRI_HOP"] = "NORMAL"
    prediction_history.loc[
        prediction_history["Nilai_HOP"] < 10,
        "Status_KRI_HOP",
    ] = "EMERGENCY"
    prediction_history.loc[
        prediction_history["Nilai_HOP"].between(
            10,
            15,
            inclusive="both",
        ),
        "Status_KRI_HOP",
    ] = "SIAGA"

    prediction_units = sorted(
        prediction_history["HOP_Unit_Key"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if not prediction_units:
        st.warning(
            "Prediksi belum dapat dijalankan karena tidak "
            "tersedia observasi HOP unit-hari."
        )
    else:
        latest_hop_date = pd.to_datetime(
            prediction_history["Tanggal"],
            errors="coerce",
        ).max()

        default_prediction_start = (
            latest_hop_date.date() + timedelta(days=1)
            if pd.notna(latest_hop_date)
            else date.today()
        )
        default_prediction_end = (
            default_prediction_start + timedelta(days=89)
        )

        input_col1, input_col2, input_col3 = st.columns(3)

        with input_col1:
            prediction_unit = st.selectbox(
                "Unit Prediksi",
                options=prediction_units,
                key="prediction_unit",
            )

        with input_col2:
            prediction_start = st.date_input(
                "Tanggal Awal Prediksi",
                value=default_prediction_start,
                key="prediction_start_date",
            )

        with input_col3:
            prediction_end = st.date_input(
                "Tanggal Akhir Prediksi",
                value=default_prediction_end,
                key="prediction_end_date",
            )

        if prediction_end < prediction_start:
            st.error(
                "Tanggal akhir tidak boleh lebih awal "
                "daripada tanggal awal prediksi."
            )
        else:
            projection_days = (
                prediction_end - prediction_start
            ).days + 1

            parameter_col1, parameter_col2 = st.columns(2)

            with parameter_col1:
                projected_hop = st.number_input(
                    "Proyeksi HOP (hari)",
                    min_value=0.0,
                    max_value=90.0,
                    value=12.0,
                    step=0.5,
                    format="%.2f",
                    help=(
                        "Nilai HOP yang diperkirakan berlaku "
                        "pada periode prediksi."
                    ),
                    key="projected_hop",
                )

            with parameter_col2:
                prediction_iterations = st.number_input(
                    "Iterasi Prediksi",
                    min_value=1_000,
                    max_value=100_000,
                    value=10_000,
                    step=1_000,
                    key="prediction_iterations",
                )

            if projected_hop < 10:
                projected_hop_status = "EMERGENCY"
                projected_status_color = "#DC2626"
                projected_status_label = "Emergency / Merah"
            elif projected_hop <= 15:
                projected_hop_status = "SIAGA"
                projected_status_color = "#EAB308"
                projected_status_label = "Siaga / Kuning"
            else:
                projected_hop_status = "NORMAL"
                projected_status_color = "#16A34A"
                projected_status_label = "Normal / Hijau"

            status_history = prediction_history[
                (
                    prediction_history["HOP_Unit_Key"]
                    == prediction_unit
                )
                & (
                    prediction_history["Status_KRI_HOP"]
                    == projected_hop_status
                )
            ].copy()

            history_source_label = (
                f"{prediction_unit} – "
                f"{projected_hop_status}"
            )

            if len(status_history) < 30:
                status_history = prediction_history[
                    prediction_history["Status_KRI_HOP"]
                    == projected_hop_status
                ].copy()
                history_source_label = (
                    "seluruh unit – "
                    f"{projected_hop_status}"
                )

            if status_history.empty:
                status_history = prediction_history.copy()
                history_source_label = (
                    "seluruh unit dan seluruh status HOP"
                )

            historical_observations = len(status_history)
            historical_events = float(
                status_history[
                    "Jumlah_Kejadian_Loss"
                ].sum()
            )
            historical_event_rate = (
                historical_events / historical_observations
                if historical_observations > 0
                else 0.0
            )

            expected_event_frequency = (
                historical_event_rate * projection_days
            )
            probability_at_least_one = (
                1 - math.exp(-expected_event_frequency)
            )

            unit_severity = filtered[
                filtered["HOP_Unit_Key"]
                == prediction_unit
            ]["Loss_Opportunity_Rp"].dropna()
            unit_severity = unit_severity[
                unit_severity > 0
            ].astype(float)

            severity_basis_label = prediction_unit

            if len(unit_severity) < 3:
                unit_severity = filtered[
                    "Loss_Opportunity_Rp"
                ].dropna()
                unit_severity = unit_severity[
                    unit_severity > 0
                ].astype(float)
                severity_basis_label = "seluruh unit terfilter"

            duration_metric, status_metric = st.columns(2)
            duration_metric.metric(
                "Durasi Prediksi",
                f"{projection_days:,} hari kalender",
            )
            status_metric.markdown(
                "**Status Proyeksi HOP**"
            )
            status_metric.markdown(
                f"<div style='background:{projected_status_color};"
                "color:white;padding:11px 14px;border-radius:8px;"
                "font-weight:700;text-align:center'>"
                f"{projected_status_label} · "
                f"HOP {projected_hop:,.2f}</div>",
                unsafe_allow_html=True,
            )

            if len(unit_severity) < 3:
                st.warning(
                    "Minimal tiga nilai Loss Opportunity positif "
                    "diperlukan untuk simulasi dampak."
                )
            else:
                prediction_minimum = float(
                    unit_severity.quantile(0.10)
                )
                prediction_likely = float(
                    unit_severity.quantile(0.50)
                )
                prediction_maximum = float(
                    unit_severity.quantile(0.90)
                )

                if prediction_maximum <= prediction_minimum:
                    prediction_maximum = float(
                        unit_severity.max()
                    )

                if prediction_maximum <= prediction_minimum:
                    st.warning(
                        "Rentang Loss Opportunity belum memadai "
                        "untuk membentuk distribusi BETA-PERT."
                    )
                else:
                    prediction_likely = min(
                        max(
                            prediction_likely,
                            prediction_minimum,
                        ),
                        prediction_maximum,
                    )
                    prediction_lambda = 4.0
                    prediction_alpha = (
                        1
                        + prediction_lambda
                        * (
                            prediction_likely
                            - prediction_minimum
                        )
                        / (
                            prediction_maximum
                            - prediction_minimum
                        )
                    )
                    prediction_beta = (
                        1
                        + prediction_lambda
                        * (
                            prediction_maximum
                            - prediction_likely
                        )
                        / (
                            prediction_maximum
                            - prediction_minimum
                        )
                    )

                    prediction_rng = np.random.default_rng(
                        int(random_seed) + 101
                    )
                    prediction_event_counts = (
                        prediction_rng.poisson(
                            lam=expected_event_frequency,
                            size=int(prediction_iterations),
                        )
                    )
                    prediction_total_events = int(
                        prediction_event_counts.sum()
                    )
                    predicted_losses = np.zeros(
                        int(prediction_iterations),
                        dtype=float,
                    )

                    if prediction_total_events > 0:
                        prediction_beta_samples = (
                            prediction_rng.beta(
                                prediction_alpha,
                                prediction_beta,
                                size=prediction_total_events,
                            )
                        )
                        prediction_severities = (
                            prediction_minimum
                            + prediction_beta_samples
                            * (
                                prediction_maximum
                                - prediction_minimum
                            )
                        )
                        prediction_simulation_index = np.repeat(
                            np.arange(
                                int(prediction_iterations)
                            ),
                            prediction_event_counts,
                        )
                        predicted_losses = np.bincount(
                            prediction_simulation_index,
                            weights=prediction_severities,
                            minlength=int(prediction_iterations),
                        )

                    prediction_mean = float(
                        np.mean(predicted_losses)
                    )
                    prediction_p50 = float(
                        np.percentile(predicted_losses, 50)
                    )
                    prediction_p90 = float(
                        np.percentile(predicted_losses, 90)
                    )
                    prediction_p95 = float(
                        np.percentile(predicted_losses, 95)
                    )
                    prediction_exceedance = float(
                        np.mean(
                            predicted_losses
                            > exceedance_limit_rp
                        )
                    )

                    likelihood_score = (
                        likelihood_score_from_probability(
                            probability_at_least_one
                        )
                    )
                    likelihood_letter = {
                        1: "A",
                        2: "B",
                        3: "C",
                        4: "D",
                        5: "E",
                    }[likelihood_score]
                    impact_ratio = (
                        prediction_p90 / risk_limit_rp
                        if risk_limit_rp > 0
                        else 0.0
                    )
                    impact_score = (
                        impact_score_from_risk_limit_ratio(
                            impact_ratio
                        )
                    )
                    prediction_risk_score = edir_risk_score(
                        impact_score,
                        likelihood_score,
                    )
                    prediction_risk_level = edir_risk_level(
                        prediction_risk_score
                    )

                    result_columns = st.columns(6)
                    result_columns[0].metric(
                        "Ekspektasi Kejadian",
                        f"{expected_event_frequency:,.2f}",
                    )
                    result_columns[1].metric(
                        "P(≥1 Kejadian)",
                        f"{probability_at_least_one:.2%}",
                    )
                    result_columns[2].metric(
                        "P50 Loss",
                        format_compact_rupiah(
                            prediction_p50
                        ),
                    )
                    result_columns[3].metric(
                        "P90 Loss",
                        format_compact_rupiah(
                            prediction_p90
                        ),
                    )
                    result_columns[4].metric(
                        "Kemungkinan",
                        (
                            f"{likelihood_letter} "
                            f"({likelihood_score})"
                        ),
                    )
                    result_columns[5].metric(
                        "Dampak",
                        str(impact_score),
                    )

                    risk_result_col1, risk_result_col2 = (
                        st.columns([1, 2])
                    )
                    risk_result_col1.metric(
                        "Nilai Risiko",
                        str(prediction_risk_score),
                        delta=prediction_risk_level,
                        delta_color="off",
                    )

                    prediction_summary = pd.DataFrame(
                        {
                            "Parameter": [
                                "Mean predicted loss",
                                "P50 predicted loss",
                                "P90 predicted loss",
                                "P95 predicted loss",
                                "P90 terhadap Risk Limit",
                                (
                                    "Peluang loss melampaui "
                                    f"{exceedance_percent}% "
                                    "Risk Limit"
                                ),
                            ],
                            "Nilai": [
                                format_compact_rupiah(
                                    prediction_mean
                                ),
                                format_compact_rupiah(
                                    prediction_p50
                                ),
                                format_compact_rupiah(
                                    prediction_p90
                                ),
                                format_compact_rupiah(
                                    prediction_p95
                                ),
                                f"{impact_ratio:.2%}",
                                f"{prediction_exceedance:.2%}",
                            ],
                        }
                    )
                    risk_result_col2.dataframe(
                        prediction_summary,
                        use_container_width=True,
                        hide_index=True,
                    )

                    prediction_frame = pd.DataFrame(
                        {"Predicted_Loss_Rp": predicted_losses}
                    )
                    prediction_chart = px.histogram(
                        prediction_frame,
                        x="Predicted_Loss_Rp",
                        nbins=45,
                        histnorm="probability density",
                        title=(
                            "Distribusi Prediksi Total Loss – "
                            f"{prediction_unit}"
                        ),
                        labels={
                            "Predicted_Loss_Rp": (
                                "Predicted Loss (Rp)"
                            )
                        },
                        color_discrete_sequence=["#2563EB"],
                    )
                    for line_value, line_label, line_color in [
                        (
                            prediction_p50,
                            "P50",
                            "#F59E0B",
                        ),
                        (
                            prediction_p90,
                            "P90",
                            "#DC2626",
                        ),
                        (
                            exceedance_limit_rp,
                            (
                                f"{exceedance_percent}% "
                                "Risk Limit"
                            ),
                            "#111827",
                        ),
                    ]:
                        prediction_chart.add_vline(
                            x=line_value,
                            line_dash="dash",
                            line_color=line_color,
                            annotation_text=line_label,
                            annotation_position="top",
                        )
                    prediction_chart.update_layout(
                        height=450,
                        margin=dict(
                            l=20,
                            r=20,
                            t=75,
                            b=20,
                        ),
                        showlegend=False,
                    )
                    st.plotly_chart(
                        prediction_chart,
                        use_container_width=True,
                        theme="streamlit",
                    )

                    prediction_matrix = np.array(
                        [
                            [1, 5, 10, 15, 20],
                            [2, 6, 11, 16, 21],
                            [3, 8, 13, 18, 23],
                            [4, 9, 14, 19, 24],
                            [7, 12, 17, 22, 25],
                        ]
                    )
                    prediction_colorscale = [
                        [0.0000, "#35B24A"],
                        [0.1875, "#35B24A"],
                        [0.1876, "#8DCC74"],
                        [0.3958, "#8DCC74"],
                        [0.3959, "#FFE31A"],
                        [0.6042, "#FFE31A"],
                        [0.6043, "#F5A623"],
                        [0.7708, "#F5A623"],
                        [0.7709, "#EF503B"],
                        [1.0000, "#EF503B"],
                    ]
                    prediction_heatmap = go.Figure()
                    prediction_heatmap.add_trace(
                        go.Heatmap(
                            z=prediction_matrix,
                            x=[1, 2, 3, 4, 5],
                            y=[1, 2, 3, 4, 5],
                            zmin=1,
                            zmax=25,
                            colorscale=prediction_colorscale,
                            showscale=False,
                            hovertemplate=(
                                "Kemungkinan: %{y}<br>"
                                "Dampak: %{x}<br>"
                                "Nilai Risiko: %{z}"
                                "<extra></extra>"
                            ),
                        )
                    )
                    for y_index in range(5):
                        for x_index in range(5):
                            prediction_heatmap.add_annotation(
                                x=x_index + 1,
                                y=y_index + 1,
                                text=str(
                                    int(
                                        prediction_matrix[
                                            y_index,
                                            x_index,
                                        ]
                                    )
                                ),
                                showarrow=False,
                                font=dict(
                                    color="#111827",
                                    size=13,
                                ),
                            )
                    prediction_heatmap.add_trace(
                        go.Scatter(
                            x=[impact_score + 0.28],
                            y=[likelihood_score + 0.28],
                            mode="markers+text",
                            marker=dict(
                                size=32,
                                color="#0F172A",
                                line=dict(
                                    color="white",
                                    width=2,
                                ),
                            ),
                            text=["PRED"],
                            textposition="middle center",
                            textfont=dict(
                                color="white",
                                size=10,
                            ),
                            hovertemplate=(
                                f"{prediction_unit}<br>"
                                f"Kemungkinan: {likelihood_letter}<br>"
                                f"Dampak: {impact_score}<br>"
                                f"Nilai Risiko: "
                                f"{prediction_risk_score}<br>"
                                f"Level: {prediction_risk_level}"
                                "<extra></extra>"
                            ),
                            name="Prediksi",
                        )
                    )
                    prediction_heatmap.update_xaxes(
                        title="Skala Dampak",
                        tickvals=[1, 2, 3, 4, 5],
                        range=[0.5, 5.5],
                    )
                    prediction_heatmap.update_yaxes(
                        title="Skala Kemungkinan",
                        tickvals=[1, 2, 3, 4, 5],
                        ticktext=["A", "B", "C", "D", "E"],
                        range=[0.5, 5.5],
                    )
                    prediction_heatmap.update_layout(
                        title="Posisi Prediksi pada Heat Map Juknis",
                        height=570,
                        margin=dict(
                            l=70,
                            r=30,
                            t=70,
                            b=60,
                        ),
                        showlegend=False,
                    )
                    st.plotly_chart(
                        prediction_heatmap,
                        use_container_width=True,
                        theme="streamlit",
                    )

                    if projected_hop_status == "EMERGENCY":
                        recommendation = (
                            "Aktifkan respons prioritas: validasi "
                            "stok dan jadwal pasokan, percepat "
                            "pengiriman, evaluasi kualitas batubara, "
                            "dan siapkan skenario operasi pembangkit."
                        )
                    elif projected_hop_status == "SIAGA":
                        recommendation = (
                            "Perketat monitoring harian HOP dan "
                            "realisasi pasokan, konfirmasi jadwal "
                            "pengiriman, serta siapkan tindakan "
                            "kontinjensi sebelum HOP turun di bawah 10."
                        )
                    else:
                        recommendation = (
                            "Pertahankan monitoring rutin dan "
                            "pastikan realisasi pasokan menjaga HOP "
                            "tetap di atas 15 hari."
                        )

                    report_prediction = {
                        "unit": prediction_unit,
                        "start": prediction_start,
                        "end": prediction_end,
                        "days": projection_days,
                        "projected_hop": projected_hop,
                        "status": projected_hop_status,
                        "historical_source": history_source_label,
                        "historical_observations": historical_observations,
                        "historical_events": historical_events,
                        "expected_frequency": expected_event_frequency,
                        "probability": probability_at_least_one,
                        "mean": prediction_mean,
                        "p50": prediction_p50,
                        "p90": prediction_p90,
                        "p95": prediction_p95,
                        "p90_ratio": impact_ratio,
                        "exceedance_probability": prediction_exceedance,
                        "likelihood_score": likelihood_score,
                        "likelihood_letter": likelihood_letter,
                        "impact_score": impact_score,
                        "risk_score": prediction_risk_score,
                        "risk_level": prediction_risk_level,
                        "recommendation": recommendation,
                    }

                    st.success(
                        "**Rekomendasi model:** "
                        + recommendation
                    )

                    with st.expander(
                        "Dasar dan asumsi prediksi"
                    ):
                        st.markdown(
                            f"""
- Durasi dihitung otomatis dari **{prediction_start:%d %b %Y}** sampai **{prediction_end:%d %b %Y}**: **{projection_days:,} hari kalender**.
- Laju historis berasal dari **{history_source_label}**, dengan **{historical_observations:,} observasi unit-hari** dan **{historical_events:,.0f} kejadian**.
- Basis severity berasal dari **{severity_basis_label}**.
- Frekuensi menggunakan distribusi **Poisson** dan severity menggunakan **BETA-PERT**.
- Faktor kemungkinan memakai peluang minimal satu kejadian; faktor dampak memakai **P90/Risk Limit**.
- Hasil merupakan prediksi berbasis skenario, bukan kepastian kejadian.
"""
                        )


# ============================================================
# TAB RISK HEAT MAP
# ============================================================

with tab_heatmap:
    st.subheader(
        "Risk Heat Map Hambatan Energi Primer"
    )

    st.caption(
        "Skala kemungkinan dibentuk dari frekuensi relatif "
        "Kejadian Loss. Skala dampak dihitung dari total "
        "Loss Opportunity terhadap Risk Limit aktif."
    )

    st.info(
        "Risk Limit aktif: "
        f"**{format_compact_rupiah(risk_limit_rp)}**. "
        "Ubah nilainya melalui tab Monte Carlo & BETA-PERT; "
        "heat map akan dihitung ulang secara otomatis."
    )

    heatmap_source = filtered.copy()

    if "Start_DateTime" in heatmap_source.columns:
        heatmap_source = heatmap_source.dropna(
            subset=["Start_DateTime"]
        )

    heatmap_source = heatmap_source.dropna(
        subset=[
            "Kategori_Final",
            LOSS_ID_COLUMN,
            "Loss_Opportunity_Rp",
        ]
    )

    heatmap_source = heatmap_source[
        heatmap_source["Loss_Opportunity_Rp"] > 0
    ]

    if heatmap_source.empty:
        st.warning(
            "Risk heat map belum dapat dibentuk karena "
            "tidak terdapat Kejadian Loss bertanggal dengan "
            "Loss Opportunity positif pada data terfilter."
        )

    else:
        category_risk = (
            heatmap_source
            .groupby(
                "Kategori_Final",
                as_index=False,
            )
            .agg(
                Jumlah_Kejadian=(
                    LOSS_ID_COLUMN,
                    "nunique",
                ),
                Median_Severity_Rp=(
                    "Loss_Opportunity_Rp",
                    "median",
                ),
                Total_Loss_Rp=(
                    "Loss_Opportunity_Rp",
                    "sum",
                ),
            )
        )

        category_count = len(category_risk)

        if category_count == 1:
            category_risk["Skala_Kemungkinan"] = 3
        else:
            likelihood_percentile = (
                category_risk["Jumlah_Kejadian"]
                .rank(method="average", pct=True)
            )

            category_risk["Skala_Kemungkinan"] = (
                np.ceil(likelihood_percentile * 5)
                .clip(1, 5)
                .astype(int)
            )

        category_risk["Rasio_Risk_Limit"] = (
            category_risk["Total_Loss_Rp"]
            / risk_limit_rp
        )
        category_risk["Persen_Risk_Limit"] = (
            category_risk["Rasio_Risk_Limit"] * 100
        )
        category_risk["Skala_Dampak"] = (
            category_risk["Rasio_Risk_Limit"]
            .apply(impact_score_from_risk_limit_ratio)
            .astype(int)
        )

        # Nilai matriks mengikuti Gambar 3 Peta Risiko pada
        # 0012.E-2024 Edir Juknis Perencanaan Manajemen
        # Risiko Terintegrasi, bukan perkalian sederhana.
        risk_matrix = np.array(
            [
                [1, 5, 10, 15, 20],
                [2, 6, 11, 16, 21],
                [3, 8, 13, 18, 23],
                [4, 9, 14, 19, 24],
                [7, 12, 17, 22, 25],
            ]
        )

        category_risk["Nilai_Risiko"] = category_risk.apply(
            lambda row: int(
                risk_matrix[
                    int(row["Skala_Kemungkinan"]) - 1,
                    int(row["Skala_Dampak"]) - 1,
                ]
            ),
            axis=1,
        )

        category_risk["Level_Risiko"] = "Low"
        category_risk.loc[
            category_risk["Nilai_Risiko"].between(6, 10),
            "Level_Risiko",
        ] = "Low to Moderate"
        category_risk.loc[
            category_risk["Nilai_Risiko"].between(11, 15),
            "Level_Risiko",
        ] = "Moderate"
        category_risk.loc[
            category_risk["Nilai_Risiko"].between(16, 19),
            "Level_Risiko",
        ] = "Moderate to High"
        category_risk.loc[
            category_risk["Nilai_Risiko"].between(20, 25),
            "Level_Risiko",
        ] = "High"

        category_risk = category_risk.sort_values(
            [
                "Nilai_Risiko",
                "Total_Loss_Rp",
            ],
            ascending=False,
        ).reset_index(drop=True)

        category_risk["Kode"] = [
            f"K{index + 1}"
            for index in range(len(category_risk))
        ]

        report_category_risk = category_risk.copy()

        risk_colorscale = [
            [0.0000, "#35B24A"],
            [0.1875, "#35B24A"],
            [0.1876, "#8DCC74"],
            [0.3958, "#8DCC74"],
            [0.3959, "#FFE31A"],
            [0.6042, "#FFE31A"],
            [0.6043, "#F5A623"],
            [0.7708, "#F5A623"],
            [0.7709, "#EF503B"],
            [1.0000, "#EF503B"],
        ]

        heatmap_figure = go.Figure()

        heatmap_figure.add_trace(
            go.Heatmap(
                z=risk_matrix,
                x=[1, 2, 3, 4, 5],
                y=[1, 2, 3, 4, 5],
                zmin=1,
                zmax=25,
                colorscale=risk_colorscale,
                showscale=False,
                hovertemplate=(
                    "Kemungkinan: %{y}<br>"
                    "Dampak: %{x}<br>"
                    "Nilai Risiko: %{z}<extra></extra>"
                ),
            )
        )

        for likelihood_index in range(5):
            for impact_index in range(5):
                cell_value = int(
                    risk_matrix[
                        likelihood_index,
                        impact_index,
                    ]
                )

                heatmap_figure.add_annotation(
                    x=impact_index + 1,
                    y=likelihood_index + 1,
                    text=str(cell_value),
                    showarrow=False,
                    font=dict(
                        color="#111827",
                        size=14,
                    ),
                )

        heatmap_figure.add_trace(
            go.Scatter(
                x=(
                    category_risk["Skala_Dampak"]
                    + 0.31
                ),
                y=(
                    category_risk["Skala_Kemungkinan"]
                    + 0.31
                ),
                mode="markers+text",
                marker=dict(
                    size=29,
                    color="#0F172A",
                    line=dict(
                        color="white",
                        width=2,
                    ),
                ),
                text=category_risk["Kode"],
                textposition="middle center",
                textfont=dict(
                    color="white",
                    size=12,
                ),
                customdata=category_risk[
                    [
                        "Kategori_Final",
                        "Jumlah_Kejadian",
                        "Median_Severity_Rp",
                        "Rasio_Risk_Limit",
                        "Level_Risiko",
                    ]
                ].to_numpy(),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Jumlah Kejadian: %{customdata[1]}<br>"
                    "Median Severity: Rp%{customdata[2]:,.0f}<br>"
                    "% Risk Limit: %{customdata[3]:.2%}<br>"
                    "Level: %{customdata[4]}<extra></extra>"
                ),
                name="Kategori Risiko",
            )
        )

        heatmap_figure.update_xaxes(
            title="Skala Dampak",
            tickmode="array",
            tickvals=[1, 2, 3, 4, 5],
            ticktext=[
                "1 Sangat Rendah",
                "2 Rendah",
                "3 Moderat",
                "4 Tinggi",
                "5 Sangat Tinggi",
            ],
            range=[0.5, 5.5],
        )
        heatmap_figure.update_yaxes(
            title="Skala Kemungkinan",
            tickmode="array",
            tickvals=[1, 2, 3, 4, 5],
            ticktext=[
                "A · Sangat Jarang Terjadi",
                "B · Jarang Terjadi",
                "C · Bisa Terjadi",
                "D · Sangat Mungkin Terjadi",
                "E · Hampir Pasti Terjadi",
            ],
            range=[0.5, 5.5],
        )
        heatmap_figure.update_layout(
            title=(
                "Heat Map Relatif Kategori "
                "Hambatan Energi Primer"
            ),
            height=650,
            margin=dict(
                l=120,
                r=40,
                t=80,
                b=110,
            ),
            showlegend=False,
        )

        st.plotly_chart(
            heatmap_figure,
            use_container_width=True,
            theme="streamlit",
        )

        st.markdown(
            "**Legenda warna berdasarkan "
            "0012.E-2024 Edir Juknis Perencanaan "
            "Manajemen Risiko Terintegrasi**"
        )

        st.markdown(
            """
<div style="display:flex;flex-wrap:wrap;gap:10px;margin:8px 0 20px 0;">
  <div style="background:#35B24A;color:#ffffff;padding:10px 16px;border-radius:8px;font-weight:600;">1–5 · Low</div>
  <div style="background:#8DCC74;color:#102A13;padding:10px 16px;border-radius:8px;font-weight:600;">6–10 · Low to Moderate</div>
  <div style="background:#FFE31A;color:#332C00;padding:10px 16px;border-radius:8px;font-weight:600;">11–15 · Moderate</div>
  <div style="background:#F5A623;color:#2F1D00;padding:10px 16px;border-radius:8px;font-weight:600;">16–19 · Moderate to High</div>
  <div style="background:#EF503B;color:#ffffff;padding:10px 16px;border-radius:8px;font-weight:600;">20–25 · High</div>
</div>
""",
            unsafe_allow_html=True,
        )

        heatmap_display = category_risk[
            [
                "Kode",
                "Kategori_Final",
                "Jumlah_Kejadian",
                "Median_Severity_Rp",
                "Persen_Risk_Limit",
                "Skala_Kemungkinan",
                "Skala_Dampak",
                "Nilai_Risiko",
                "Level_Risiko",
            ]
        ].copy()

        st.dataframe(
            heatmap_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Kode": st.column_config.TextColumn(
                    "Kode"
                ),
                "Kategori_Final": (
                    st.column_config.TextColumn(
                        "Kategori Risiko"
                    )
                ),
                "Jumlah_Kejadian": (
                    st.column_config.NumberColumn(
                        "Jumlah Kejadian",
                        format="%d",
                    )
                ),
                "Median_Severity_Rp": (
                    st.column_config.NumberColumn(
                        "Median Severity",
                        format="Rp %,.0f",
                    )
                ),
                "Persen_Risk_Limit": (
                    st.column_config.NumberColumn(
                        "% Risk Limit",
                        format="%.2f%%",
                    )
                ),
                "Skala_Kemungkinan": (
                    st.column_config.NumberColumn(
                        "Skala Kemungkinan",
                        format="%d",
                    )
                ),
                "Skala_Dampak": (
                    st.column_config.NumberColumn(
                        "Skala Dampak",
                        format="%d",
                    )
                ),
                "Nilai_Risiko": (
                    st.column_config.NumberColumn(
                        "Nilai Risiko",
                        format="%d",
                    )
                ),
                "Level_Risiko": (
                    st.column_config.TextColumn(
                        "Level Risiko"
                    )
                ),
            },
        )

        with st.expander(
            "Dasar perhitungan Risk Heat Map"
        ):
            st.markdown(
                """
- **Skala kemungkinan** dibentuk dari peringkat relatif
  jumlah Kejadian Loss antar-kategori pada data terfilter.
- **Skala dampak** menggunakan total Loss Opportunity
  kategori terhadap Risk Limit aktif: sampai 20% = 1,
  20–40% = 2, 40–60% = 3, 60–80% = 4, dan di atas
  80% = 5.
- **Nilai risiko** mengikuti posisi matriks pada Gambar 3
  Peta Risiko dalam 0012.E-2024 Edir Juknis Perencanaan
  Manajemen Risiko Terintegrasi.
- Legend warna: 1–5 Low, 6–10 Low to Moderate,
  11–15 Moderate, 16–19 Moderate to High, dan
  20–25 High.
- Heat map ini merupakan pembandingan relatif untuk
  eksplorasi model. Batas skala perlu diganti dengan
  kriteria matriks risiko korporat sebelum digunakan
  sebagai penetapan level risiko resmi.
"""
            )


# ============================================================
# TAB VALIDASI MODEL
# ============================================================


def classify_backtest_hop(value):
    """Klasifikasi KRI HOP untuk validasi prediksi."""
    if pd.isna(value):
        return "TIDAK TERSEDIA"
    if value < 10:
        return "EMERGENCY / MERAH"
    if value <= 15:
        return "SIAGA / KUNING"
    return "NORMAL / HIJAU"


def safe_backtest_error(actual, predicted):
    """Absolute percentage error tanpa pembagian nol."""
    if pd.isna(actual) or pd.isna(predicted) or actual == 0:
        return np.nan
    return abs(float(actual) - float(predicted)) / abs(float(actual)) * 100


def prepare_backtest_sources(loss_source, hop_source):
    """Menyiapkan data EVENT dan HOP untuk rolling backtesting."""
    loss_bt = loss_source.copy()
    hop_bt = hop_source.copy()

    if "Start_DateTime" not in loss_bt.columns:
        raise ValueError("Kolom Start_DateTime tidak ditemukan.")
    if "Tanggal" not in hop_bt.columns:
        raise ValueError("Kolom Tanggal pada HOP_Harian tidak ditemukan.")

    loss_bt["_Tanggal_BT"] = pd.to_datetime(
        loss_bt["Start_DateTime"], errors="coerce"
    )
    hop_bt["_Tanggal_BT"] = pd.to_datetime(
        hop_bt["Tanggal"], errors="coerce"
    )

    if "Jenis_Kejadian_Loss" in loss_bt.columns:
        loss_bt = loss_bt.loc[
            loss_bt["Jenis_Kejadian_Loss"]
            .astype(str)
            .str.strip()
            .str.upper()
            .eq("EVENT")
        ].copy()

    loss_bt["Loss_Opportunity_Rp"] = pd.to_numeric(
        loss_bt["Loss_Opportunity_Rp"], errors="coerce"
    )
    hop_bt["Nilai_HOP"] = pd.to_numeric(
        hop_bt["Nilai_HOP"], errors="coerce"
    )

    loss_bt = loss_bt.dropna(
        subset=["_Tanggal_BT", "HOP_Unit_Key", "Loss_Opportunity_Rp"]
    )
    hop_bt = hop_bt.dropna(
        subset=["_Tanggal_BT", "HOP_Unit_Key", "Nilai_HOP"]
    )
    loss_bt = loss_bt.loc[loss_bt["Loss_Opportunity_Rp"] >= 0].copy()

    loss_bt["_Bulan_BT"] = (
        loss_bt["_Tanggal_BT"].dt.to_period("M").dt.to_timestamp()
    )
    hop_bt["_Bulan_BT"] = (
        hop_bt["_Tanggal_BT"].dt.to_period("M").dt.to_timestamp()
    )
    return loss_bt, hop_bt


def simulate_backtest_loss(
    expected_frequency,
    minimum_severity,
    likely_severity,
    maximum_severity,
    iterations,
    rng,
):
    """Compound Poisson–BETA-PERT untuk satu periode pengujian."""
    event_counts = rng.poisson(
        max(float(expected_frequency), 0.0), size=int(iterations)
    )
    total_losses = np.zeros(int(iterations), dtype=float)

    if maximum_severity <= minimum_severity:
        maximum_severity = minimum_severity + 1.0
    likely_severity = float(
        np.clip(likely_severity, minimum_severity, maximum_severity)
    )
    pert_lambda = 4.0
    alpha = 1 + pert_lambda * (
        (likely_severity - minimum_severity)
        / (maximum_severity - minimum_severity)
    )
    beta = 1 + pert_lambda * (
        (maximum_severity - likely_severity)
        / (maximum_severity - minimum_severity)
    )

    for index, count in enumerate(event_counts):
        if count <= 0:
            continue
        samples = minimum_severity + rng.beta(
            alpha, beta, size=int(count)
        ) * (maximum_severity - minimum_severity)
        total_losses[index] = samples.sum()

    return event_counts, total_losses


def run_monthly_backtest(
    loss_source,
    hop_source,
    selected_unit,
    maximum_folds,
    iterations,
    random_seed,
):
    """Rolling-origin bulanan tanpa data leakage."""
    loss_bt, hop_bt = prepare_backtest_sources(loss_source, hop_source)

    if selected_unit != "Seluruh Unit":
        loss_bt = loss_bt.loc[
            loss_bt["HOP_Unit_Key"].astype(str).eq(selected_unit)
        ].copy()
        hop_bt = hop_bt.loc[
            hop_bt["HOP_Unit_Key"].astype(str).eq(selected_unit)
        ].copy()

    if hop_bt.empty:
        return pd.DataFrame(), "Data HOP tidak tersedia."

    monthly_coverage = (
        hop_bt.groupby("_Bulan_BT")
        .agg(Tanggal_Akhir=("_Tanggal_BT", "max"))
        .reset_index()
        .sort_values("_Bulan_BT")
    )
    monthly_coverage["Akhir_Bulan"] = (
        monthly_coverage["_Bulan_BT"]
        .dt.to_period("M")
        .dt.to_timestamp("M")
    )
    complete_months = monthly_coverage.loc[
        monthly_coverage["Tanggal_Akhir"]
        >= monthly_coverage["Akhir_Bulan"],
        "_Bulan_BT",
    ].tolist()

    if len(complete_months) < 3:
        return pd.DataFrame(), "Minimal diperlukan tiga bulan HOP lengkap."

    test_months = complete_months[2:][-int(maximum_folds):]
    rng = np.random.default_rng(int(random_seed))
    results = []

    for test_month in test_months:
        test_start = pd.Timestamp(test_month)
        test_end = test_start.to_period("M").to_timestamp("M")
        train_loss = loss_bt.loc[loss_bt["_Tanggal_BT"] < test_start].copy()
        actual_loss = loss_bt.loc[
            loss_bt["_Tanggal_BT"].between(test_start, test_end)
        ].copy()
        train_hop = hop_bt.loc[hop_bt["_Tanggal_BT"] < test_start].copy()
        actual_hop = hop_bt.loc[
            hop_bt["_Tanggal_BT"].between(test_start, test_end)
        ].copy()

        if train_loss.empty:
            continue

        first_month = train_loss["_Tanggal_BT"].min().to_period("M")
        last_month = (test_start - pd.Timedelta(days=1)).to_period("M")
        training_months = last_month.ordinal - first_month.ordinal + 1
        if training_months <= 0:
            continue

        expected_frequency = len(train_loss) / training_months
        severity = train_loss["Loss_Opportunity_Rp"].dropna().astype(float)
        severity = severity.loc[severity >= 0]
        if severity.empty:
            continue

        minimum_severity = float(severity.quantile(0.10))
        likely_severity = float(severity.quantile(0.50))
        maximum_severity = float(severity.quantile(0.90))
        event_sim, loss_sim = simulate_backtest_loss(
            expected_frequency,
            minimum_severity,
            likely_severity,
            maximum_severity,
            iterations,
            rng,
        )

        actual_frequency = int(len(actual_loss))
        actual_total_loss = float(actual_loss["Loss_Opportunity_Rp"].sum())
        p50_loss = float(np.quantile(loss_sim, 0.50))
        p90_loss = float(np.quantile(loss_sim, 0.90))
        p95_loss = float(np.quantile(loss_sim, 0.95))

        lookback_start = test_start - pd.Timedelta(days=30)
        projected_hop_data = train_hop.loc[
            train_hop["_Tanggal_BT"] >= lookback_start, "Nilai_HOP"
        ]
        projected_hop = (
            float(projected_hop_data.mean())
            if not projected_hop_data.empty else np.nan
        )
        actual_hop_mean = (
            float(actual_hop["Nilai_HOP"].mean())
            if not actual_hop.empty else np.nan
        )
        predicted_kri = classify_backtest_hop(projected_hop)
        actual_kri = classify_backtest_hop(actual_hop_mean)

        results.append(
            {
                "Periode_Uji": test_start,
                "Frekuensi_Aktual": actual_frequency,
                "Frekuensi_Prediksi": expected_frequency,
                "P50_Frekuensi": float(np.quantile(event_sim, 0.50)),
                "P90_Frekuensi": float(np.quantile(event_sim, 0.90)),
                "Loss_Aktual": actual_total_loss,
                "P50_Loss": p50_loss,
                "P90_Loss": p90_loss,
                "P95_Loss": p95_loss,
                "Error_P50_Pct": safe_backtest_error(actual_total_loss, p50_loss),
                "Actual_Percentile": float(np.mean(loss_sim <= actual_total_loss) * 100),
                "P90_Covered": actual_total_loss <= p90_loss,
                "HOP_Proyeksi": projected_hop,
                "HOP_Aktual": actual_hop_mean,
                "KRI_Prediksi": predicted_kri,
                "KRI_Aktual": actual_kri,
                "KRI_Akurat": predicted_kri == actual_kri,
            }
        )

    result = pd.DataFrame(results)
    if result.empty:
        return result, "Tidak ada periode yang dapat diuji."
    return result, "Backtesting berhasil dijalankan."

with tab_validation:
    st.subheader(
        "Validasi Awal PRIME-RISK"
    )

    st.caption(
        "Pemeriksaan kualitas data, dukungan statistik, "
        "kesiapan model frekuensi dan severity, serta "
        "kesenjangan validasi yang masih harus ditutup."
    )

    validation_loss = filtered.copy()

    dated_validation_loss = validation_loss.copy()
    if "Start_DateTime" in dated_validation_loss.columns:
        dated_validation_loss = dated_validation_loss.dropna(
            subset=["Start_DateTime"]
        )

    total_dated_events = int(
        dated_validation_loss[LOSS_ID_COLUMN].nunique()
    )

    paired_hop_events = 0
    if "Nilai_HOP" in dated_validation_loss.columns:
        paired_hop_events = int(
            dated_validation_loss
            .dropna(subset=["Nilai_HOP"])[
                LOSS_ID_COLUMN
            ]
            .nunique()
        )

    hop_pairing_coverage = (
        paired_hop_events / total_dated_events
        if total_dated_events > 0
        else 0
    )

    mapped_events = int(
        dated_validation_loss
        .dropna(subset=["HOP_Unit_Key"])[
            LOSS_ID_COLUMN
        ]
        .nunique()
    )
    mapping_coverage = (
        mapped_events / total_dated_events
        if total_dated_events > 0
        else 0
    )

    negative_hop_records = int(
        (filtered_hop["Nilai_HOP"] < 0).sum()
    )
    duplicate_unit_days = int(
        filtered_hop.duplicated(
            subset=[
                "Tanggal",
                "HOP_Unit_Key",
            ]
        ).sum()
    )

    severity_sample_count = int(
        dated_validation_loss[
            "Loss_Opportunity_Rp"
        ]
        .dropna()
        .gt(0)
        .sum()
    )

    validation_metric1, validation_metric2, validation_metric3, validation_metric4 = (
        st.columns(4)
    )

    validation_metric1.metric(
        "Coverage Loss–HOP",
        f"{hop_pairing_coverage:.1%}",
    )
    validation_metric2.metric(
        "Coverage Mapping Unit",
        f"{mapping_coverage:.1%}",
    )
    validation_metric3.metric(
        "Sampel Severity Positif",
        format_number(severity_sample_count),
    )
    validation_metric4.metric(
        "HOP Negatif",
        format_number(negative_hop_records),
    )

    validation_rows = [
        {
            "Area_Validasi": "Kelengkapan pasangan Loss–HOP",
            "Indikator": "Coverage kejadian bertanggal dengan Nilai HOP",
            "Hasil": f"{hop_pairing_coverage:.1%}",
            "Status": (
                "MEMADAI"
                if hop_pairing_coverage >= 0.90
                else "PERLU PERBAIKAN"
            ),
            "Tindak_Lanjut": (
                "Pertahankan coverage minimal 90%"
                if hop_pairing_coverage >= 0.90
                else "Lengkapi pasangan tanggal-unit dengan HOP"
            ),
        },
        {
            "Area_Validasi": "Mapping unit",
            "Indikator": "Kejadian bertanggal dengan HOP_Unit_Key",
            "Hasil": f"{mapping_coverage:.1%}",
            "Status": (
                "MEMADAI"
                if mapping_coverage >= 0.95
                else "PERLU PERBAIKAN"
            ),
            "Tindak_Lanjut": "Verifikasi unit yang belum terpetakan",
        },
        {
            "Area_Validasi": "Duplikasi HOP",
            "Indikator": "Duplikasi kombinasi tanggal dan unit",
            "Hasil": format_number(duplicate_unit_days),
            "Status": (
                "MEMADAI"
                if duplicate_unit_days == 0
                else "PERLU PERBAIKAN"
            ),
            "Tindak_Lanjut": "Hapus atau konsolidasikan duplikasi",
        },
        {
            "Area_Validasi": "Rentang HOP",
            "Indikator": "Observasi HOP bernilai negatif",
            "Hasil": format_number(negative_hop_records),
            "Status": (
                "MEMADAI"
                if negative_hop_records == 0
                else "VALIDASI SUMBER"
            ),
            "Tindak_Lanjut": (
                "Konfirmasi definisi dan sumber nilai HOP negatif"
            ),
        },
        {
            "Area_Validasi": "Asosiasi HOP–Loss",
            "Indikator": "Relative Risk dan 95% CI",
            "Hasil": (
                f"RR {relative_risk:.2f}x; CI "
                f"{rr_ci_low:.2f}–{rr_ci_high:.2f}"
                if (
                    relative_risk is not None
                    and rr_ci_low is not None
                    and rr_ci_high is not None
                )
                else "Belum dapat dihitung"
            ),
            "Status": (
                "SIGNIFIKAN"
                if association_significant
                else "PERLU TAMBAHAN DATA"
            ),
            "Tindak_Lanjut": (
                "Uji konsistensi per regional dan leave-one-unit-out"
            ),
        },
        {
            "Area_Validasi": "Model frekuensi",
            "Indikator": "Ketersediaan exposure unit-hari",
            "Hasil": format_number(len(filtered_hop)),
            "Status": (
                "SIAP UJI DISTRIBUSI"
                if len(filtered_hop) >= 365
                else "DATA TERBATAS"
            ),
            "Tindak_Lanjut": (
                "Bandingkan Poisson dan Negative Binomial"
            ),
        },
        {
            "Area_Validasi": "Model severity",
            "Indikator": "Jumlah severity positif bertanggal",
            "Hasil": format_number(severity_sample_count),
            "Status": (
                "SIAP UJI DISTRIBUSI"
                if severity_sample_count >= 30
                else "DATA TERBATAS"
            ),
            "Tindak_Lanjut": (
                "Bandingkan BETA-PERT, Lognormal, dan Gamma"
            ),
        },
        {
            "Area_Validasi": "Backtesting temporal",
            "Indikator": "Aktual dibanding prediksi periode berikutnya",
            "Hasil": "Belum dilakukan",
            "Status": "WAJIB DILENGKAPI",
            "Tindak_Lanjut": (
                "Pisahkan training dan validation berdasarkan waktu"
            ),
        },
        {
            "Area_Validasi": "Konvergensi Monte Carlo",
            "Indikator": "Stabilitas P90 saat iterasi ditambah",
            "Hasil": "Belum dilakukan",
            "Status": "WAJIB DILENGKAPI",
            "Tindak_Lanjut": (
                "Bandingkan P90 pada 1k, 5k, 10k, dan 50k iterasi"
            ),
        },
    ]

    validation_table = pd.DataFrame(
        validation_rows
    )

    st.dataframe(
        validation_table,
        use_container_width=True,
        hide_index=True,
        height=480,
        column_config={
            "Area_Validasi": st.column_config.TextColumn(
                "Area Validasi",
                width="medium",
            ),
            "Indikator": st.column_config.TextColumn(
                "Indikator",
                width="large",
            ),
            "Hasil": st.column_config.TextColumn(
                "Hasil",
                width="medium",
            ),
            "Status": st.column_config.TextColumn(
                "Status",
                width="medium",
            ),
            "Tindak_Lanjut": st.column_config.TextColumn(
                "Tindak Lanjut",
                width="large",
            ),
        },
    )

    validation_failures = int(
        validation_table["Status"].isin(
            [
                "PERLU PERBAIKAN",
                "DATA TERBATAS",
            ]
        ).sum()
    )
    validation_mandatory = int(
        (
            validation_table["Status"]
            == "WAJIB DILENGKAPI"
        ).sum()
    )

    if (
        validation_failures == 0
        and validation_mandatory == 0
    ):
        st.success(
            "Kesimpulan validasi awal: model memenuhi "
            "pemeriksaan yang tersedia."
        )
    else:
        st.warning(
            "Kesimpulan validasi awal: PRIME-RISK dapat "
            "digunakan untuk eksplorasi dan pengambilan "
            "keputusan pendahuluan, tetapi belum dinyatakan "
            "tervalidasi penuh. Backtesting temporal, uji "
            "distribusi pembanding, konvergensi Monte Carlo, "
            "dan validasi nilai HOP negatif masih harus "
            "diselesaikan."
        )

    with st.expander(
        "Prinsip validasi dan pencegahan data leakage"
    ):
        st.markdown(
            """
- Pembagian data harus dilakukan berdasarkan waktu,
  bukan secara acak.
- Batas P20 untuk data validasi harus dihitung hanya
  dari periode training.
- Unit pada periode validasi tidak boleh digunakan
  untuk mengkalibrasi parameter yang sedang diuji.
- Hasil perlu diuji per regional dan dengan metode
  *leave-one-unit-out* agar tidak didominasi satu unit.
- Status validasi dashboard merupakan pemeriksaan awal,
  bukan pengesahan independen atau persetujuan pemilik
  risiko.
"""
        )

    st.divider()
    st.subheader("Rolling Backtesting Temporal")
    st.caption(
        "Model dilatih hanya dengan data sebelum bulan uji, "
        "kemudian prediksi dibandingkan dengan realisasi. "
        "Frekuensi memakai Poisson, severity memakai BETA-PERT, "
        "dan total loss dibentuk melalui Monte Carlo."
    )

    try:
        backtest_loss_source, backtest_hop_source = prepare_backtest_sources(
            loss_data, hop_data
        )
        backtest_units = sorted(
            set(
                backtest_loss_source["HOP_Unit_Key"]
                .dropna().astype(str).unique()
            )
            & set(
                backtest_hop_source["HOP_Unit_Key"]
                .dropna().astype(str).unique()
            )
        )

        bt_col1, bt_col2, bt_col3, bt_col4 = st.columns(4)
        with bt_col1:
            backtest_unit = st.selectbox(
                "Unit Backtesting",
                ["Seluruh Unit"] + backtest_units,
                key="backtest_unit_v15",
            )
        with bt_col2:
            backtest_folds = st.number_input(
                "Maksimum Periode Uji",
                min_value=1,
                max_value=12,
                value=6,
                step=1,
                key="backtest_folds_v15",
            )
        with bt_col3:
            backtest_iterations = st.number_input(
                "Iterasi Backtesting",
                min_value=1_000,
                max_value=50_000,
                value=10_000,
                step=1_000,
                key="backtest_iterations_v15",
            )
        with bt_col4:
            backtest_seed = st.number_input(
                "Random Seed Backtesting",
                min_value=1,
                max_value=999_999,
                value=2026,
                step=1,
                key="backtest_seed_v15",
            )

        if st.button(
            "Jalankan Rolling Backtesting",
            type="primary",
            use_container_width=True,
            key="run_backtest_v15",
        ):
            with st.spinner("Menjalankan validasi temporal..."):
                backtest_result, backtest_message = run_monthly_backtest(
                    loss_data,
                    hop_data,
                    backtest_unit,
                    int(backtest_folds),
                    int(backtest_iterations),
                    int(backtest_seed),
                )

            if backtest_result.empty:
                st.warning(backtest_message)
            else:
                valid_errors = (
                    backtest_result["Error_P50_Pct"]
                    .replace([np.inf, -np.inf], np.nan)
                    .dropna()
                )
                mean_error = (
                    float(valid_errors.mean())
                    if not valid_errors.empty else np.nan
                )
                p90_coverage = float(
                    backtest_result["P90_Covered"].mean() * 100
                )
                frequency_mae = float(
                    np.mean(
                        np.abs(
                            backtest_result["Frekuensi_Aktual"]
                            - backtest_result["Frekuensi_Prediksi"]
                        )
                    )
                )
                valid_kri = backtest_result.loc[
                    backtest_result["KRI_Aktual"] != "TIDAK TERSEDIA"
                ]
                kri_accuracy = (
                    float(valid_kri["KRI_Akurat"].mean() * 100)
                    if not valid_kri.empty else np.nan
                )

                metric_bt1, metric_bt2, metric_bt3, metric_bt4 = st.columns(4)
                metric_bt1.metric(
                    "Rata-rata Error P50",
                    f"{mean_error:,.2f}%" if not pd.isna(mean_error) else "-",
                )
                metric_bt2.metric("P90 Coverage", f"{p90_coverage:,.2f}%")
                metric_bt3.metric("Frequency MAE", f"{frequency_mae:,.2f}")
                metric_bt4.metric(
                    "Akurasi KRI HOP",
                    f"{kri_accuracy:,.2f}%" if not pd.isna(kri_accuracy) else "-",
                )

                if not pd.isna(mean_error) and mean_error <= 20 and p90_coverage >= 80:
                    st.success("Status backtesting: BAIK / LAYAK.")
                elif not pd.isna(mean_error) and mean_error <= 35 and p90_coverage >= 60:
                    st.warning("Status backtesting: CUKUP / LAYAK DENGAN KALIBRASI.")
                elif not pd.isna(mean_error) and mean_error <= 50:
                    st.warning("Status backtesting: PERLU KALIBRASI.")
                else:
                    st.error("Status backtesting: LEMAH / PERLU PENGEMBANGAN.")

                plot_backtest = backtest_result.sort_values("Periode_Uji").copy()
                plot_backtest["Periode"] = plot_backtest[
                    "Periode_Uji"
                ].dt.strftime("%b %Y")

                backtest_loss_chart = go.Figure()
                backtest_loss_chart.add_trace(
                    go.Scatter(
                        x=plot_backtest["Periode"],
                        y=plot_backtest["Loss_Aktual"],
                        mode="lines+markers",
                        name="Loss Aktual",
                        line=dict(color="#111827", width=3),
                    )
                )
                backtest_loss_chart.add_trace(
                    go.Scatter(
                        x=plot_backtest["Periode"],
                        y=plot_backtest["P50_Loss"],
                        mode="lines+markers",
                        name="P50 Prediksi",
                        line=dict(color="#F59E0B", width=2, dash="dash"),
                    )
                )
                backtest_loss_chart.add_trace(
                    go.Scatter(
                        x=plot_backtest["Periode"],
                        y=plot_backtest["P90_Loss"],
                        mode="lines+markers",
                        name="P90 Prediksi",
                        line=dict(color="#EF4444", width=2, dash="dot"),
                    )
                )
                backtest_loss_chart.update_layout(
                    title="Backtesting Total Loss — Aktual vs Prediksi",
                    xaxis_title="Periode Uji",
                    yaxis_title="Loss Opportunity (Rp)",
                    hovermode="x unified",
                    height=480,
                    margin=dict(l=20, r=20, t=60, b=20),
                    legend=dict(orientation="h", y=1.10),
                )
                st.plotly_chart(
                    backtest_loss_chart,
                    use_container_width=True,
                    config=PLOTLY_CONFIG,
                )

                backtest_frequency_chart = go.Figure()
                backtest_frequency_chart.add_trace(
                    go.Bar(
                        x=plot_backtest["Periode"],
                        y=plot_backtest["Frekuensi_Aktual"],
                        name="Frekuensi Aktual",
                        marker_color="#2563EB",
                    )
                )
                backtest_frequency_chart.add_trace(
                    go.Scatter(
                        x=plot_backtest["Periode"],
                        y=plot_backtest["Frekuensi_Prediksi"],
                        mode="lines+markers",
                        name="Ekspektasi Poisson",
                        line=dict(color="#DC2626", width=3),
                    )
                )
                backtest_frequency_chart.update_layout(
                    title="Backtesting Frekuensi Kejadian Loss",
                    xaxis_title="Periode Uji",
                    yaxis_title="Jumlah Kejadian",
                    height=430,
                    margin=dict(l=20, r=20, t=60, b=20),
                    legend=dict(orientation="h", y=1.12),
                )
                st.plotly_chart(
                    backtest_frequency_chart,
                    use_container_width=True,
                    config=PLOTLY_CONFIG,
                )

                backtest_display = backtest_result.copy()
                backtest_display["Periode Uji"] = backtest_display[
                    "Periode_Uji"
                ].dt.strftime("%b %Y")
                st.dataframe(
                    backtest_display[
                        [
                            "Periode Uji",
                            "Frekuensi_Aktual",
                            "Frekuensi_Prediksi",
                            "Loss_Aktual",
                            "P50_Loss",
                            "P90_Loss",
                            "Error_P50_Pct",
                            "Actual_Percentile",
                            "P90_Covered",
                            "HOP_Proyeksi",
                            "HOP_Aktual",
                            "KRI_Prediksi",
                            "KRI_Aktual",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Frekuensi_Aktual": st.column_config.NumberColumn(
                            "Frekuensi Aktual", format="%d"
                        ),
                        "Frekuensi_Prediksi": st.column_config.NumberColumn(
                            "Frekuensi Prediksi", format="%.2f"
                        ),
                        "Loss_Aktual": st.column_config.NumberColumn(
                            "Loss Aktual", format="Rp %,.0f"
                        ),
                        "P50_Loss": st.column_config.NumberColumn(
                            "P50 Prediksi", format="Rp %,.0f"
                        ),
                        "P90_Loss": st.column_config.NumberColumn(
                            "P90 Prediksi", format="Rp %,.0f"
                        ),
                        "Error_P50_Pct": st.column_config.NumberColumn(
                            "Error P50", format="%.2f%%"
                        ),
                        "Actual_Percentile": st.column_config.NumberColumn(
                            "Actual Percentile", format="%.2f%%"
                        ),
                        "HOP_Proyeksi": st.column_config.NumberColumn(
                            "HOP Proyeksi", format="%.2f"
                        ),
                        "HOP_Aktual": st.column_config.NumberColumn(
                            "HOP Aktual", format="%.2f"
                        ),
                    },
                )

                with st.expander("Dasar dan keterbatasan backtesting"):
                    st.markdown(
                        """
- Pembagian training dan validation dilakukan berdasarkan waktu.
- Baris `AGREGAT BULANAN` tidak dihitung sebagai kejadian individual.
- Frekuensi disimulasikan dengan Poisson dan severity dengan BETA-PERT.
- HOP proyeksi memakai rata-rata 30 hari sebelum bulan uji.
- Bulan HOP yang belum lengkap tidak dijadikan periode uji.
- Hasil merupakan validasi internal awal, bukan validasi independen.
"""
                    )
    except Exception as backtest_error:
        st.error(f"Rolling backtesting gagal dijalankan: {backtest_error}")
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
            hop_chart_data = (
                filtered_hop
                .dropna(
                    subset=[
                        "Tanggal",
                        "HOP_Unit_Key",
                        "Nilai_HOP",
                    ]
                )
                .groupby(
                    [
                        "Tanggal",
                        "HOP_Unit_Key",
                    ],
                    as_index=False,
                )
                .agg(
                    Nilai_HOP=(
                        "Nilai_HOP",
                        "mean",
                    )
                )
            )

            hop_threshold_chart = (
                loss_data[
                    [
                        "HOP_Unit_Key",
                        "Batas_HOP_P20",
                    ]
                ]
                .dropna()
                .groupby(
                    "HOP_Unit_Key",
                    as_index=False,
                )
                .agg(
                    Batas_HOP_P20=(
                        "Batas_HOP_P20",
                        "median",
                    )
                )
            )

            hop_chart_data = hop_chart_data.merge(
                hop_threshold_chart,
                on="HOP_Unit_Key",
                how="left",
            )

            hop_chart_data["Status_HOP"] = "NORMAL"
            hop_chart_data.loc[
                hop_chart_data["Nilai_HOP"]
                <= hop_chart_data["Batas_HOP_P20"],
                "Status_HOP",
            ] = "RENDAH"

            chart_unit_count = (
                hop_chart_data["HOP_Unit_Key"]
                .nunique()
            )

            if chart_unit_count == 1:
                chart_unit = (
                    hop_chart_data[
                        "HOP_Unit_Key"
                    ].iloc[0]
                )

                figure_hop = px.line(
                    hop_chart_data,
                    x="Tanggal",
                    y="Nilai_HOP",
                    markers=True,
                    title=f"Tren HOP Harian – {chart_unit}",
                    labels={
                        "Tanggal": "Tanggal",
                        "Nilai_HOP": "HOP (hari)",
                    },
                    color_discrete_sequence=[
                        "#0F6CBD"
                    ],
                )

                threshold_value = (
                    hop_chart_data[
                        "Batas_HOP_P20"
                    ].dropna()
                )

                if not threshold_value.empty:
                    figure_hop.add_hline(
                        y=threshold_value.iloc[0],
                        line_dash="dash",
                        line_color="#F59E0B",
                        annotation_text="Batas HOP P20",
                        annotation_position="top left",
                    )

            elif chart_unit_count <= 8:
                figure_hop = px.line(
                    hop_chart_data,
                    x="Tanggal",
                    y="Nilai_HOP",
                    color="HOP_Unit_Key",
                    title="Tren HOP Harian per Unit",
                    labels={
                        "Tanggal": "Tanggal",
                        "Nilai_HOP": "HOP (hari)",
                        "HOP_Unit_Key": "Unit",
                    },
                )

            else:
                hop_daily_average = (
                    hop_chart_data
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
                    hop_daily_average,
                    x="Tanggal",
                    y="Nilai_HOP",
                    title=(
                        "Tren Rata-rata HOP Harian "
                        f"({chart_unit_count} Unit)"
                    ),
                    labels={
                        "Tanggal": "Tanggal",
                        "Nilai_HOP": "Rata-rata HOP (hari)",
                    },
                    color_discrete_sequence=[
                        "#0F6CBD"
                    ],
                )

            low_hop_points = hop_chart_data[
                hop_chart_data["Status_HOP"]
                == "RENDAH"
            ]

            if (
                chart_unit_count <= 8
                and not low_hop_points.empty
            ):
                figure_hop.add_scatter(
                    x=low_hop_points["Tanggal"],
                    y=low_hop_points["Nilai_HOP"],
                    mode="markers",
                    marker=dict(
                        color="#DC2626",
                        size=8,
                        symbol="circle",
                    ),
                    text=low_hop_points[
                        "HOP_Unit_Key"
                    ],
                    hovertemplate=(
                        "%{text}<br>"
                        "%{x|%d-%b-%Y}<br>"
                        "HOP: %{y:.2f}<extra>HOP rendah</extra>"
                    ),
                    name="HOP ≤ P20",
                )

            figure_hop.update_layout(
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
                theme="streamlit",
            )

            if chart_unit_count > 8:
                st.caption(
                    "Karena lebih dari 8 unit dipilih, "
                    "grafik menampilkan rata-rata HOP harian. "
                    "Pilih maksimal 8 unit untuk melihat "
                    "garis masing-masing unit dan penanda "
                    "merah saat HOP berada di bawah P20."
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


# ============================================================
# TAB LAPORAN PDF
# ============================================================

with tab_report:
    st.subheader("Laporan Lengkap PRIME-RISK")
    st.caption(
        "Buat PDF multi-halaman dari seluruh hasil utama "
        "dashboard sesuai filter dan parameter aktif."
    )

    if not REPORTLAB_AVAILABLE:
        st.error(
            "Pembuatan PDF memerlukan paket reportlab. "
            "Tambahkan `reportlab>=4.2,<5` pada requirements.txt, "
            "lalu reboot aplikasi."
        )
    else:
        report_input_col1, report_input_col2 = st.columns(2)

        with report_input_col1:
            report_title = st.text_input(
                "Judul Laporan",
                value=(
                    "Laporan Risk Model Hambatan Energi "
                    "Primer Batubara"
                ),
                key="pdf_report_title",
            )

        with report_input_col2:
            report_prepared_by = st.text_input(
                "Disusun oleh",
                value="Tim Risk Management",
                key="pdf_report_prepared_by",
            )

        st.info(
            "PDF mencakup ringkasan eksekutif, KRI HOP, "
            "analisis HOP-Loss, Monte Carlo, prediksi risiko, "
            "heat map, rekomendasi, dan metodologi."
        )

        if st.button(
            "Buat Laporan PDF Lengkap",
            type="primary",
            use_container_width=True,
        ):
            kri_report_rows = []
            if "kri_unit" in locals() and not kri_unit.empty:
                kri_report_source = (
                    kri_unit.assign(
                        _Prioritas=kri_unit["Status_KRI"].map(
                            {
                                "EMERGENCY": 1,
                                "SIAGA": 2,
                                "NORMAL": 3,
                            }
                        )
                    )
                    .sort_values(
                    ["_Prioritas", "HOP_Terakhir"],
                    ascending=[True, True],
                    )
                    .drop(columns="_Prioritas")
                )
                for _, row in kri_report_source.iterrows():
                    trend_value = row["Tren_7_Observasi"]
                    kri_report_rows.append(
                        [
                            row["HOP_Unit_Key"],
                            pd.to_datetime(
                                row["Tanggal_Terakhir"]
                            ).strftime("%d-%b-%Y"),
                            f"{row['HOP_Terakhir']:,.2f}",
                            row["Status_KRI"],
                            (
                                f"{trend_value:+,.2f}"
                                if pd.notna(trend_value)
                                else "-"
                            ),
                        ]
                    )

            hop_report_rows = []
            if (
                "hop_loss_summary" in locals()
                and not hop_loss_summary.empty
            ):
                for _, row in hop_loss_summary.iterrows():
                    hop_report_rows.append(
                        [
                            row["Status_HOP_Analisis"],
                            f"{int(row['Observasi_Hari']):,}",
                            f"{int(row['Hari_Dengan_Loss']):,}",
                            f"{row['Jumlah_Kejadian_Loss']:,.0f}",
                            f"{row['Probabilitas_Loss']:.2%}",
                            format_compact_rupiah(
                                row[
                                    "Total_Loss_Opportunity_Rp"
                                ]
                            ),
                        ]
                    )

            monte_report_rows = []
            if report_monte_carlo:
                monte_report_rows = [
                    [
                        "Ekspektasi frekuensi tahunan",
                        f"{report_monte_carlo['expected_frequency']:,.2f}",
                    ],
                    [
                        "Mean annual loss",
                        format_compact_rupiah(
                            report_monte_carlo["mean"]
                        ),
                    ],
                    [
                        "P50 annual loss",
                        format_compact_rupiah(
                            report_monte_carlo["p50"]
                        ),
                    ],
                    [
                        "P90 annual loss",
                        format_compact_rupiah(
                            report_monte_carlo["p90"]
                        ),
                    ],
                    [
                        "P95 annual loss",
                        format_compact_rupiah(
                            report_monte_carlo["p95"]
                        ),
                    ],
                    [
                        "P90 terhadap Risk Limit",
                        f"{report_monte_carlo['p90_ratio']:.2%}",
                    ],
                    [
                        (
                            "Peluang loss melampaui "
                            f"{report_monte_carlo['exceedance_percent']}% "
                            "Risk Limit"
                        ),
                        (
                            f"{report_monte_carlo['exceedance_probability']:.2%}"
                        ),
                    ],
                ]

            prediction_report_rows = []
            if report_prediction:
                prediction_report_rows = [
                    ["Unit", report_prediction["unit"]],
                    [
                        "Periode",
                        (
                            f"{report_prediction['start']:%d-%b-%Y} "
                            f"s.d. {report_prediction['end']:%d-%b-%Y}"
                        ),
                    ],
                    [
                        "Durasi",
                        f"{report_prediction['days']:,} hari kalender",
                    ],
                    [
                        "Proyeksi HOP",
                        (
                            f"{report_prediction['projected_hop']:,.2f} hari "
                            f"({report_prediction['status']})"
                        ),
                    ],
                    [
                        "Ekspektasi kejadian",
                        f"{report_prediction['expected_frequency']:,.2f}",
                    ],
                    [
                        "Peluang minimal satu kejadian",
                        f"{report_prediction['probability']:.2%}",
                    ],
                    [
                        "P50 predicted loss",
                        format_compact_rupiah(
                            report_prediction["p50"]
                        ),
                    ],
                    [
                        "P90 predicted loss",
                        format_compact_rupiah(
                            report_prediction["p90"]
                        ),
                    ],
                    [
                        "P95 predicted loss",
                        format_compact_rupiah(
                            report_prediction["p95"]
                        ),
                    ],
                    [
                        "Faktor kemungkinan",
                        (
                            f"{report_prediction['likelihood_letter']} "
                            f"({report_prediction['likelihood_score']})"
                        ),
                    ],
                    [
                        "Faktor dampak",
                        str(report_prediction["impact_score"]),
                    ],
                    [
                        "Nilai dan level risiko",
                        (
                            f"{report_prediction['risk_score']} - "
                            f"{report_prediction['risk_level']}"
                        ),
                    ],
                ]

            category_report_rows = []
            if not report_category_risk.empty:
                for _, row in report_category_risk.iterrows():
                    category_report_rows.append(
                        [
                            row["Kode"],
                            row["Kategori_Final"],
                            f"{row['Jumlah_Kejadian']:,.0f}",
                            format_compact_rupiah(
                                row["Total_Loss_Rp"]
                            ),
                            f"{row['Rasio_Risk_Limit']:.2%}",
                            str(int(row["Skala_Kemungkinan"])),
                            str(int(row["Skala_Dampak"])),
                            str(int(row["Nilai_Risiko"])),
                            row["Level_Risiko"],
                        ]
                    )

            report_payload = {
                "title": report_title,
                "prepared_by": report_prepared_by,
                "report_date": date.today().strftime("%d-%b-%Y"),
                "filter_years": (
                    ", ".join(map(str, selected_years))
                    if selected_years
                    else "Semua tahun"
                ),
                "filter_units": (
                    ", ".join(selected_units)
                    if selected_units
                    else "Semua unit"
                ),
                "risk_limit": format_compact_rupiah(
                    risk_limit_rp
                ),
                "summary_rows": [
                    ["Jumlah Kejadian Loss", f"{total_loss_events:,}"],
                    [
                        "Loss Production",
                        f"{total_loss_production:,.3f} MWh",
                    ],
                    [
                        "Loss Opportunity",
                        format_compact_rupiah(
                            total_loss_opportunity
                        ),
                    ],
                    [
                        "Total data HOP",
                        f"{total_hop_records:,}",
                    ],
                    [
                        "Data HOP sesuai filter",
                        f"{filtered_hop_records:,}",
                    ],
                ],
                "kri_rows": kri_report_rows,
                "hop_loss_rows": hop_report_rows,
                "monte_rows": monte_report_rows,
                "prediction_rows": prediction_report_rows,
                "prediction_likelihood": (
                    report_prediction.get("likelihood_score")
                    if report_prediction
                    else None
                ),
                "prediction_impact": (
                    report_prediction.get("impact_score")
                    if report_prediction
                    else None
                ),
                "recommendation": (
                    report_prediction.get("recommendation", "-")
                    if report_prediction
                    else "-"
                ),
                "category_rows": category_report_rows,
            }

            try:
                st.session_state["prime_risk_pdf"] = (
                    build_prime_risk_pdf(report_payload)
                )
                st.session_state["prime_risk_pdf_name"] = (
                    "PRIME_RISK_Report_"
                    + date.today().strftime("%Y%m%d")
                    + ".pdf"
                )
                st.success(
                    "Laporan PDF berhasil dibuat."
                )
            except Exception as report_error:
                st.error(
                    "Laporan belum berhasil dibuat: "
                    + str(report_error)
                )

        if st.session_state.get("prime_risk_pdf"):
            st.download_button(
                "Unduh Laporan PDF",
                data=st.session_state["prime_risk_pdf"],
                file_name=st.session_state.get(
                    "prime_risk_pdf_name",
                    "PRIME_RISK_Report.pdf",
                ),
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )

with tab_method:
    st.markdown(
        """
### Identitas model

**PRIME-RISK** merupakan singkatan dari **Primary Energy
Risk Intelligence, Modelling & Evaluation**. Model ini
mengubah data HOP dan Kejadian Loss menjadi informasi
frekuensi, severity, distribusi kerugian, probability of
exceedance, dan posisi risiko pada heat map.

### Definisi Kejadian Loss

**Kejadian Loss** adalah satu rangkaian kejadian risiko
yang menimbulkan kehilangan produksi atau kehilangan
peluang pendapatan.

Beberapa segmen KKP/PLO yang masih merupakan satu
rangkaian kejadian dapat digabungkan menjadi satu
Kejadian Loss. Tujuannya adalah mencegah penghitungan
frekuensi secara berlebihan atau *double counting*.

### Struktur data

1. `Loss_Event_Detail_v2` berfungsi sebagai sumber
   transaksi event-level dan audit trail.
2. Lapisan transformasi Python membentuk kolom kalender,
   identitas kejadian, dan status kesiapan model.
3. `HOP_Harian` berisi kondisi Hari Operasi
   Persediaan per unit.
4. `Kejadian_Loss_ID` menjadi identitas unik setiap
   Kejadian Loss.
5. Jika `Kejadian_Loss_ID` belum tersedia, aplikasi
   menggunakan `Event_ID` sebagai identitas sementara.

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
    "PRIME-RISK · Primary Energy Risk Intelligence, "
    "Modelling & Evaluation · "
    "Sumber data Google Sheet publik · "
    f"Versi {APP_VERSION}"
)
