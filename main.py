import streamlit as st

st.title("FinRatioX — Dashboard Rasio Keuangan Otomatis")

st.write("Silakan upload file Excel laporan keuangan Anda.")
uploaded = st.file_uploader("Upload file Excel", type=["xlsx"]
