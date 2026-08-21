import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

# --- PAGE CONFIG ---
st.set_page_config(page_title="LGS 7/8 Çalışma & Veli Takip", page_icon="🎓", layout="wide")

# --- DATABASE SETUP ---
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
    st.title("🎓 LGS Çalışma ve Veli Takip Sistemi")
    st.subheader("Giriş Yap")
    
    col1, _ = st.columns([1, 2])
    with col1:
        username = st.selectbox("Kullanıcı Rolü", ["ogrenci", "veli"], format_func=lambda x: "Öğrenci Girişi" if x == "ogrenci" else "Veli Girişi")
        password = st.text_input("Şifre", type="password")
        
        if st.button("Giriş Yap", type="primary"):
            if username in USERS and USERS[username]["password"] == password:
                st.session_state["logged_in"] = True
                st.session_state["user_role"] = USERS[username]["role"]
                st.rerun()
            else:
                st.error("Hatalı şifre!")

if not st.session_state["logged_in"]:
    login_screen()
    st.stop()

# --- MAIN HEADER ---
st.sidebar.title(f"👤 {st.session_state['user_role']} Modu")
if st.sidebar.button("Çıkış Yap"):
    st.session_state["logged_in"] = False
    st.session_state["user_role"] = None
    st.rerun()

st.title("📚 LGS Hazırlık & Disiplin Takip Paneli")

# Tarih ve Gün Bilgisi
secilen_tarih = st.date_input("Takip Tarihi", date.today())
tarih_str = secilen_tarih.strftime("%Y-%m-%d")

gunler_tr = {
    0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 
    3: "Perşembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar"
}
gun_adi = gunler_tr[secilen_tarih.weekday()]

# --- SABİT PROGRAM BİLGİLENDİRMESİ ---
st.info(f"📅 **Günün Programı ({gun_adi}):**")
if secilen_tarih.weekday() < 5:  # Hafta İçi
    st.write("🏫 **08:30 - 16:30** Okul Saati (Sabit Kilitli Blok)")
elif secilen_tarih.weekday() == 5:  # Cumartesi
    st.write("📖 **08:30 - 13:30** Dershane Saati")
elif secilen_tarih.weekday() == 6:  # Pazar
    st.write("🇬🇧 **08:30 - 12:30** İngilizce Kursu | 📖 **14:00 - 19:00** Dershane Saati")

# --- GÜNLÜK RUTİN LİSTESİ ---
varsayilan_gorevler = [
    "Ders Tekrarı (Okul/Dershane konuları)",
    "Soru Çözümü & Ödevler",
    "Kitap Okuma Saati (En az 30 dk)",
    "Çanta ve Yarınki Plan Hazırlığı",
    "Eğlence / Dinlenme / Spor Saati"
]

# --- TAB'LAR ---
tab1, tab2, tab3 = st.tabs(["📝 Günlük Görevler & Giriş", "🛡️ Veli Onay & Notlar", "📊 Haftalık Özet & Rapor"])

