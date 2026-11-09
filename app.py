import json
import os
from datetime import datetime
import gspread
import pandas as pd
import streamlit as st

# ==================== 1. KUSTOMISASI TAMPILAN (CSS) ====================
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            [data-testid="stAppDeployButton"] {display: none !important;}
            [data-testid="stStatusWidget"] {display: none !important;}
            .stAppToolbar {display: none !important;}
            [data-testid="stHeader"] {display: none !important;}
            [data-testid="stFooter"] {display: none !important;}
            #stDecoration {display: none !important;}
            div[class*="viewerBadge"] {display: none !important;}
            a[href*="streamlit.io"] {display: none !important;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==================== 2. AUTENTIKASI GOOGLE SHEETS ====================
try:
  client = gspread.service_account_from_dict(
      dict(st.secrets["gcp_service_account"])
  )
except Exception:
  client = gspread.service_account(filename="credentials.json")

spreadsheet_url = "https://docs.google.com/spreadsheets/d/1L04V4tynlOABViIwlj87G8T7WV51kZbUnftJEt4JLfk/edit?usp=sharing"


# ==================== 3. SYSTEM LOG & DATABASE FREKUENSI PENCARIAN ====================
@st.cache_data(ttl=60)
def get_top_searches_from_sheets(top_n=10):
  try:
    sh = client.open_by_url(spreadsheet_url)
    ws = sh.worksheet("Log_Pencarian")
    records = ws.get_all_records()
    df_log = pd.DataFrame(records)
    if not df_log.empty and "Kata_Kunci" in df_log.columns:
      df_log["Jumlah_Pencarian"] = pd.to_numeric(
          df_log["Jumlah_Pencarian"], errors="coerce"
      ).fillna(0)
      df_log = df_log.sort_values(by="Jumlah_Pencarian", ascending=False)
      return df_log.head(top_n).to_dict("records")
  except Exception:
    pass
  return []


def record_search_to_sheets(keyword):
  if not keyword or len(str(keyword).strip()) < 2:
    return
  item = str(keyword).strip().title()
  if item.startswith("--"):
    return

  try:
    sh = client.open_by_url(spreadsheet_url)
    try:
      ws = sh.worksheet("Log_Pencarian")
    except Exception:
      ws = sh.add_worksheet(title="Log_Pencarian", rows="100", cols="3")
      ws.append_row(["Kata_Kunci", "Jumlah_Pencarian", "Terakhir_Dicari"])

    records = ws.get_all_records()
    found = False
    row_idx = 2

    for r in records:
      if str(r.get("Kata_Kunci", "")).strip().title() == item:
        current_count = int(r.get("Jumlah_Pencarian", 0))
        ws.update_cell(row_idx, 2, current_count + 1)
        ws.update_cell(
            row_idx, 3, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        found = True
        break
      row_idx += 1

    if not found:
      ws.append_row([item, 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
  except Exception:
    pass


# ==================== 4. FUNGSI DATA CACHE & FORMAT KOLOM ====================
@st.cache_data(ttl=3600)
def load_data_with_file_cache(sheet_name, cache_filename):
  if os.path.exists(cache_filename):
    try:
      return pd.read_csv(cache_filename)
    except Exception:
      pass

  sheet = client.open_by_url(spreadsheet_url).worksheet(sheet_name)
  records = sheet.get_all_records()
  df = pd.DataFrame(records)
  df.to_csv(cache_filename, index=False)
  return df


def arrange_initial_columns(df):
  priority_cols = [
      "Kode Lengkap",
      "Kode Komoditas",
      "Nama Komoditas",
      "Kode Kualitas",
      "Nama Kualitas",
  ]
  existing_priority = [col for col in priority_cols if col in df.columns]
  other_cols = [col for col in df.columns if col not in existing_priority]
  return df[existing_priority + other_cols]


# ==================== 5. JUDUL UTAMA & REFRESH DATA ====================
st.title("📊 Manajemen Data & Pengeluaran Rumah Tangga")

col1, col2 = st.columns(2)
with col2:
  if st.button("🔄 Refresh Data"):
    if os.path.exists("cache_database.csv"):
      os.remove("cache_database.csv")
    if os.path.exists("cache_pemetaan.csv"):
      os.remove("cache_pemetaan.csv")
    st.cache_data.clear()
    st.success("Cache berhasil dibersihkan!")
    st.rerun()

# ==================== 6. MULTI-TAB NAVIGATION ====================
tab1, tab2 = st.tabs([
    "🔍 Database Utama",
    "🚗 Pemetaan Pengeluaran Turunan",
])

# -------------------- TAB 1: DATABASE UTAMA --------------------
with tab1:
  st.subheader("📋 Pencarian Database Utama ('Database')")
  try:
    df = load_data_with_file_cache("Database", "cache_database.csv")
    df = arrange_initial_columns(df)

    top_logs = get_top_searches_from_sheets(5)
    if top_logs:
      st.markdown("🔥 **Top Komoditas Paling Sering Dicari Pengguna:**")
      cols = st.columns(len(top_logs))
      for idx, item in enumerate(top_logs):
        label = f"📌 {item['Kata_Kunci']} ({item['Jumlah_Pencarian']}x)"
        if cols[idx].button(label, key=f"btn_t1_{idx}"):
          st.session_state["search_keyword"] = item["Kata_Kunci"]

    with st.form(key="search_form"):
      default_val = st.session_state.get("search_keyword", "")
      keyword = st.text_input(
          "Ketik kata kunci atau kode (tekan Enter atau klik Cari):",
          value=default_val,
          placeholder="Contoh: Kode, Nama, Kategori...",
      )
      submit_search = st.form_submit_button("🔍 Cari Data")

    if keyword:
      record_search_to_sheets(keyword)
      mask = pd.Series(False, index=df.index)
      for col in df.columns:
        mask |= (
            df[col].astype(str).str.contains(keyword, case=False, na=False)
        )
      filtered_df = df[mask]
      st.write(
          f"Ditemukan **{len(filtered_df)}** data untuk kata kunci"
          f" *'{keyword}'*:"
      )
      st.dataframe(filtered_df, use_container_width=True)
    else:
      st.dataframe(df, use_container_width=True)
  except Exception as e:
    st.error(f"Gagal memuat data dari worksheet 'Database': {e}")

# -------------------- TAB 2: DATABASE PEMETAAN --------------------
with tab2:
  st.subheader("💡 Pemetaan Pengeluaran Turunan ('Database_Pemetaan')")
  st.caption(
      "Pilih barang/komoditas utama melalui opsi pilihan di bawah untuk melihat"
      " pengeluaran konsekuensi yang lazim muncul."
  )

  try:
    df_pemetaan = load_data_with_file_cache(
        "Database_Pemetaan", "cache_pemetaan.csv"
    )
    df_pemetaan = arrange_initial_columns(df_pemetaan)

    if not df_pemetaan.empty:
      # Deteksi nama kolom acuan komoditas induk secara aman (selalu mengembalikan 1 string nama kolom)
      candidates = [
          "Komoditas Induk",
          "Nama Komoditas",
          "Barang Utama",
          "Komoditas",
      ]
      col_induk = next(
          (c for c in candidates if c in df_pemetaan.columns),
          df_pemetaan.columns[0],
      )

      opsi_induk = ["-- Tampilkan Semua Barang --"] + sorted(
          [
              str(x)
              for x in df_pemetaan[col_induk].dropna().unique()
              if str(x).strip() != ""
          ]
      )

      col_filter1, col_filter2 = st.columns(2)

      with col_filter1:
        pilihan_induk = st.selectbox(
            "📌 Pilih Barang Utama yang Dimiliki:", opsi_induk
        )

      if pilihan_induk != "-- Tampilkan Semua Barang --":
        record_search_to_sheets(pilihan_induk)

      filtered_pemetaan = df_pemetaan.copy()
      if pilihan_induk != "-- Tampilkan Semua Barang --":
        filtered_pemetaan = filtered_pemetaan[
            filtered_pemetaan[col_induk].astype(str) == pilihan_induk
        ]

      col_kat = next(
          (
              col
              for col in ["Kategori Relasi", "Kategori"]
              if col in df_pemetaan.columns
          ),
          None,
      )
      if col_kat:
        opsi_kat = ["-- Semua Kategori --"] + sorted(
            [
                str(x)
                for x in filtered_pemetaan[col_kat].dropna().unique()
                if str(x).strip() != ""
            ]
        )
        with col_filter2:
          pilihan_kat = st.selectbox("🏷️ Filter Kategori Relasi:", opsi_kat)

        if pilihan_kat != "-- Semua Kategori --":
          filtered_pemetaan = filtered_pemetaan[
              filtered_pemetaan[col_kat].astype(str) == pilihan_kat
          ]

      st.write(
          f"Menampilkan **{len(filtered_pemetaan)}** daftar pengeluaran turunan"
          " yang sesuai:"
      )
      st.dataframe(filtered_pemetaan, use_container_width=True)

    else:
      st.warning("Worksheet 'Database_Pemetaan' masih kosong.")

  except Exception as e:
    st.error(f"Gagal memuat data dari worksheet 'Database_Pemetaan': {e}")