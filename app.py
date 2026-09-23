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
