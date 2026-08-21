import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import time

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="LGS 7/8 Çalışma, Deneme & Veli Takip",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (TASARIM & MOBİL UYUM) ---
st.markdown("""
<style>
    .stApp {
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #1E3A8A !important;
    }
    
    [data-testid="stMetricLabel"] {
        font-weight: 600 !important;
        color: #4B5563 !important;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1E40AF 0%, #3B82F6 100%);
        padding: 20px;
        border-radius: 14px;
        color: white;
        margin-bottom: 25px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(30, 64, 175, 0.15);
    }
    .main-header h1 {
        color: white !important;
        margin: 0;
        font-size: 1.8rem;
    }
    .main-header p {
        color: #DBEAFE !important;
        margin-top: 5px;
        margin-bottom: 0;
    }

    .stCheckbox label {
        font-size: 1.05rem !important;
    }
    
    .stButton>button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1rem !important;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- DATABASE SETUP (SUPABASE & SQLITE HİBRİT) ---
USE_SUPABASE = False
supabase_client = None

if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
    try:
        from supabase import create_client
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase_client = create_client(url, key)
        USE_SUPABASE = True
    except Exception as e:
        st.warning(f"Supabase bağlantısı kurulamadı, yerel veritabanına geçiliyor: {e}")

if not USE_SUPABASE:
    conn = sqlite3.connect("lgs_takip.db", check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS gunluk_takip (
                    tarih TEXT,
                    gorev TEXT,
                    durum INTEGER,
                    veli_onay INTEGER,
                    veli_notu TEXT,
                    PRIMARY KEY (tarih, gorev)
                )''')
                
    c.execute('''CREATE TABLE IF NOT EXISTS ders_soru_takip (
                    tarih TEXT,
                    ders TEXT,
                    dogru INTEGER,
                    yanlis INTEGER,
                    bos INTEGER,
                    net REAL,
                    PRIMARY KEY (tarih, ders)
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS okuma_takip (
                    tarih TEXT PRIMARY KEY,
                    okunan_sayfa INTEGER
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS denemeler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tarih TEXT,
                    deneme_adi TEXT,
                    turkce_net REAL,
                    mat_net REAL,
                    fen_net REAL,
                    sosyal_net REAL,
                    din_net REAL,
                    ing_net REAL,
                    toplam_net REAL,
                    puan REAL
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS konu_takip (
                    ders TEXT,
                    konu TEXT,
                    tamamlandi INTEGER,
                    PRIMARY KEY (ders, konu)
                )''')
    conn.commit()

# --- CONSTANTS ---
DERSLER = ["Türkçe", "Matematik", "Fen", "Sosyal", "Din Kültürü", "İngilizce"]

LGS_KATSAYILAR = {
    "Türkçe": 4.0,
    "Matematik": 4.0,
    "Fen": 4.0,
    "Sosyal": 1.0,
    "Din Kültürü": 1.0,
    "İngilizce": 1.0
}

VARSAYILAN_KONULAR = {
    "Türkçe": ["Fiilimsiler", "Sözcükte Anlam", "Cümlede Anlam", "Paragrafta Anlam", "Cümlenin Ögeleri", "Yazım Kuralları & Noktalama"],
    "Matematik": ["Çarpanlar ve Katlar", "Üslü İfadeler", "Kareköklü İfadeler", "Veri Analizi", "Basit Olasılık", "Cebirsel İfadeler"],
    "Fen": ["Mevsimler ve İklim", "DNA ve Genetik Kod", "Basınç", "Madde ve Endüstri", "Basit Makineler", "Enerji Dönüşümleri"],
    "Sosyal": ["Bir Kahraman Doğuyor", "Milli Uyanış", "Milli Bir Destan", "Atatürkçülük ve Çağdaşlaşan Türkiye"],
    "Din Kültürü": ["Kader İnancı", "Zekat ve Sadaka", "Din ve Hayat", "Hz. Muhammed'in Örnekliği"],
    "İngilizce": ["Friendship", "Teen Life", "In the Kitchen", "On the Phone", "The Internet"]
}

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
    st.markdown('<div class="main-header"><h1>🎓 LGS Çalışma, Deneme & Veli Takip</h1><p>Disiplinli Çalışma, Şeffaf Takip</p></div>', unsafe_allow_html=True)
    
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

# --- SIDEBAR ---
st.sidebar.markdown(f"### 👤 Rol: **{st.session_state['user_role']}**")
db_badge = "☁️ Supabase (Bulut)" if USE_SUPABASE else "💾 SQLite (Yerel)"
st.sidebar.caption(f"Veritabanı: **{db_badge}**")

if st.sidebar.button("🚪 Çıkış Yap"):
    st.session_state["logged_in"] = False
    st.session_state["user_role"] = None
    st.rerun()

st.markdown(f'''
<div class="main-header">
    <h1>📚 LGS Hazırlık & Disiplin Paneli</h1>
    <p>Aktif Mod: <b>{st.session_state['user_role']}</b></p>
</div>
''', unsafe_allow_html=True)

# TABS DEFINITION
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📝 Günlük Görevler & Ders Soru Girişi", 
    "📝 Deneme Sınavları & LGS Puanı",
    "🎯 Konu / Müfredat Takibi",
    "⏱️ Pomodoro Sayacı",
    "🛡️ Veli Onay & Notlar", 
    "📊 Genel Analiz & Rapor"
])

# ==========================================
# TAB 1: GÜNLÜK GÖREVLER & DERS DERS SORU GİRİŞİ
# ==========================================
with tab1:
    secilen_tarih = st.date_input("📅 Takip Tarihi Seçin", date.today())
    tarih_str = secilen_tarih.strftime("%Y-%m-%d")

    gunler_tr = {0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 3: "Perşembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar"}
    st.info(f"📅 **Günün Programı ({gunler_tr[secilen_tarih.weekday()]}):** " + 
            ("🏫 08:30 - 16:30 Okul Saati" if secilen_tarih.weekday() < 5 else 
             "📖 08:30 - 13:30 Dershane Saati" if secilen_tarih.weekday() == 5 else 
             "🇬🇧 08:30 - 12:30 İngilizce Kursu | 📖 14:00 - 19:00 Dershane Saati"))

    st.subheader("📋 Günlük Rutin Listesi")
    varsayilan_gorevler = [
        "Ders Tekrarı (Okul/Dershane konuları)",
        "Soru Çözümü & Ödevler",
        "Kitap Okuma Saati (En az 30 dk)",
        "Çanta ve Yarınki Plan Hazırlığı",
        "Eğlence / Dinlenme / Spor Saati"
    ]

    mevcut_gorevler = {}
    if not USE_SUPABASE:
        c.execute("SELECT gorev, durum FROM gunluk_takip WHERE tarih=?", (tarih_str,))
        mevcut_gorevler = dict(c.fetchall())

    yeni_durumlar = {}
    for g in varsayilan_gorevler:
        val = bool(mevcut_gorevler.get(g, 0))
        yeni_durumlar[g] = st.checkbox(g, value=val, disabled=(st.session_state["user_role"] == "Veli"))

    st.divider()
    st.subheader("📊 Ders Bazlı Soru Çözümü & Net Takibi")

    soru_verileri = {}
    cols = st.columns(3)
    for i, ders in enumerate(DERSLER):
        with cols[i % 3]:
            st.markdown(f"**{ders}**")
            d = st.number_input(f"{ders} Doğru", min_value=0, value=0, step=1, key=f"{ders}_d", disabled=(st.session_state["user_role"] == "Veli"))
            y = st.number_input(f"{ders} Yanlış", min_value=0, value=0, step=1, key=f"{ders}_y", disabled=(st.session_state["user_role"] == "Veli"))
            b = st.number_input(f"{ders} Boş", min_value=0, value=0, step=1, key=f"{ders}_b", disabled=(st.session_state["user_role"] == "Veli"))
            net = max(0.0, round(d - (y / 3.0), 2))
            st.caption(f"📈 Net: **{net}**")
            soru_verileri[ders] = (d, y, b, net)

    st.divider()
    okunan_sayfa = st.number_input("📖 Bugün Okunan Kitap Sayfası", min_value=0, value=0, step=5, disabled=(st.session_state["user_role"] == "Veli"))

    if st.session_state["user_role"] == "Öğrenci":
        if st.button("💾 Günlük Verileri Kaydet", type="primary"):
            if not USE_SUPABASE:
                for g, dur in yeni_durumlar.items():
                    c.execute("""INSERT INTO gunluk_takip (tarih, gorev, durum, veli_onay, veli_notu) 
                                 VALUES (?, ?, ?, 0, '') ON CONFLICT(tarih, gorev) DO UPDATE SET durum=excluded.durum""",
                              (tarih_str, g, int(dur)))
                
                for ders, (d, y, b, net) in soru_verileri.items():
                    c.execute("""INSERT INTO ders_soru_takip (tarih, ders, dogru, yanlis, bos, net)
                                 VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(tarih, ders) DO UPDATE SET 
                                 dogru=excluded.dogru, yanlis=excluded.yanlis, bos=excluded.bos, net=excluded.net""",
                              (tarih_str, ders, d, y, b, net))
                
                c.execute("""INSERT INTO okuma_takip (tarih, okunan_sayfa) VALUES (?, ?) 
                             ON CONFLICT(tarih) DO UPDATE SET okunan_sayfa=excluded.okunan_sayfa""",
                          (tarih_str, okunan_sayfa))
                conn.commit()
            st.success("Günün verileri başarıyla kaydedildi! 🎉")

# ==========================================
# TAB 2: DENEME SINAVLARI & LGS PUANI
# ==========================================
with tab2:
    st.subheader("📝 LGS Deneme Sınavı Kaydı ve Puan Hesaplama")

    with st.form("deneme_form"):
        deneme_adi = st.text_input("Deneme Sınavı Adı / Yayın", "Örn: Özdebir 1. Deneme")
        deneme_tarihi = st.date_input("Deneme Tarihi", date.today())
        
        st.markdown("##### Ders Netleri Girişi")
        d_cols = st.columns(3)
        netler = {}
        for i, ders in enumerate(DERSLER):
            with d_cols[i % 3]:
                d = st.number_input(f"{ders} D", min_value=0, max_value=20 if ders in ["Türkçe","Matematik","Fen"] else 10, value=15, key=f"den_{ders}_d")
                y = st.number_input(f"{ders} Y", min_value=0, max_value=20, value=3, key=f"den_{ders}_y")
                net = max(0.0, round(d - (y / 3.0), 2))
                netler[ders] = net
                st.caption(f"{ders} Net: **{net}**")

        submit_deneme = st.form_submit_button("🏆 Denemeyi Kaydet ve Puan Hesapla", type="primary")

    if submit_deneme:
        toplam_net = sum(netler.values())
        # LGS Tahmini Puan Hesaplama Modeli (Taban Puan ~190 + Net Katsayı Ağırlıkları)
        agirlikli_puan = sum(netler[ders] * LGS_KATSAYILAR[ders] for ders in DERSLER)
        tahmini_puan = min(500.0, round(190.0 + (agirlikli_puan * 1.52), 2))

        st.balloons()
        st.success(f"🎉 **{deneme_adi}** Kaydedildi!")
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Toplam Net", f"{round(toplam_net, 2)} Net")
        col_m2.metric("Tahmini LGS Puanı", f"{tahmini_puan} Puan")

        if not USE_SUPABASE:
            c.execute("""INSERT INTO denemeler (tarih, deneme_adi, turkce_net, mat_net, fen_net, sosyal_net, din_net, ing_net, toplam_net, puan)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (deneme_tarihi.strftime("%Y-%m-%d"), deneme_adi, netler["Türkçe"], netler["Matematik"], netler["Fen"], 
                       netler["Sosyal"], netler["Din Kültürü"], netler["İngilizce"], toplam_net, tahmini_puan))
            conn.commit()

    st.divider()
    st.subheader("📈 Deneme Sınavı Gelişim Grafiği")
    if not USE_SUPABASE:
        df_deneme = pd.read_sql_query("SELECT * FROM denemeler ORDER BY tarih ASC", conn)
        if not df_deneme.empty:
            st.dataframe(df_deneme[['tarih', 'deneme_adi', 'toplam_net', 'puan']], use_container_width=True)
            st.line_chart(df_deneme.set_index('deneme_adi')[['puan', 'toplam_net']])
        else:
            st.info("Henüz kayıtlı deneme sınavı bulunmuyor.")

