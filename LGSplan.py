import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="LGS 7/8 Çalışma & Veli Takip",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM STYLING (MOBİL & MODERN TASARIM İYİLEŞTİRMELERİ) ---
st.markdown("""
<style>
    /* Ana Tema ve Yazı Tipi */
    .stApp {
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    
    /* Responsive Metrik Kartları */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #1E3A8A !important;
    }
    
    [data-testid="stMetricLabel"] {
        font-weight: 600 !important;
        color: #4B5563 !important;
    }
    
    /* Üst Banner Kart Tasarımı */
    .main-header {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        padding: 20px;
        border-radius: 14px;
        color: white;
        margin-bottom: 25px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .main-header h1 {
        color: white !important;
        margin: 0;
        font-size: 1.8rem;
    }
    .main-header p {
        color: #E0E7FF !important;
        margin-top: 5px;
        margin-bottom: 0;
    }

    /* Mobilde Kolay Dokunma için Checkbox Dokunma Alanı */
    .stCheckbox label {
        font-size: 1.05rem !important;
        padding-top: 4px;
        padding-bottom: 4px;
    }
    
    /* Mobil Uyumlu Yuvarlatılmış Butonlar */
    .stButton>button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1rem !important;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- SUPABASE / SQLITE HİBRİT VERİTABANI BAĞLANTISI ---
USE_SUPABASE = False
supabase_client = None

# Streamlit Secrets içinde Supabase bilgileri var mı kontrol et
if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
    try:
        from supabase import create_client
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase_client = create_client(url, key)
        USE_SUPABASE = True
    except Exception as e:
        st.warning(f"Supabase bağlantısı kurulamadı, yerel SQLite veritabanına geçiliyor: {e}")

if not USE_SUPABASE:
    conn = sqlite3.connect("lgs_takip.db", check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS gunluk_takip (
                    tarih TEXT,
                    gorev TEXT,
                    durum INTEGER,
                    soru_sayisi INTEGER,
                    okunan_sayfa INTEGER,
                    veli_onay INTEGER,
                    veli_notu TEXT,
                    PRIMARY KEY (tarih, gorev)
                )''')
    conn.commit()

# --- VERİTABANI YARDIMCI FONKSİYONLARI ---
def get_daily_records(tarih_str):
    if USE_SUPABASE:
        res = supabase_client.table("gunluk_takip").select("*").eq("tarih", tarih_str).execute()
        return res.data
    else:
        c.execute("SELECT * FROM gunluk_takip WHERE tarih=?", (tarih_str,))
        rows = c.fetchall()
        keys = ["tarih", "gorev", "durum", "soru_sayisi", "okunan_sayfa", "veli_onay", "veli_notu"]
        return [dict(zip(keys, row)) for row in rows]

def save_student_data(tarih_str, yeni_durumlar, soru_sayisi, okunan_sayfa):
    if USE_SUPABASE:
        for gorev, dur in yeni_durumlar.items():
            data = {
                "tarih": tarih_str,
                "gorev": gorev,
                "durum": int(dur),
                "soru_sayisi": soru_sayisi,
                "okunan_sayfa": okunan_sayfa
            }
            supabase_client.table("gunluk_takip").upsert(data, on_conflict="tarih,gorev").execute()
    else:
        for g, dur in yeni_durumlar.items():
            c.execute("""INSERT INTO gunluk_takip (tarih, gorev, durum, soru_sayisi, okunan_sayfa, veli_onay, veli_notu) 
                         VALUES (?, ?, ?, ?, ?, 0, '')
                         ON CONFLICT(tarih, gorev) DO UPDATE SET 
                         durum=excluded.durum, soru_sayisi=excluded.soru_sayisi, okunan_sayfa=excluded.okunan_sayfa""",
                      (tarih_str, g, int(dur), soru_sayisi, okunan_sayfa))
        conn.commit()

def save_parent_data(tarih_str, onay_kutusu, veli_notu_giris):
    if USE_SUPABASE:
        supabase_client.table("gunluk_takip").update({
            "veli_onay": int(onay_kutusu),
            "veli_notu": veli_notu_giris
        }).eq("tarih", tarih_str).execute()
    else:
        c.execute("UPDATE gunluk_takip SET veli_onay=?, veli_notu=? WHERE tarih=?",
                  (int(onay_kutusu), veli_notu_giris, tarih_str))
        conn.commit()

def get_all_records():
    if USE_SUPABASE:
        res = supabase_client.table("gunluk_takip").select("*").execute()
        return pd.DataFrame(res.data)
    else:
        return pd.read_sql_query("SELECT * FROM gunluk_takip", conn)

# --- USER AUTHENTICATION ---
USERS = {
    "ogrenci": {"password": "123", "role": "Öğrenci"},
    "veli": {"password": "456", "role": "Veli"}
}

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_role" not in st.session_state:
    st.session_state["user_role"] = None

def login_screen():
    st.markdown('<div class="main-header"><h1>🎓 LGS Çalışma & Veli Takip</h1><p>Disiplinli Çalışma, Şeffaf Takip</p></div>', unsafe_allow_html=True)
    
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.subheader("🔑 Giriş Yap")
            username = st.selectbox("Kullanıcı Rolü", ["ogrenci", "veli"], format_func=lambda x: "Öğrenci Girişi 🎒" if x == "ogrenci" else "Veli Girişi 🛡️")
            password = st.text_input("Şifre", type="password")
            submit = st.form_submit_button("Sisteme Giriş Yap", type="primary")
            
            if submit:
                if username in USERS and USERS[username]["password"] == password:
                    st.session_state["logged_in"] = True
                    st.session_state["user_role"] = USERS[username]["role"]
                    st.rerun()
                else:
                    st.error("❌ Hatalı şifre! Lütfen tekrar deneyin.")

if not st.session_state["logged_in"]:
    login_screen()
    st.stop()

# --- SIDEBAR & HEADER ---
st.sidebar.markdown(f"### 👤 Rol: **{st.session_state['user_role']}**")
db_badge = "☁️ Supabase (Bulut)" if USE_SUPABASE else "💾 SQLite (Yerel)"
st.sidebar.caption(f"Veritabanı Durumu: **{db_badge}**")

if st.sidebar.button("🚪 Çıkış Yap"):
    st.session_state["logged_in"] = False
    st.session_state["user_role"] = None
    st.rerun()

st.markdown(f'''
<div class="main-header">
    <h1>📚 LGS Hazırlık & Disiplin Paneli</h1>
    <p>Aktif Kullanıcı: <b>{st.session_state['user_role']} Modu</b></p>
</div>
''', unsafe_allow_html=True)

# Tarih Seçimi
secilen_tarih = st.date_input("📅 Takip Tarihi Seçin", date.today())
tarih_str = secilen_tarih.strftime("%Y-%m-%d")

gunler_tr = {
    0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 
    3: "Perşembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar"
}
gun_adi = gunler_tr[secilen_tarih.weekday()]

# Program Bilgisi
st.info(f"📅 **Günün Programı ({gun_adi}):**")
if secilen_tarih.weekday() < 5:
    st.write("🏫 **08:30 - 16:30** Okul Saati (Sabit Kilitli Blok)")
elif secilen_tarih.weekday() == 5:
    st.write("📖 **08:30 - 13:30** Dershane Saati")
elif secilen_tarih.weekday() == 6:
    st.write("🇬🇧 **08:30 - 12:30** İngilizce Kursu | 📖 **14:00 - 19:00** Dershane Saati")

varsayilan_gorevler = [
    "Ders Tekrarı (Okul/Dershane konuları)",
    "Soru Çözümü & Ödevler",
    "Kitap Okuma Saati (En az 30 dk)",
    "Çanta ve Yarınki Plan Hazırlığı",
    "Eğlence / Dinlenme / Spor Saati"
]

# Veritabanından Veri Çekme
records = get_daily_records(tarih_str)
mevcut_kayitlar = {r["gorev"]: r["durum"] for r in records} if records else {}
mevcut_soru = records[0]["soru_sayisi"] if records and records[0].get("soru_sayisi") is not None else 0
mevcut_sayfa = records[0]["okunan_sayfa"] if records and records[0].get("okunan_sayfa") is not None else 0
mevcut_onay = bool(records[0]["veli_onay"]) if records and records[0].get("veli_onay") is not None else False
mevcut_not = records[0]["veli_notu"] if records and records[0].get("veli_notu") is not None else ""

# TABS
tab1, tab2, tab3 = st.tabs(["📝 Günlük Görevler & Giriş", "🛡️ Veli Onay & Notlar", "📊 Haftalık Özet & Rapor"])

# TAB 1: ÖĞRENCİ PANELİ
with tab1:
    st.subheader("📋 Günlük Rutin Listesi")
    
    yeni_durumlar = {}
    for g in varsayilan_gorevler:
        varsayilan_val = bool(mevcut_kayitlar.get(g, 0))
        yeni_durumlar[g] = st.checkbox(g, value=varsayilan_val, disabled=(st.session_state["user_role"] == "Veli"))
    
    st.divider()
    st.subheader("📈 Günlük Soru & Sayfa Girişi")
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        soru_sayisi = st.number_input("Bugün Çözülen Toplam Soru Sayısı", min_value=0, value=int(mevcut_soru), step=5, disabled=(st.session_state["user_role"] == "Veli"))
    with col_s2:
        okunan_sayfa = st.number_input("Bugün Okunan Kitap Sayfası", min_value=0, value=int(mevcut_sayfa), step=5, disabled=(st.session_state["user_role"] == "Veli"))

    if st.session_state["user_role"] == "Öğrenci":
        if st.button("💾 Kaydet ve Veliye Gönder", type="primary"):
            save_student_data(tarih_str, yeni_durumlar, soru_sayisi, okunan_sayfa)
            st.success("Günün verileri başarıyla kaydedildi! 🎉")

# TAB 2: VELİ PANELİ
with tab2:
    st.subheader("🛡️ Veli Onay ve Değerlendirme Paneli")
    
    if mevcut_onay:
        st.success("✅ Bu günün çalışmaları Veli tarafından onaylandı!")
    else:
        st.warning("⏳ Bu gün henüz onaylanmadı.")

    if mevcut_not:
        st.info(f"💬 **Veli Notu:** {mevcut_not}")

    if st.session_state["user_role"] == "Veli":
        st.divider()
        st.subheader("Değerlendirmeyi Güncelle")
        onay_kutusu = st.checkbox("Günü Onayla (Çalışmalar Tamamlandı)", value=mevcut_onay)
        veli_notu_giris = st.text_area("Çocuğunuza Motivasyon / Değerlendirme Notu Ekle", value=mevcut_not)
        
        if st.button("✔ Veli Onayını Kaydet", type="primary"):
            save_parent_data(tarih_str, onay_kutusu, veli_notu_giris)
            st.success("Veli onayı ve notu kaydedildi!")
            st.rerun()

# TAB 3: RAPOR PANELİ
with tab3:
    st.subheader("📊 Haftalık Analiz ve Performans Raporu")
    
    df = get_all_records()
    
    if not df.empty:
        df_gunluk = df.groupby('tarih').agg({
            'soru_sayisi': 'max',
            'okunan_sayfa': 'max'
        }).reset_index()

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Toplam Çözülen Soru", f"{int(df_gunluk['soru_sayisi'].sum())} Soru")
        with col_m2:
            st.metric("Toplam Okunan Sayfa", f"{int(df_gunluk['okunan_sayfa'].sum())} Sayfa")
        with col_m3:
            tamamlanan = df['durum'].sum()
            toplam_g = len(df)
            yuzde = int((tamamlanan / toplam_g) * 100) if toplam_g > 0 else 0
            st.metric("Görev Başarı Oranı", f"%{yuzde}")

        st.divider()
        st.subheader("📊 Günlere Göre Soru Çözüm Grafiği")
        st.bar_chart(df_gunluk.set_index('tarih')['soru_sayisi'])
    else:
        st.info("Henüz analiz gösterilecek veri girişi yapılmadı.")
