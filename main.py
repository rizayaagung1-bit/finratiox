import streamlit as st
import pandas as pd
import io
import re
import os
import requests
import math

st.set_page_config(page_title="FinRatioX — Single Sheet Robust", layout="wide")
st.title("FinRatioX — Ekstraksi & Analisis (Single Sheet)")

uploaded = st.file_uploader("Upload file Excel (.xlsx) (sheet ringkasan di sheet pertama)", type=["xlsx"])
if not uploaded:
    st.info("Silakan upload file Excel (.xlsx) terlebih dahulu.")
    st.stop()

# --- Baca file Excel dengan aman ---
try:
    xls = pd.read_excel(io.BytesIO(uploaded.getvalue()), sheet_name=None)
except Exception as e:
    st.error("Gagal membaca file Excel: " + str(e))
    st.stop()

# pastikan ada sheet di xls
if not xls or len(xls) == 0:
    st.error("File Excel tidak berisi sheet yang bisa dibaca.")
    st.stop()

# ambil sheet pertama (robust)
sheet_name = list(xls.keys())[0]
sheet0 = xls[sheet_name].copy()

st.subheader(f"Sheet: {sheet_name}")
st.dataframe(sheet0.head(12))

# ---------- Tentukan kolom Account & Value secara robust ----------
def find_account_value_cols(df):
    cols = list(df.columns)
    account_col = None
    value_col = None
    # 1) cari berdasarkan nama kolom
    for c in cols:
        low = str(c).lower()
        if any(k in low for k in ["account", "akun", "description", "nama", "item", "label"]):
            account_col = c
        if any(k in low for k in ["value", "amount", "nilai", "value (id)", "amount (id)"]):
            value_col = c
    # 2) kalau belum ketemu, scan beberapa baris untuk menemukan kata-kata khas di sel
    if account_col is None:
        for c in cols:
            sample = " ".join(df[c].astype(str).head(8).str.lower().tolist())
            if any(k in sample for k in ["current assets", "current liabilities", "total assets", "total liabilities", "total equity", "net income", "laba"]):
                account_col = c
                break
    # 3) fallback posisi kolom (umumnya data contoh: kolom ke-2 = account, kolom ke-3 = value)
    if account_col is None and len(cols) >= 2:
        account_col = cols[1]
    if value_col is None and len(cols) >= 3:
        value_col = cols[2]
    if value_col is None and len(cols) == 2:
        value_col = cols[1]
    # final fallback: first & second
    if account_col is None and len(cols) >= 1:
        account_col = cols[0]
    if value_col is None and len(cols) >= 2:
        value_col = cols[1]
    return account_col, value_col

acct_col, val_col = find_account_value_cols(sheet0)
st.write("Detected account column:", acct_col, "| detected value column:", val_col)

# Build key-value cleaned table
df_kv = sheet0[[acct_col, val_col]].copy()
df_kv.columns = ["Account", "Value"]
# drop rows where Account is blank or nan
df_kv["Account_str"] = df_kv["Account"].astype(str).str.strip()
df_kv = df_kv[df_kv["Account_str"].str.strip() != ""].reset_index(drop=True)

