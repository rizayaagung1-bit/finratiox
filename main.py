import streamlit as st

st.title("FinRatioX — Dashboard Rasio Keuangan Otomatis")

st.write("Silakan upload file Excel laporan keuangan Anda.")

# Upload file
uploaded = st.file_uploader("Upload file Excel", type=["xlsx"])

if uploaded:
    st.success("File berhasil di-upload!")
    st.write("Nama file:", uploaded.name)