# ==========================================
# TAB 3: MÜFREDAT / KONU TAKİBİ
# ==========================================
with tab3:
    st.subheader("🎯 LGS Konu ve Müfredat Takip Paneli")
    secilen_ders_konu = st.selectbox("Ders Seçin", DERSLER)

    st.markdown(f"### **{secilen_ders_konu} Konu Listesi**")
    konular = VARSAYILAN_KONULAR[secilen_ders_konu]
    
    tamamlanan_sayisi = 0
    for k in konular:
        ch = st.checkbox(k, key=f"konu_{secilen_ders_konu}_{k}")
        if ch:
            tamamlanan_sayisi += 1
            
    yuzde = int((tamamlanan_sayisi / len(konular)) * 100) if konular else 0
    st.progress(yuzde / 100)
    st.caption(f"Gelişim: **%{yuzde}** tamamlandı ({tamamlanan_sayisi}/{len(konular)} Konu)")

# ==========================================
# TAB 4: POMODORO ZAMANLAYICI
# ==========================================
with tab4:
    st.subheader("⏱️ Odaklanma Zamanlayıcısı (Pomodoro)")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        sure_dk = st.number_input("Çalışma Süresi (Dakika)", min_value=1, max_value=60, value=25)
    with col_p2:
        mola_dk = st.number_input("Mola Süresi (Dakika)", min_value=1, max_value=30, value=5)

    if st.button("▶️ Zamanlayıcıyı Başlat"):
        saniye = sure_dk * 60
        ph = st.empty()
        st.warning("🔥 Odaklanma Süresi Başladı! İyi Çalışmalar!")
        while saniye > 0:
            dk, sn = divmod(saniye, 60)
            ph.header(f"⏳ **{dk:02d}:{sn:02d}**")
            time.sleep(1)
            saniye -= 1
        st.success("🎉 Süre bitti! Şimdi harika bir molayı hak ettin!")