# parse number function (robust)
def parse_number(x):
    if pd.isna(x):
        return None
    s = str(x)
    # replace parentheses with negative sign, remove thousand separators (commas or dots)
    s = s.replace("(", "-").replace(")", "").replace(",", "").strip()
    # Sometimes dots are thousand separators; try to extract contiguous digits including possible minus
    m = re.search(r"-?\d+", s.replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except:
        return None

df_kv["ParsedValue"] = df_kv["Value"].apply(parse_number)
# show cleaned table
st.subheader("Table extracted (Account | Value | ParsedValue)")
display_df = df_kv[["Account_str", "Value", "ParsedValue"]].rename(columns={"Account_str":"Account"})
display_df["ParsedValue_fmt"] = display_df["ParsedValue"].apply(lambda v: f"{int(v):,}" if (v is not None and not pd.isna(v)) else "N/A")
st.dataframe(display_df.reset_index(drop=True))

# ---------- keyword search ----------
keywords = {
    "current_assets": ["current asset", "current assets", "aset lancar", "kas dan setara kas", "cash and cash equivalents", "kas"],
    "current_liabilities": ["current liabilities", "current liability", "liabilitas lancar", "hutang jangka pendek", "utang lancar", "utang"],
    "total_assets": ["total assets", "total asset", "total aset", "jumlah aset"],
    "total_liabilities": ["total liabilities", "total liability", "total liabilitas", "jumlah liabilitas"],
    "total_equity": ["total equity", "total ekuitas", "ekuitas", "modal saham", "jumlah ekuitas"],
    "net_income": ["net income", "laba bersih", "profit for the year", "laba tahun berjalan", "net profit"]
}

def norm(s): 
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()

found = {}
found_context = {}
for metric, kwlist in keywords.items():
    for kw in kwlist:
        nk = norm(kw)
        for idx, row in df_kv.iterrows():
            label_norm = norm(row["Account"])
            if nk in label_norm or label_norm in nk:
                val = row["ParsedValue"]
                if val is not None:
                    found[metric] = val
                    found_context[metric] = {"value": val, "raw_label": row["Account"], "row_index": idx}
                    break
        if metric in found:
            break

st.subheader("Hasil Ekstraksi (detected)")
if found:
    nice = {k: (f"{v:,.0f}" if v is not None else "N/A") for k, v in found.items()}
    st.json(nice)
else:
    st.write("Tidak ada metric otomatis terdeteksi.")

# ---------- manual mapping for missing metrics ----------
required = ["current_assets","current_liabilities","total_assets","total_liabilities","total_equity","net_income"]
missing = [m for m in required if m not in found]
if missing:
    st.warning("Beberapa metric belum otomatis terdeteksi: " + ", ".join(missing))

if missing:
    st.subheader("Manual mapping (pilih baris jika otomatis gagal)")
    choices = [f"Row {i+1}: {row['Account']}" for i, row in df_kv.iterrows()]
    manual = {}
    for m in missing:
        sel = st.selectbox(f"Pilih baris untuk {m} (atau pilih '(skip)')", ["(skip)"] + choices, key=m)
        if sel != "(skip)":
            idx = choices.index(sel)
            manual[m] = df_kv.at[idx, "ParsedValue"]
    # merge manual
    for k, v in manual.items():
        found[k] = v

# ---------- Final extracted values ----------
final_labels = {
    "current_assets":"Current Assets",
    "current_liabilities":"Current Liabilities",
    "total_assets":"Total Assets",
    "total_liabilities":"Total Liabilities",
    "total_equity":"Total Equity",
    "net_income":"Net Income"
}
final_rows = []
for key, label in final_labels.items():
    val = found.get(key)
    source = found_context.get(key, {}).get("raw_label", "")
    final_rows.append({"Metric": label, "Value": (f"{int(val):,}" if val is not None else "N/A"), "Value_raw": val, "Source": source})
final_df = pd.DataFrame(final_rows)
st.subheader("Final extracted values (clearly shown)")
st.table(final_df[["Metric","Value","Source"]])

# ---------- compute ratios ----------
def safe_div(a, b):
    try:
        if a is None or b is None or b == 0:
            return None
        return a / b
    except:
        return None

ca = found.get("current_assets")
cl = found.get("current_liabilities")
ta = found.get("total_assets")
tl = found.get("total_liabilities")
te = found.get("total_equity")
ni = found.get("net_income")

cr = safe_div(ca, cl)
der = safe_div(tl, te)
roa = safe_div(ni, ta)
roe = safe_div(ni, te)

st.subheader("Rasio yang dihitung")
ratios = {
    "Current Ratio": cr,
    "Debt-to-Equity (DER)": der,
    "ROA": roa,
    "ROE": roe
}
st.write(ratios)

# ---------- analysis ----------
st.subheader("Analisis Singkat (rule-based)")
analysis = []
if cr is None:
    analysis.append("Current Ratio: Tidak cukup data.")
else:
    if cr >= 1.5:
        analysis.append(f"Current Ratio {cr:.2f} → Likuiditas baik.")
    elif cr >= 1.0:
        analysis.append(f"Current Ratio {cr:.2f} → Likuiditas moderat.")
    else:
        analysis.append(f"Current Ratio {cr:.2f} → Likuiditas rendah.")

if der is None:
    analysis.append("DER: Tidak cukup data.")
else:
    if der < 1:
        analysis.append(f"DER {der:.2f} → Leverage rendah.")
    elif der <= 2:
        analysis.append(f"DER {der:.2f} → Leverage sedang.")
    else:
        analysis.append(f"DER {der:.2f} → Leverage tinggi — perhatikan risiko.")

if roa is None:
    analysis.append("ROA: Tidak cukup data.")
else:
    analysis.append(f"ROA {roa:.2%} → Efisiensi penggunaan aset.")

if roe is None:
    analysis.append("ROE: Tidak cukup data.")
else:
    analysis.append(f"ROE {roe:.2%} → Pengembalian terhadap modal pemilik.")

for line in analysis:
    st.write("- " + line)

# ---------- visualization ----------
st.subheader("Visualisasi Rasio")
num_ratios = {k: v for k, v in ratios.items() if v is not None and not (isinstance(v, float) and math.isnan(v))}
if num_ratios:
    chart_df = pd.DataFrame({"Rasio": list(num_ratios.keys()), "Nilai": list(num_ratios.values())})
    st.bar_chart(chart_df.set_index("Rasio"))
else:
    st.info("Tidak ada rasio numerik yang cukup untuk divisualisasikan.")

# Optional Grok integration (if configured)
if os.getenv("GROK_API_KEY") and os.getenv("GROK_API_URL"):
    if st.button("Interpretasi otomatis via Grok"):
        payload = {
            "prompt": "You are an accounting analyst. Given the following ratios, provide JSON with interpretation, risk level (Low/Medium/High) and 2 recommended actions for each ratio.\n"
                      + "\n".join([f"- {k}: {v}" for k, v in ratios.items()]) + "\nReturn only JSON.",
            "max_tokens": 300,
            "temperature": 0.1
        }
        headers = {"Authorization": f"Bearer {os.getenv('GROK_API_KEY')}", "Content-Type": "application/json"}
        try:
            r = requests.post(os.getenv("GROK_API_URL"), json=payload, headers=headers, timeout=20)
            r.raise_for_status()
            st.subheader("Hasil interpretasi Grok")
            st.write(r.text)
        except Exception as e:
            st.error("Grok request failed: " + str(e))
else:
    st.info("Grok tidak dikonfigurasi. Tambahkan GROK_API_KEY & GROK_API_URL di environment variables jika mau pakai interpretasi AI.")
