# main.py
import streamlit as st
import pandas as pd
import io
import re
import os
import requests
import math
from typing import Optional

st.set_page_config(page_title="FinRatioX — Robust single-sheet", layout="wide")
st.title("FinRatioX — Ekstraksi, Rasio & Interpretasi (Robust)")

# -------------------
# Utility functions
# -------------------
def safe_parse_number(x):
    if pd.isna(x):
        return None
    s = str(x)
    # parentheses -> negative
    s = s.replace("(", "-").replace(")", "").replace(",", "").strip()
    # find first numeric group
    m = re.search(r"-?\d+", s.replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except:
        return None

def safe_div(a, b):
    try:
        if a is None or b is None:
            return None
        if b == 0:
            return None
        return a / b
    except:
        return None

def norm(s: str):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()

def local_rule_based_analysis(ratios: dict) -> list:
    # ratios: {"Current Ratio": val, ...}
    out = []
    cr = ratios.get("Current Ratio")
    der = ratios.get("Debt-to-Equity (DER)")
    roa = ratios.get("ROA")
    roe = ratios.get("ROE")

    if cr is None:
        out.append("Current Ratio: Tidak cukup data untuk menghitung.")
    else:
        if cr >= 1.5:
            out.append(f"Current Ratio {cr:.2f}: Likuiditas baik (cukup untuk kewajiban jangka pendek).")
        elif cr >= 1.0:
            out.append(f"Current Ratio {cr:.2f}: Likuiditas moderat; perbaikan manajemen kas dianjurkan.")
        else:
            out.append(f"Current Ratio {cr:.2f}: Likuiditas rendah; risiko kesulitan pembayaran jangka pendek.")

    if der is None:
        out.append("DER: Tidak cukup data.")
    else:
        if der < 1:
            out.append(f"DER {der:.2f}: Leverage rendah.")
        elif der <= 2:
            out.append(f"DER {der:.2f}: Leverage sedang; pantau arus kas.")
        else:
            out.append(f"DER {der:.2f}: Leverage tinggi; pertimbangkan strategi pengurangan utang atau refinancing.")

    if roa is None:
        out.append("ROA: Tidak cukup data.")
    else:
        out.append(f"ROA {roa:.2%}: Efisiensi penggunaan aset.")

    if roe is None:
        out.append("ROE: Tidak cukup data.")
    else:
        out.append(f"ROE {roe:.2%}: Pengembalian atas ekuitas.")

    return out

# -------------------
# Upload & read
# -------------------
uploaded = st.file_uploader("Upload file Excel (.xlsx) — gunakan sheet ringkasan (satu sheet) jika memungkinkan", type=["xlsx"])
if not uploaded:
    st.info("Silakan upload file Excel terlebih dahulu.")
    st.stop()

# Read all sheets safely
try:
    xls = pd.read_excel(io.BytesIO(uploaded.getvalue()), sheet_name=None)
except Exception as e:
    st.error("Gagal membaca file Excel: " + str(e))
    st.stop()

if not xls or len(xls) == 0:
    st.error("File Excel tidak mengandung sheet yang bisa dibaca.")
    st.stop()

sheet_name = list(xls.keys())[0]
sheet0 = xls[sheet_name].copy()
st.subheader(f"Sheet: {sheet_name}")
st.dataframe(sheet0.head(12))

# -------------------
# Detect account/value columns robustly
# -------------------
def find_account_value_cols(df: pd.DataFrame):
    cols = list(df.columns)
    account_col = None
    value_col = None
    # search by header name
    for c in cols:
        low = str(c).lower()
        if any(k in low for k in ["account", "akun", "description", "nama", "item", "label"]):
            account_col = c
        if any(k in low for k in ["value", "amount", "nilai", "value (id)", "jumlah"]):
            value_col = c
    # scan early rows if not found
    if account_col is None:
        for c in cols:
            sample = " ".join(df[c].astype(str).head(8).str.lower().tolist())
            if any(k in sample for k in ["current assets", "current liabilities", "total assets", "total liabilities", "total equity", "net income", "laba"]):
                account_col = c
                break
    # common fallback positions
    if account_col is None and len(cols) >= 2:
        account_col = cols[1]
    if value_col is None and len(cols) >= 3:
        value_col = cols[2]
    if value_col is None and len(cols) == 2:
        value_col = cols[1]
    # last fallback: first and second
    if account_col is None and len(cols) >= 1:
        account_col = cols[0]
    if value_col is None and len(cols) >= 2:
        value_col = cols[1]
    return account_col, value_col

acct_col, val_col = find_account_value_cols(sheet0)
st.write(f"Detected columns -> Account: `{acct_col}` | Value: `{val_col}`")

# Build key-value table
try:
    df_kv = sheet0[[acct_col, val_col]].copy()
except Exception as e:
    st.error("Tidak dapat membangun table Account/Value dari kolom yang terdeteksi: " + str(e))
    st.stop()

df_kv.columns = ["Account", "Value"]
df_kv["Account_str"] = df_kv["Account"].astype(str).str.strip()
df_kv = df_kv[df_kv["Account_str"].str.strip() != ""].reset_index(drop=True)
df_kv["ParsedValue"] = df_kv["Value"].apply(safe_parse_number)

# show cleaned table
st.subheader("Table extracted (Account | Value | ParsedValue)")
display_df = df_kv[["Account_str", "Value", "ParsedValue"]].rename(columns={"Account_str": "Account"})
display_df["ParsedValue_fmt"] = display_df["ParsedValue"].apply(lambda v: f"{int(v):,}" if (v is not None and not pd.isna(v)) else "N/A")
st.dataframe(display_df.reset_index(drop=True))

# -------------------
# Attempt automatic keyword matching
# -------------------
keywords = {
    "current_assets": ["current asset", "current assets", "aset lancar", "kas dan setara kas", "cash and cash equivalents", "kas"],
    "current_liabilities": ["current liabilities", "current liability", "liabilitas lancar", "hutang jangka pendek", "utang lancar", "utang"],
    "total_assets": ["total assets", "total asset", "total aset", "jumlah aset", "total assets (net)"],
    "total_liabilities": ["total liabilities", "total liability", "total liabilitas", "jumlah liabilitas"],
    "total_equity": ["total equity", "total ekuitas", "ekuitas", "modal", "jumlah ekuitas"],
    "net_income": ["net income", "laba bersih", "profit for the year", "laba tahun berjalan", "net profit", "profit"]
}

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

# manual mapping for missing metrics
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

# final values
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

# compute ratios
ca = found.get("current_assets")
cl = found.get("current_liabilities")
ta = found.get("total_assets")
tl = found.get("total_liabilities")
te = found.get("total_equity")
ni = found.get("net_income")

ratios = {
    "Current Ratio": safe_div(ca, cl),
    "Debt-to-Equity (DER)": safe_div(tl, te),
    "ROA": safe_div(ni, ta),
    "ROE": safe_div(ni, te)
}

st.subheader("Rasio yang dihitung")
st.write(ratios)

# local analysis fallback
st.subheader("Analisis Singkat (rule-based, lokal)")
local_analysis = local_rule_based_analysis(ratios)
for line in local_analysis:
    st.write("- " + line)

# visualization
st.subheader("Visualisasi Rasio")
num_ratios = {k: v for k, v in ratios.items() if v is not None and not (isinstance(v, float) and math.isnan(v))}
if num_ratios:
    chart_df = pd.DataFrame({"Rasio": list(num_ratios.keys()), "Nilai": list(num_ratios.values())})
    st.bar_chart(chart_df.set_index("Rasio"))
else:
    st.info("Tidak ada rasio numerik yang cukup untuk divisualisasikan.")

# -------------------
# Integration with LLM (Groq or Grok) — tolerant + safe
# -------------------
# Use priority: GROQ_ env -> GROK_ env. Accept both names for compatibility.
groq_key = os.getenv("GROQ_API_KEY")
groq_url = os.getenv("GROQ_API_URL")
grok_key = os.getenv("GROK_API_KEY")
grok_url = os.getenv("GROK_API_URL")

# determine which service to call (if any)
api_key = None
api_url = None
provider = None
if groq_key and groq_url:
    api_key = groq_key
    api_url = groq_url
    provider = "groq"
elif grok_key and grok_url:
    api_key = grok_key
    api_url = grok_url
    provider = "grok"

if not api_key or not api_url:
    st.info("Interpretasi otomatis via LLM tidak dikonfigurasi. Tambahkan GROQ_API_KEY/GROQ_API_URL atau GROK_API_KEY/GROK_API_URL di Secrets jika mau fitur AI.")
else:
    st.write(f"LLM provider detected: {provider.upper()}")
    if st.button("Interpretasi otomatis via LLM (cloud)"):
        # build a concise prompt
        prompt_parts = []
        prompt_parts.append("You are an accounting analyst. Given the following financial ratios, return a JSON array with fields: ratio, value, interpretation (1-2 sentences), risk_level (Low/Medium/High), recommendations (array of 2 short actions).")
        prompt_parts.append("Ratios:")
        for k, v in ratios.items():
            prompt_parts.append(f"- {k}: {v if v is not None else 'N/A'}")
        prompt = "\n".join(prompt_parts)

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        # payload depends on provider:
        if provider == "groq":
            payload = {
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.05,
                "max_tokens": 400
            }
        else:
            # grok/x.ai style (chat completions)
            payload = {
                "model": "grok-1",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.05,
                "max_tokens": 400
            }
        try:
            with st.spinner("Menghubungi LLM..."):
                resp = requests.post(api_url, json=payload, headers=headers, timeout=25)
                # check HTTP status
                if resp.status_code == 401:
                    st.error("LLM request failed: 401 Unauthorized. Periksa API key & permissions di dashboard penyedia.")
                elif resp.status_code >= 400:
                    st.error(f"LLM request failed: {resp.status_code} {resp.reason}. Response: {resp.text[:400]}")
                else:
                    # try parse result safely
                    try:
                        data = resp.json()
                    except Exception:
                        st.error("Gagal membaca JSON dari LLM response.")
                        st.write(resp.text[:1000])
                        data = None

                    if data:
                        # attempt to extract content for common providers
                        content = None
                        # Groq style: choices[0]['message']['content'] or choices[0]['text']
                        if isinstance(data, dict) and "choices" in data:
                            ch0 = data["choices"][0]
                            # chat-like
                            if isinstance(ch0.get("message"), dict) and "content" in ch0["message"]:
                                content = ch0["message"]["content"]
                            elif "text" in ch0:
                                content = ch0["text"]
                        # fallback raw text
                        if content is None:
                            content = resp.text

                        st.subheader("Hasil interpretasi LLM")
                        # print content (likely JSON)
                        st.code(content)
        except requests.exceptions.RequestException as e:
            st.error("Permintaan ke LLM gagal (network/timeout): " + str(e))
            st.info("Aplikasi tetap menampilkan analisis lokal (rule-based).")

# End of file
