import streamlit as st
import pandas as pd
import io
from utils.ratios import current_ratio, debt_to_equity, roa, roe

st.set_page_config(layout="wide")
st.title("FinRatioX — Debug & Ekstraksi Otomatis")

uploaded = st.file_uploader("Upload file Excel", type=["xlsx"])
if not uploaded:
    st.info("Silakan upload file Excel (.xlsx) untuk menguji ekstraksi.")
else:
    st.success("File berhasil di-upload!")
    st.write("Nama file:", uploaded.name)

    # 1) Tampilkan daftar sheet dan preview
    try:
        xls = pd.read_excel(io.BytesIO(uploaded.getvalue()), sheet_name=None)
    except Exception as e:
        st.error(f"Gagal membaca file Excel: {e}")
        raise

    st.subheader("Sheet terdeteksi")
    sheet_names = list(xls.keys())
    st.write(sheet_names)

    for name, df in xls.items():
        st.markdown(f"**Sheet:** `{name}` — preview 10 baris")
        st.dataframe(df.head(10))

    # 2) Cari nilai penting dengan keyword matching
    # keywords mapping (toleran)
    key_map = {
        "current_assets": ["current asset", "current assets", "current_assets", "aset lancar", "aset_lancar"],
        "current_liabilities": ["current liability", "current liabilities", "current_liabilities", "liabilitas lancar", "liabilitas_lancar"],
        "total_assets": ["total asset", "total assets", "total_assets", "total aset", "total_aset"],
        "total_liabilities": ["total liability", "total liabilities", "total_liabilities", "total liabilitas", "total_liabilitas"],
        "total_equity": ["total equity", "total_equity", "ekuitas", "modal", "total equity (owner)"],
        "net_income": ["net income", "net_income", "laba bersih", "laba_bersih", "profit", "net profit"]
    }

    def try_parse_number(x):
        if pd.isna(x): return None
        s = str(x).replace(",", "").replace("(", "-").replace(")", "").strip()
        import re
        s = re.sub(r"[^\d\.\-]", "", s)
        try:
            return float(s)
        except:
            return None

    found = {}
    # iterate sheets to find keywords in any cell of first column and also column headers
    for name, df in xls.items():
        # normalize all values to str for searching
        df_str = df.astype(str).fillna("").applymap(lambda v: v.lower())
        # check headers first
        for col in df.columns:
            col_low = str(col).lower()
            for std, kws in key_map.items():
                if std in found: continue
                for kw in kws:
                    if kw in col_low:
                        # try find numeric in that column's first non-empty cell
                        for val in df[col].tolist():
                            num = try_parse_number(val)
                            if num is not None:
                                found[std] = num
                                break
        # check rows (assume possible layout: Account | Value)
        if df.shape[1] >= 2:
            first_col = df.columns[0]
            for i, cell in enumerate(df[first_col].astype(str).tolist()):
                cell_low = cell.lower()
                for std, kws in key_map.items():
                    if std in found: continue
                    for kw in kws:
                        if kw in cell_low:
                            # look for numeric in the remaining columns of that row
                            for c in df.columns[1:]:
                                num = try_parse_number(df.iloc[i][c])
                                if num is not None:
                                    found[std] = num
                                    break
                            if std in found:
                                break

    st.subheader("Hasil ekstraksi (ditemukan)")
    st.json(found)

    # 3) Hitung rasio jika data cukup
    ca = found.get("current_assets")
    cl = found.get("current_liabilities")
    ta = found.get("total_assets")
    tl = found.get("total_liabilities")
    te = found.get("total_equity")
    ni = found.get("net_income")

    ratios = {
        "current_ratio": current_ratio(ca, cl) if (ca is not None or cl is not None) else None,
        "debt_to_equity": debt_to_equity(tl, te) if (tl is not None or te is not None) else None,
        "roa": roa(ni, ta) if (ni is not None or ta is not None) else None,
        "roe": roe(ni, te) if (ni is not None or te is not None) else None
    }

    st.subheader("Rasio (dihitung)")
    st.write(ratios)

    # 4) Visualisasi sederhana (bar chart untuk rasio yang terisi)
    import pandas as pd
    df_rat = pd.DataFrame(
        [(k, v) for k, v in ratios.items() if v is not None],
        columns=["ratio", "value"]
    )
    if not df_rat.empty:
        st.bar_chart(df_rat.set_index("ratio"))
    else:
        st.info("Tidak ada rasio yang cukup data untuk divisualisasikan. Pastikan file Excel memuat minimal satu period Balance Sheet dan Income Statement dengan field yang sesuai.")