# ==========================================
# TAB 1: ÖĞRENCİ PANELİ
# ==========================================
with tab1:
    st.header("Günlük Görev Listesi")
    
    c.execute("SELECT gorev, durum FROM gunluk_takip WHERE tarih=?", (tarih_str,))
    mevcut_kayitlar = dict(c.fetchall())
    
    yeni_durumlar = {}
    for g in varsayilan_gorevler:
        varsayilan_val = bool(mevcut_kayitlar.get(g, 0))
        yeni_durumlar[g] = st.checkbox(g, value=varsayilan_val, disabled=(st.session_state["user_role"] == "Veli"))
    
    st.divider()
    st.subheader("📈 Günlük Soru ve Sayfa Sayıları")
    
    c.execute("SELECT soru_sayisi, okunan_sayfa FROM gunluk_takip WHERE tarih=? LIMIT 1", (tarih_str,))
    row = c.fetchone()
    mevcut_soru = row[0] if row and row[0] is not None else 0
    mevcut_sayfa = row[1] if row and row[1] is not None else 0
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        soru_sayisi = st.number_input("Bugün Çözülen Toplam Soru Sayısı", min_value=0, value=mevcut_soru, step=5, disabled=(st.session_state["user_role"] == "Veli"))
    with col_s2:
        okunan_sayfa = st.number_input("Bugün Okunan Kitap Sayfası", min_value=0, value=mevcut_sayfa, step=5, disabled=(st.session_state["user_role"] == "Veli"))

    if st.session_state["user_role"] == "Öğrenci":
        if st.button("Kaydet ve Gönder", type="primary"):
            for g, dur in yeni_durumlar.items():
                c.execute("""INSERT INTO gunluk_takip (tarih, gorev, durum, soru_sayisi, okunan_sayfa, veli_onay, veli_notu) 
                             VALUES (?, ?, ?, ?, ?, 0, '')
                             ON CONFLICT(tarih, gorev) DO UPDATE SET 
                             durum=excluded.durum, soru_sayisi=excluded.soru_sayisi, okunan_sayfa=excluded.okunan_sayfa""",
                          (tarih_str, g, int(dur), soru_sayisi, okunan_sayfa))
            conn.commit()
            st.success("Günün verileri başarıyla kaydedildi! 🎉")

# ==========================================
# TAB 2: VELİ ONAY PANELİ
# ==========================================
with tab2:
    st.header("Veli Kontrolü ve Onay")
    
    c.execute("SELECT veli_onay, veli_notu FROM gunluk_takip WHERE tarih=? LIMIT 1", (tarih_str,))
    v_row = c.fetchone()
    mevcut_onay = bool(v_row[0]) if v_row and v_row[0] is not None else False
    mevcut_not = v_row[1] if v_row and v_row[1] is not None else ""
    
    if mevcut_onay:
        st.success("✅ Bu günün çalışmaları Veli tarafından onaylandı!")
    else:
        st.warning("⏳ Bu gün henüz onaylanmadı.")

    if mevcut_not:
        st.info(f"💬 **Veli Notu:** {mevcut_not}")

    if st.session_state["user_role"] == "Veli":
        st.divider()
        st.subheader("Veli Değerlendirmesi Yap")
        onay_kutusu = st.checkbox("Günü Onayla (Çalışmalar Tamamlandı)", value=mevcut_onay)
        veli_notu_giris = st.text_area("Çocuğunuza Motivasyon Notu Ekle", value=mevcut_not)
        
        if st.button("Veli Onayını Kaydet", type="primary"):
            c.execute("UPDATE gunluk_takip SET veli_onay=?, veli_notu=? WHERE tarih=?",
                      (int(onay_kutusu), veli_notu_giris, tarih_str))
            conn.commit()
            st.success("Veli onayı ve notu kaydedildi!")
            st.rerun()

# ==========================================
# TAB 3: HAFTALIK ÖZET & ANALİZ
# ==========================================
with tab3:
    st.header("📊 Haftalık Analiz ve Performans")
    
    df = pd.read_sql_query("SELECT * FROM gunluk_takip", conn)
    
    if not df.empty:
        df_gunluk = df.groupby('tarih').agg({
            'soru_sayisi': 'max',
            'okunan_sayfa': 'max'
        }).reset_index()

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Toplam Çözülen Soru", f"{df_gunluk['soru_sayisi'].sum()} Soru")
        with col_m2:
            st.metric("Toplam Okunan Sayfa", f"{df_gunluk['okunan_sayfa'].sum()} Sayfa")
        with col_m3:
            tamamlanan = df['durum'].sum()
            toplam_g = len(df)
            yuzde = int((tamamlanan / toplam_g) * 100) if toplam_g > 0 else 0
            st.metric("Görev Başarı Oranı", f"%{yuzde}")

        st.divider()
        st.subheader("Günlere Göre Soru Çözüm Grafiği")
        st.bar_chart(df_gunluk.set_index('tarih')['soru_sayisi'])
    else:
        st.info("Henüz analiz gösterilecek veri girişi yapılmadı.")