# ==========================================
# TAB 5: VELİ ONAY PANELİ
# ==========================================
with tab5:
    st.subheader("🛡️ Veli Kontrolü ve Onay Paneli")
    
    mevcut_onay = False
    mevcut_not = ""
    if not USE_SUPABASE:
        c.execute("SELECT veli_onay, veli_notu FROM gunluk_takip WHERE tarih=? LIMIT 1", (tarih_str,))
        v_row = c.fetchone()
        mevcut_onay = bool(v_row[0]) if v_row and v_row[0] else False
        mevcut_not = v_row[1] if v_row and v_row[1] else ""

    if mevcut_onay:
        st.success("✅ Seçili günün çalışmaları Veli tarafından onaylandı!")
    else:
        st.warning("⏳ Seçili gün henüz onaylanmadı.")

    if mevcut_not:
        st.info(f"💬 **Veli Notu:** {mevcut_not}")

    if st.session_state["user_role"] == "Veli":
        st.divider()
        st.subheader("Değerlendirmeyi Güncelle")
        onay_kutusu = st.checkbox("Günü Onayla (Çalışmalar Tamamlandı)", value=mevcut_onay)
        veli_notu_giris = st.text_area("Çocuğunuza Motivasyon / Değerlendirme Notu Ekle", value=mevcut_not)
        
        if st.button("✔ Veli Onayını Kaydet", type="primary"):
            if not USE_SUPABASE:
                c.execute("UPDATE gunluk_takip SET veli_onay=?, veli_notu=? WHERE tarih=?",
                          (int(onay_kutusu), veli_notu_giris, tarih_str))
                conn.commit()
            st.success("Veli onayı ve notu kaydedildi!")
            st.rerun()

# ==========================================
# TAB 6: GENEL ANALİZ VE RAPOR
# ==========================================
with tab6:
    st.subheader("📊 Genel Performans Analizi")
    if not USE_SUPABASE:
        df_soru = pd.read_sql_query("SELECT * FROM ders_soru_takip", conn)
        df_okuma = pd.read_sql_query("SELECT * FROM okuma_takip", conn)
        
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            toplam_s = df_soru['dogru'].sum() + df_soru['yanlis'].sum() + df_soru['bos'].sum() if not df_soru.empty else 0
            st.metric("Toplam Çözülen Soru", f"{toplam_s} Soru")
        with col_r2:
            toplam_sayfa = df_okuma['okunan_sayfa'].sum() if not df_okuma.empty else 0
            st.metric("Toplam Okunan Sayfa", f"{toplam_sayfa} Sayfa")

        st.divider()
        if not df_soru.empty:
            st.subheader("Derslere Göre Çözülen Toplam Soru Dağılımı")
            df_ders_toplam = df_soru.groupby('ders')[['dogru', 'yanlis', 'bos']].sum()
            st.bar_chart(df_ders_toplam)
        else:
            st.info("Henüz grafik gösterilecek soru verisi girişi yapılmadı.")
