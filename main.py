import streamlit as st
import pandas as pd
import io

st.title("FinRatioX — Dashboard Rasio Keuangan Otomatis")

uploaded = st.file_uploader("Upload file Excel", type=["xlsx"])

if uploaded:
    st.success("File berhasil di-upload!")

    # Membaca semua sheet
    xls = pd.read_excel(uploaded, sheet_name=None)
    st.write("Detected sheets:", list(xls.keys()))

    # Tampilkan preview sheet
    for name, df in xls.items():
        st.write(f"Sheet: {name}")
        st.dataframe(df.head())

    # --- Ekstraksi nilai dari tabel dua kolom ---
    df = list(xls.values())[0]   # Ambil sheet pertama
    df.columns = ["col1", "Account", "Value"]  # S
