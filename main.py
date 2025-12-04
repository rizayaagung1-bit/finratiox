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
    df.columns = ["col1", "Account", "Value"]  # Sesuaikan kolom
    df["Account"] = df["Account"].astype(str).str.lower()

    # Mapping pencarian
    def find_value(keyword):
        row = df[df["Account"].str.contains(keyword)]
        if len(row) == 0:
            return None
        return float(row["Value"].values[0])

    current_assets = find_value("current assets")
    current_liabilities = find_value("current liabilities")
    total_assets = find_value("total assets")
    total_liabilities = find_value("total liabilities")
    total_equity = find_value("total equity")
    net_income = find_value("net income")

    # Tampilkan hasil ekstraksi
    st.subheader("Hasil Ekstraksi")
    st.write({
        "Current Assets": current_assets,
        "Current Liabilities": current_liabilities,
        "Total Assets": total_assets,
        "Total Liabilities": total_liabilities,
        "Total Equity": total_equity,
        "Net Income": net_income,
    })

    # --- Hitung Rasio ---
    st.subheader("Rasio Keuangan")

    def safe_div(a, b):
        if a is None or b is None or b == 0:
            return None
        return a / b

    current_ratio = safe_div(current_assets, current_liabilities)
    der = safe_div(total_liabilities, total_equity)
    roa = safe_div(net_income, total_assets)
    roe = safe_div(net_income, total_equity)

    ratios = {
        "Current Ratio": current_ratio,
        "DER (Debt to Equity)": der,
        "ROA": roa,
        "ROE": roe
    }

    st.write(ratios)

    # --- Analisis ---
    st.subheader("Analisis Otomatis")

    analysis = []

    if current_ratio:
        if current_ratio >= 1.5:
            analysis.append(f"Current Ratio {current_ratio:.2f} → Likuiditas sangat baik.")
        elif current_ratio >= 1.0:
            analysis.append(f"Current Ratio {current_ratio:.2f} → Likuiditas cukup.")
        else:
            analysis.append(f"Current Ratio {current_ratio:.2f} → Likuiditas rendah.")

    if der:
        if der < 1:
            analysis.append(f"DER {der:.2f} → Leverage rendah, risiko kecil.")
        elif der <= 2:
            analysis.append(f"DER {der:.2f} → Leverage sedang.")
        else:
            analysis.append(f"DER {der:.2f} → Leverage tinggi, perlu antisipasi risiko.")

    if roa:
        analysis.append(f"ROA {roa:.2%} → Efisiensi penggunaan aset.")

    if roe:
        analysis.append(f"ROE {roe:.2%} → Pengembalian modal pemilik baik.")

    st.write(analysis)

    # --- Grafik ---
    st.subheader("Visualisasi Rasio")

    numeric_ratios = {k: v for k, v in ratios.items() if v is not None}

    if numeric_ratios:
        chart_df = pd.DataFrame(
            {"Rasio": list(numeric_ratios.keys()),
             "Nilai": list(numeric_ratios.values())}
        )
        st.bar_chart(chart_df.set_index("Rasio"))
    else:
        st.write("Tidak ada rasio yang bisa divisualisasikan.")
