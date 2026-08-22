import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime
import time
from PIL import Image

# --- STREAMLIT COMPATIBILITY PATCH (DRAWABLE CANVAS FIX) ---
try:
    import streamlit.elements.image as st_image
    if not hasattr(st_image, "image_to_url"):
        from streamlit.elements.lib.image_utils import image_to_url
        st_image.image_to_url = image_to_url
except Exception:
    pass

try:
    from streamlit_drawable_canvas import st_canvas
except ImportError:
    st_canvas = None

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="LGS 7/8 Akıllı Çalışma & Veli Takip",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
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
    
    .main-header {
        background: linear-gradient(135deg, #1E40AF 0%, #3B82F6 100%);
        padding: 22px;
        border-radius: 14px;
        color: white;
        margin-bottom: 20px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(30, 64, 175, 0.15);
    }
    .main-header h1 {
        color: white !important;
        margin: 0;
        font-size: 1.9rem;
    }
    .main-header p {
        color: #DBEAFE !important;
        margin-top: 5px;
        margin-bottom: 0;
    }

    .badge-card {
        background-color: #F3F4F6;
        border-radius: 10px;
        padding: 12px;
        text-align: center;
        border: 1px solid #E5E7EB;
        margin-bottom: 10px;
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

    c.execute('''CREATE TABLE IF NOT EXISTS yanlis_defteri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tarih TEXT,
                    ders TEXT,
                    konu TEXT,
                    soru_notu TEXT,
                    cozuldu INTEGER DEFAULT 0
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

USERS = {
    "ogrenci": {"password": "123", "role": "Öğrenci"},
    "veli": {"password": "456", "role": "Veli"}
}

# --- AUTHENTICATION ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_role" not in st.session_state:
    st.session_state["user_role"] = None

def login_screen():
    st.markdown('<div class="main-header"><h1>🎓 LGS Akıllı Çalışma & Veli Takip</h1><p>Disiplin, Oyunlaştırma ve Şeffaf Takip</p></div>', unsafe_allow_html=True)
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
                    st.error("❌ Hatalı şifre!")

if not st.session_state["logged_in"]:
    login_screen()
    st.stop()

# --- SIDEBAR & BANNER ---
st.sidebar.markdown(f"### 👤 Rol: **{st.session_state['user_role']}**")

lgs_tarihi = date(2027, 6, 6) if date.today().year == 2026 and date.today().month > 6 else date(date.today().year + (1 if date.today().month > 6 else 0), 6, 7)
kalan_gun = (lgs_tarihi - date.today()).days

st.sidebar.metric("⏳ LGS'ye Kalan Gün", f"{kalan_gun} Gün")
st.sidebar.divider()

if st.sidebar.button("🚪 Çıkış Yap"):
    st.session_state["logged_in"] = False
    st.session_state["user_role"] = None
    st.rerun()

st.markdown(f'''
<div class="main-header">
    <h1>📚 LGS Hazırlık & Akıllı Takip Paneli</h1>
    <p>Aktif Mod: <b>{st.session_state['user_role']}</b> | 🎯 LGS'ye <b>{kalan_gun}</b> Gün Kaldı!</p>
</div>
''', unsafe_allow_html=True)

# TABS DEFINITION
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "📝 Günlük Görev & Soru", 
    "📝 Denemeler & LGS Puanı",
    "🎨 Tahta",
    "📕 Yanlış Defteri",
    "🎯 Müfredat Takibi",
    "🏆 Puan & Rozetler",
    "⏱️ Pomodoro",
    "🛡️ Veli Onay", 
    "📊 Analiz & Koçluk"
])

# ==========================================
# TAB 1: GÜNLÜK GÖREVLER & DERS DERS SORU GİRİŞİ
# ==========================================
with tab1:
    secilen_tarih = st.date_input("📅 Takip Tarihi Seçin", date.today())
    tarih_str = secilen_tarih.strftime("%Y-%m-%d")

    gunluk_hedef = st.number_input("🎯 Günlük Soru Hedefi", min_value=50, max_value=500, value=150, step=10)

    st.subheader("📊 Ders Bazlı Soru Çözümü & Net Takibi")
    soru_verileri = {}
    toplam_cozuldu = 0
    cols = st.columns(3)
    for i, ders in enumerate(DERSLER):
        with cols[i % 3]:
            st.markdown(f"**{ders}**")
            d = st.number_input(f"{ders} D", min_value=0, value=0, step=1, key=f"{ders}_d", disabled=(st.session_state["user_role"] == "Veli"))
            y = st.number_input(f"{ders} Y", min_value=0, value=0, step=1, key=f"{ders}_y", disabled=(st.session_state["user_role"] == "Veli"))
            b = st.number_input(f"{ders} B", min_value=0, value=0, step=1, key=f"{ders}_b", disabled=(st.session_state["user_role"] == "Veli"))
            net = max(0.0, round(d - (y / 3.0), 2))
            toplam_cozuldu += (d + y + b)
            st.caption(f"📈 Net: **{net}**")
            soru_verileri[ders] = (d, y, b, net)

    hedef_yuzde = min(1.0, toplam_cozuldu / gunluk_hedef)
    st.markdown(f"**Günlük Hedef İlerlemesi ({toplam_cozuldu} / {gunluk_hedef} Soru)**")
    st.progress(hedef_yuzde)

    st.divider()
    okunan_sayfa = st.number_input("📖 Bugün Okunan Kitap Sayfası", min_value=0, value=0, step=5, disabled=(st.session_state["user_role"] == "Veli"))

    if st.session_state["user_role"] == "Öğrenci":
        if st.button("💾 Günlük Verileri Kaydet", type="primary"):
            if not USE_SUPABASE:
                for ders, (d, y, b, net) in soru_verileri.items():
                    c.execute("""INSERT INTO ders_soru_takip (tarih, ders, dogru, yanlis, bos, net)
                                 VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(tarih, ders) DO UPDATE SET 
                                 dogru=excluded.dogru, yanlis=excluded.yanlis, bos=excluded.bos, net=excluded.net""",
                              (tarih_str, ders, d, y, b, net))
                
                c.execute("""INSERT INTO okuma_takip (tarih, okunan_sayfa) VALUES (?, ?) 
                             ON CONFLICT(tarih) DO UPDATE SET okunan_sayfa=excluded.okunan_sayfa""",
                          (tarih_str, okunan_sayfa))
                conn.commit()
            st.success("Günün verileri kaydedildi! 🎉")

# ==========================================
# TAB 2: DENEME SINAVLARI & LGS PUANI
# ==========================================
with tab2:
    st.subheader("📝 LGS Deneme Sınavı Kaydı ve Puan Hesaplama")
    with st.form("deneme_form"):
        deneme_adi = st.text_input("Deneme Sınavı Adı", "Örn: Özdebir 1. Deneme")
        deneme_tarihi = st.date_input("Deneme Tarihi", date.today())
        
        d_cols = st.columns(3)
        netler = {}
        for i, ders in enumerate(DERSLER):
            with d_cols[i % 3]:
                max_s = 20 if ders in ["Türkçe", "Matematik", "Fen"] else 10
                varsayilan_d = 15 if max_s == 20 else 8
                d = st.number_input(f"{ders} D", min_value=0, max_value=max_s, value=varsayilan_d, key=f"den_{ders}_d")
                y = st.number_input(f"{ders} Y", min_value=0, max_value=max_s, value=2, key=f"den_{ders}_y")
                net = max(0.0, round(d - (y / 3.0), 2))
                netler[ders] = net
                st.caption(f"{ders} Net: **{net}**")

        submit_deneme = st.form_submit_button("🏆 Denemeyi Kaydet", type="primary")

    if submit_deneme:
        toplam_net = sum(netler.values())
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
    if not USE_SUPABASE:
        df_deneme = pd.read_sql_query("SELECT * FROM denemeler ORDER BY tarih ASC", conn)
        if not df_deneme.empty:
            st.dataframe(df_deneme[['tarih', 'deneme_adi', 'toplam_net', 'puan']], use_container_width=True)
            st.line_chart(df_deneme.set_index('deneme_adi')[['puan', 'toplam_net']])

# ==========================================
# TAB 3: TAHTA
# ==========================================
with tab3:
    st.subheader("🎨 Tahta")

    if st_canvas is None:
        st.error("⚠️ `streamlit-drawable-canvas` kütüphanesi yüklenemedi. Lütfen `requirements.txt` dosyanıza `streamlit-drawable-canvas` eklediğinizden emin olun.")
    else:
        # Üst Araç Çubuğu (Kompakt Ayarlar)
        col_tool1, col_tool2, col_tool3, col_tool4 = st.columns([2, 1, 1, 1])
        
        with col_tool1:
            mode_option = st.selectbox(
                "🖌️ Çizim Aracı:",
                ["Kalem (Serbest Çizim)", "Düz Çizgi", "Dikdörtgen", "Daire", "Seç / Taşı"],
                index=0
            )
            mode_map = {
                "Kalem (Serbest Çizim)": "freedraw",
                "Düz Çizgi": "line",
                "Dikdörtgen": "rect",
                "Daire": "circle",
                "Seç / Taşı": "transform"
            }
            drawing_mode = mode_map[mode_option]

        with col_tool2:
            stroke_width = st.slider("✏️ Kalınlık:", 1, 25, 4)

        with col_tool3:
            stroke_color = st.color_picker("🎨 Kalem Rengi:", "#1E40AF")

        with col_tool4:
            bg_color = st.color_picker("🖼️ Arka Plan:", "#FFFFFF")

        st.divider()

        # Ekran moduna göre CSS injection (Tam Ekran Modu Anahtarı)
        is_fullscreen = st.checkbox("🖥️ Tahtayı Tam Ekran Genişliğinde Aç", value=False)
        
        if is_fullscreen:
            # CSS ile tahtayı ekranın tüm alanına zorlar
            st.markdown("""
                <style>
                iframe[title="streamlit_drawable_canvas.st_canvas"] {
                    width: 100% !important;
                    height: 80vh !important;
                }
                </style>
            """, unsafe_allow_html=True)
            canvas_width = 1200
            canvas_height = 750
        else:
            canvas_width = 730
            canvas_height = 550

        # Çizim Tuvali
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.2)",
            stroke_width=stroke_width,
            stroke_color=stroke_color,
            background_color=bg_color,
            update_streamlit=True,
            width=canvas_width,
            height=canvas_height,
            drawing_mode=drawing_mode,
            key="canvas_full_board",
        )

        col_act1, col_act2 = st.columns([1, 1])
        with col_act1:
            if st.button("🗑️ Tahtayı Temizle", use_container_width=True):
                st.rerun()

        with col_act2:
            if canvas_result is not None and canvas_result.image_data is not None:
                draw_img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                import io
                buf = io.BytesIO()
                draw_img.save(buf, format="PNG")
                byte_im = buf.getvalue()
                
                st.download_button(
                    label="💾 Çizimi İndir (PNG)",
                    data=byte_im,
                    file_name="tahta_cizim.png",
                    mime="image/png",
                    use_container_width=True
                )
# ==========================================
# TAB 4: YANLIŞ SORU DEFTERİ
# ==========================================
with tab4:
    st.subheader("📚 Yanlış Soru Defteri")
    st.caption("Çözmekte zorlandığınız veya yanlış yaptığınız soruları görseli, dersi, konusu ve notlarınızla birlikte kaydedin.")

    if "yanlis_sorular" not in st.session_state:
        st.session_state["yanlis_sorular"] = []

    with st.expander("➕ Yeni Yanlış Soru Ekle", expanded=True):
        col_ys1, col_ys2 = st.columns([1, 1])
        
        with col_ys1:
            ys_ders = st.selectbox(
                "📘 Ders Seçin:",
                ["Türkçe", "Matematik", "Fen", "Sosyal", "İngilizce", "Din Kültürü"]
            )
            ys_konu = st.text_input("📌 Konu Adı:", placeholder="Örn: Çarpanlar ve Katlar / Paragrafta Anlam")
            ys_not = st.text_area("📝 Soru/Çözüm Açıklaması veya Notunuz:", placeholder="Bu soruda nerede hata yaptınız? Dikkat edilmesi gereken nokta nedir?")

        with col_ys2:
            ys_gorsel = st.file_uploader(
                "📷 Soru Görseli veya PDF Dosyası Yükleyin:",
                type=["png", "jpg", "jpeg", "pdf"],
                key="ys_file_uploader_input"
            )
            
            if ys_gorsel is not None:
                file_ext = ys_gorsel.name.split('.')[-1].lower()
                if file_ext in ["png", "jpg", "jpeg"]:
                    st.image(ys_gorsel, caption="Yüklenen Görsel Önizleme", use_container_width=True)

        if st.button("💾 Yanlış Soru Defterine Kaydet", type="primary", use_container_width=True):
            if ys_gorsel is None and not ys_konu:
                st.warning("⚠️ Lütfen en az bir dosya (görsel/PDF) yükleyin veya konu adı belirtin.")
            else:
                gorsel_veri = None
                if ys_gorsel is not None:
                    file_ext = ys_gorsel.name.split('.')[-1].lower()
                    if file_ext == "pdf":
                        try:
                            import pypdfium2 as pdfium
                            pdf = pdfium.PdfDocument(ys_gorsel)
                            page = pdf[0]
                            gorsel_veri = page.render(scale=2.0).to_pil().convert("RGBA")
                        except Exception as e:
                            st.error(f"PDF dönüştürülürken hata oluştu: {e}")
                    else:
                        try:
                            gorsel_veri = Image.open(ys_gorsel).convert("RGBA")
                        except Exception as e:
                            st.error(f"Görsel okunurken hata oluştu: {e}")

                yeni_kayit = {
                    "id": len(st.session_state["yanlis_sorular"]) + 1,
                    "ders": ys_ders,
                    "konu": ys_konu if ys_konu else "Belirtilmedi",
                    "not": ys_not if ys_not else "Not eklenmedi.",
                    "gorsel": gorsel_veri,
                    "tarih": datetime.now().strftime("%d.%m.%Y")
                }
                
                st.session_state["yanlis_sorular"].append(yeni_kayit)
                st.success("✅ Soru Yanlış Defterine başarıyla kaydedildi! Beyaz Tahta sekmesinden çağırıp kalemle çözebilirsiniz.")
                st.rerun()

    st.divider()

    st.markdown("### 📖 Kayıtlı Yanlış Sorularınız")

    if not st.session_state["yanlis_sorular"]:
        st.info("Henüz kaydedilmiş yanlış soru bulunmuyor. Yukarıdaki formu kullanarak ilk sorunuzu ekleyebilirsiniz.")
    else:
        filtre_ders = st.selectbox("🔍 Derse Göre Filtrele:", ["Tümü"] + DERSLER)
        
        for idx, soru in enumerate(st.session_state["yanlis_sorular"]):
            if filtre_ders != "Tümü" and soru["ders"] != filtre_ders:
                continue
                
            with st.expander(f"📌 {soru['ders']} - {soru['konu']} (Tarih: {soru.get('tarih', '-')})", expanded=False):
                col_d1, col_d2 = st.columns([1, 1])
                with col_d1:
                    st.markdown(f"**📘 Ders:** {soru['ders']}")
                    st.markdown(f"**📌 Konu:** {soru['konu']}")
                    st.markdown(f"**📝 Not/Açıklama:** {soru['not']}")
                    
                    if st.button(f"🗑️ Soruyu Sil", key=f"del_ys_{idx}"):
                        st.session_state["yanlis_sorular"].pop(idx)
                        st.rerun()
                        
                with col_d2:
                    if soru["gorsel"] is not None:
                        st.image(soru["gorsel"], caption="Soru Görseli", use_container_width=True)
                    else:
                        st.info("Bu kayıt için görsel yüklenmemiş.")

# ==========================================
# TAB 5: MÜFREDAT TAKİBİ
# ==========================================
with tab5:
    st.subheader("🎯 LGS Konu ve Müfredat Takip Paneli")
    secilen_ders_konu = st.selectbox("Ders Seçin", DERSLER, key="mufredat_ders")
    konular = VARSAYILAN_KONULAR[secilen_ders_konu]
    
    tamamlanan_sayisi = 0
    for k in konular:
        ch = st.checkbox(k, key=f"konu_{secilen_ders_konu}_{k}")
        if ch:
            tamamlanan_sayisi += 1
            
    yuzde = int((tamamlanan_sayisi / len(konular)) * 100) if konular else 0
    st.progress(yuzde / 100)
    st.caption(f"Müfredat Tamamlanma: **%{yuzde}** ({tamamlanan_sayisi}/{len(konular)} Konu)")

# ==========================================
# TAB 6: ROZET VE PUAN SİSTEMİ
# ==========================================
with tab6:
    st.subheader("🏆 Puan Paneli & Başarı Rozetleri")
    toplam_s = 0
    toplam_sayfa = 0
    if not USE_SUPABASE:
        df_s = pd.read_sql_query("SELECT dogru, yanlis, bos FROM ders_soru_takip", conn)
        if not df_s.empty:
            toplam_s = int(df_s.sum().sum())
        df_o = pd.read_sql_query("SELECT okunan_sayfa FROM okuma_takip", conn)
        if not df_o.empty:
            toplam_sayfa = int(df_o['okunan_sayfa'].sum())

    toplam_puan = (toplam_s * 2) + (toplam_sayfa * 3)

    st.metric("⭐ Toplam LGS Başarı Puanı", f"{toplam_puan} XP")
    st.divider()

    st.subheader("🎖️ Kazanılan Rozetler")
    r1, r2, r3 = st.columns(3)
    
    with r1:
        st.markdown(f'''
        <div class="badge-card">
            <h3>{"🎯" if toplam_s >= 500 else "🔒"}</h3>
            <b>500 Soru Kulübü</b><br>
            <small>{"Kazanıldı!" if toplam_s >= 500 else "500 Soruya Ulaş"}</small>
        </div>
        ''', unsafe_allow_html=True)

    with r2:
        st.markdown(f'''
        <div class="badge-card">
            <h3>{"📚" if toplam_sayfa >= 200 else "🔒"}</h3>
            <b>Kitap Kurdu</b><br>
            <small>{"Kazanıldı!" if toplam_sayfa >= 200 else "200 Sayfa Okunmalı"}</small>
        </div>
        ''', unsafe_allow_html=True)

    with r3:
        st.markdown(f'''
        <div class="badge-card">
            <h3>{"⚡" if toplam_puan >= 1000 else "🔒"}</h3>
            <b>LGS Şampiyonu</b><br>
            <small>{"Kazanıldı!" if toplam_puan >= 1000 else "1000 XP Biriktir"}</small>
        </div>
        ''', unsafe_allow_html=True)

# ==========================================
# TAB 7: POMODORO ZAMANLAYICI
# ==========================================
with tab7:
    st.subheader("⏱️ Odaklanma Zamanlayıcısı (Pomodoro)")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        sure_dk = st.number_input("Çalışma Süresi (Dakika)", min_value=1, max_value=60, value=25)
    with col_p2:
        mola_dk = st.number_input("Mola Süresi (Dakika)", min_value=1, max_value=30, value=5)

    if "pomodoro_active" not in st.session_state:
        st.session_state["pomodoro_active"] = False

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("▶️ Zamanlayıcıyı Başlat"):
            st.session_state["pomodoro_active"] = True
    with col_btn2:
        if st.button("⏹️ Durdur / Sıfırla"):
            st.session_state["pomodoro_active"] = False
            st.rerun()

    if st.session_state["pomodoro_active"]:
        st.warning("🔥 Odaklanma Süresi Başladı! İyi Çalışmalar!")
        timer_placeholder = st.empty()
        
        saniye = sure_dk * 60
        for s in range(saniye, -1, -1):
            if not st.session_state["pomodoro_active"]:
                break
            dk, sn = divmod(s, 60)
            timer_placeholder.header(f"⏳ **{dk:02d}:{sn:02d}**")
            time.sleep(1)
            
        if st.session_state["pomodoro_active"]:
            st.session_state["pomodoro_active"] = False
            timer_placeholder.empty()
            st.balloons()
            st.success("🎉 Süre bitti! Şimdi harika bir molayı hak ettin!")

# ==========================================
# TAB 8: VELİ ONAY PANELİ
# ==========================================
with tab8:
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
        with st.form("veli_onay_form"):
            onay_kutusu = st.checkbox("Günü Onayla (Çalışmalar Tamamlandı)", value=mevcut_onay)
            not_girisi = st.text_area("Veli Notu / Değerlendirmesi", value=mevcut_not)
            submit_veli = st.form_submit_button("💾 Onayı Kaydet", type="primary")

            if submit_veli:
                if not USE_SUPABASE:
                    c.execute("""INSERT INTO gunluk_takip (tarih, gorev, durum, veli_onay, veli_notu)
                                 VALUES (?, 'Genel Takip', 1, ?, ?)
                                 ON CONFLICT(tarih, gorev) DO UPDATE SET 
                                 veli_onay=excluded.veli_onay, veli_notu=excluded.veli_notu""",
                              (tarih_str, 1 if onay_kutusu else 0, not_girisi))
                    conn.commit()
                st.success("Veli onayı güncellendi!")
                st.rerun()

# ==========================================
# TAB 9: ANALİZ & KOÇLUK
# ==========================================
with tab9:
    st.subheader("📊 Çalışma Analizi ve Akıllı Koçluk")
    if not USE_SUPABASE:
        df_toplam = pd.read_sql_query("SELECT ders, SUM(dogru) as Toplam_Dogru, SUM(yanlis) as Toplam_Yanlis, SUM(net) as Toplam_Net FROM ders_soru_takip GROUP BY ders", conn)
        if not df_toplam.empty:
            st.dataframe(df_toplam, use_container_width=True)
            st.bar_chart(df_toplam.set_index('ders')['Toplam_Net'])
        else:
            st.info("Henüz analiz yapılacak soru verisi girilmemiş.")
