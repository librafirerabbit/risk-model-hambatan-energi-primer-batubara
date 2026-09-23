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


APP_VERSION = "2026.09.23-loss-event-detail-v2-v16"

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
