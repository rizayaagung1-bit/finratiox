# === REPLACE THE EXTRACTION DISPLAY BLOCK IN main.py WITH THIS ===
import streamlit as st
import pandas as pd
import io
import re

# assume 'xls' and 'sheet_names' already loaded earlier; otherwise load:
# xls = pd.read_excel(io.BytesIO(uploaded.getvalue()), sheet_name=None)
# sheet_names = list(xls.keys())

sheet0 = list(xls.values())[0].copy()

st.subheader("Sheet: " + list(xls.keys())[0])
st.dataframe(sheet0.head(12))  # show raw preview

# ---------- robustly find Account and Value columns ----------
def find_account_value_cols(df):
    cols = list(df.columns)
    account_col = None
    value_col = None
    # try to find header names containing keywords
    for c in cols:
        low = str(c).lower()
        if any(k in low for k in ["account", "akun", "description", "nama", "item"]):
            account_col = c
        if any(k in low for k in ["value", "amount", "nilai", "value (id)", "value"]):
            value_col = c
    # if not found, try scanning first few rows to detect 'Account' text in cell values (header might be missing)
    if account_col is None:
        for c in cols:
            # check first 6 rows for the word 'account' or keywords
            sample = " ".join(df[c].astype(str).head(6).str.lower().tolist())
            if any(k in sample for k in ["account", "current assets", "total assets", "current liabilities", "total liabilities", "total equity", "net income", "laba"]):
                account_col = c
                break
    # fallback to column index positions (most of your files use second and third cols)
    if account_col is None and len(cols) >= 2:
        account_col = cols[1]
    if value_col is None and len(cols) >= 3:
        value_col = cols[2]
    # final fallback: second col as value if only 2 columns present
    if value_col is None and len(cols) == 2:
        value_col = cols[1]
    return account_col, value_col

acct_col, val_col = find_account_value_cols(sheet0)
st.write("Detected account column:", acct_col, " | value column:", val_col)

# build cleaned KV table
df_kv = sheet0[[acct_col, val_col]].copy()
df_kv.columns = ["Account", "Value"]
# drop rows where Account is blank
df_kv["Account_str"] = df_kv["Account"].astype(str).str.strip()
df_kv = df_kv[df_kv["Account_str"].str.strip() != ""].reset_index(drop=True)

# parse numeric values with robust parser
def parse_number(x):
    if pd.isna(x):
        return None
    s = str(x)
    # convert parentheses (negative), remove spaces and thousands separators
    s = s.replace("(", "-").replace(")", "").replace(".", "").replace(",", "").strip()
    # keep digits and minus
    m = re.search(r"-?\d+", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except:
        return None

df_kv["ParsedValue"] = df_kv["Value"].apply(parse_number)

# show cleaned table
st.subheader("Table extracted (Account | Value | ParsedValue)")
# format ParsedValue with thousands separators for readability
display_df = df_kv[["Account_str", "Value", "ParsedValue"]].rename(columns={"Account_str":"Account"})
display_df["ParsedValue_fmt"] = display_df["ParsedValue"].apply(lambda v: f"{int(v):,}" if (v is not None and not pd.isna(v)) else "N/A")
st.dataframe(display_df.reset_index(drop=True))

# ---------- search for required metrics ----------
keywords = {
    "current_assets": ["current asset", "current assets", "aset lancar", "kas dan setara kas", "cash and cash equivalents", "kas"],
    "current_liabilities": ["current liabilities", "current liability", "liabilitas lancar", "hutang jangka pendek", "utang lancar", "utang"],
    "total_assets": ["total assets", "total asset", "total aset", "jumlah aset", "total assets (net)"],
    "total_liabilities": ["total liabilities", "total liability", "total liabilitas", "jumlah liabilitas"],
    "total_equity": ["total equity", "total ekuitas", "ekuitas", "modal saham", "jumlah ekuitas"],
    "net_income": ["net income", "laba bersih", "profit for the year", "laba tahun berjalan", "net profit", "profit"]
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

# present what was found and which metrics missing
st.subheader("Hasil Ekstraksi (detected)")
if found:
    # nicely formatted
    nice = {k: (f"{v:,.0f}" if v is not None else "N/A") for k, v in found.items()}
    st.json(nice)
else:
    st.write("Tidak ada metric otomatis terdeteksi.")

missing = [m for m in ["current_assets","current_liabilities","total_assets","total_liabilities","total_equity","net_income"] if m not in found]
if missing:
    st.warning("Beberapa metric belum otomatis terdeteksi: " + ", ".join(missing))

# ---------- allow manual mapping for any missing metric ----------
if missing:
    st.subheader("Manual mapping (pilih baris jika otomatis gagal)")
    choices = [f"Row {i+1}: {row['Account']}" for i, row in df_kv.iterrows()]
    manual = {}
    for m in missing:
        sel = st.selectbox(f"Pilih baris untuk {m} (atau biarkan kosong)", ["(skip)"] + choices, key=m)
        if sel != "(skip)":
            idx = choices.index(sel)
            manual[m] = df_kv.at[idx, "ParsedValue"]

    # merge manual values into found
    for k, v in manual.items():
        found[k] = v

# ---------- Final values table ----------
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

# now you can compute ratios using final_df["Value_raw"]
