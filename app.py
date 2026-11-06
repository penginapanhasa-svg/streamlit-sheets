import gspread
import pandas as pd
import streamlit as st

# 1. Autentikasi Google Sheets API (Otomatis: Cloud vs Lokal)
if "gcp_service_account" in st.secrets:
  # Berjalan di Streamlit Cloud (menggunakan Secrets)
  client = gspread.service_account_from_dict(
      dict(st.secrets["gcp_service_account"])
  )
else:
  # Berjalan di laptop lokal (menggunakan file credentials.json)
  client = gspread.service_account(filename="credentials.json")

# 2. Hubungkan ke Spreadsheet via URL & Tab 'Database'
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1L04V4tynlOABViIwlj87G8T7WV51kZbUnftJEt4JLfk/edit?usp=sharing"
sheet = client.open_by_url(spreadsheet_url).worksheet("Database")

st.title("📊 Tampilan Database Spreadsheet")


# 3. Fungsi Membaca Data
def load_data():
  records = sheet.get_all_records()
  return pd.DataFrame(records)


# Tampilkan Tabel Data
st.subheader("📋 Daftar Data")
try:
  df = load_data()
  st.dataframe(df, use_container_width=True)
except Exception as e:
  st.error(f"Gagal memuat data dari spreadsheet: {e}")

# 4. Form Input Data Baru di Sidebar
st.sidebar.header("➕ Form Tambah Data")
with st.sidebar.form("form_entry"):
  nama = st.text_input("Nama / Judul")
  kategori = st.text_input("Kategori")

  submit_button = st.form_submit_button("Simpan ke Sheets")

  if submit_button:
    if nama:
      sheet.append_row([nama, kategori])
      st.sidebar.success("Data berhasil disimpan!")
      st.rerun()
    else:
      st.sidebar.error("Kolom nama wajib diisi!")