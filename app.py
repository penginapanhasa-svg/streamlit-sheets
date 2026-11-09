import json
import os
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

LOG_FILE = "search_log.json"


# ==================== 3. ALGORITMA PELACAKAN PENCARIAN (TOP 10) ====================
def record_search(keyword):
  """Mencatat kata kunci pencarian dan menambah bobot frekuensinya."""
  if not keyword or len(str(keyword).strip()) < 2:
    return
  item = str(keyword).strip().title()

  # Abai jika berupa pilihan default
  if item.startswith("--"):
    return

  log_data = {}
  if os.path.exists(LOG_FILE):
    try:
      with open(LOG_FILE, "r") as f:
        log_data = json.load(f)
    except Exception:
      log_data = {}

  log_data[item] = log_data.get(item, 0) + 1

  with open(LOG_FILE, "w") as f:
    json.dump(log_data, f)


def get_top_searches(top_n=10):
  """Mengambil Top N komoditas yang paling sering dicari."""
  if not os.path.exists(LOG_FILE):
    return []
  try:
    with open(LOG_FILE, "r") as f:
      log_data = json.load(f)
    # Urutkan berdasarkan nilai frekuensi tertinggi (descending)
    sorted_items = sorted(
        log_data.items(), key=lambda item: item[1], reverse=True
    )
    return [item[0] for item in sorted_items[:top_n]]
  except Exception:
    return []


# ==================== 4. FUNGSI LOAD DATA & REORDER KOLOM ====================
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


# ==================== 5. JUDUL UTAMA & REFRESH ====================
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

    # Menampilkan Top 10 Pencarian Paling Sering
    top_items = get_top_searches(10)
    if top_items:
      st.markdown("🔥 **Top Komoditas Sering Dicari:**")
      cols = st.columns(min(len(top_items), 5))
      for idx, item_name in enumerate(top_items[:5]):
        if cols[idx].button(f"📌 {item_name}", key=f"btn_t1_{idx}"):
          st.session_state["search_keyword"] = item_name

    with st.form(key="search_form"):
      default_val = st.session_state.get("search_keyword", "")
      keyword = st.text_input(
          "Ketik kata kunci atau kode (tekan Enter atau klik Cari):",
          value=default_val,
          placeholder="Contoh: Kode, Nama, Kategori...",
      )
      submit_search = st.form_submit_button("🔍 Cari Data")

    if keyword:
      record_search(keyword)  # Catat kata kunci ke sistem ranking Top 10
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
      col_induk = (
          "Komoditas Induk"
          if "Komoditas Induk" in df_pemetaan.columns
          else (
              "Nama Komoditas"
              if "Nama Komoditas" in df_pemetaan.columns
              else df_pemetaan.columns[0]
          )
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
        record_search(
            pilihan_induk
        )  # Catat komoditas pilihan pengguna ke Top 10

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