import streamlit as st
import os
import io
from PIL import Image

# ---------------------------------------------------------
# 1. Sayfa Yapılandırması ve Oturum (Session State) Başlatma
# ---------------------------------------------------------
st.set_page_config(
    page_title="Akıllı Kaynak ve Arama Asistanı",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Yönlendirme ve Tema Durumları
if "current_page" not in st.session_state:
    st.session_state.current_page = "home"  # 'home', 'sources', 'settings', 'results'

if "bg_color" not in st.session_state:
    st.session_state.bg_color = "#f4f6f9"
if "primary_color" not in st.session_state:
    st.session_state.primary_color = "#1e3a8a"
if "text_color" not in st.session_state:
    st.session_state.text_color = "#1f2937"
if "font_size" not in st.session_state:
    st.session_state.font_size = 16
if "font_family" not in st.session_state:
    st.session_state.font_family = "sans-serif"

if "sources_list" not in st.session_state:
    st.session_state.sources_list = []

if "search_query" not in st.session_state:
    st.session_state.search_query = ""

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ---------------------------------------------------------
# 2. Dinamik CSS (Ayar Değişikliklerinin Tüm Sayfaya Etkisi)
# ---------------------------------------------------------
custom_css = f"""
    <style>
    /* Ana Arka Plan ve Font */
    .stApp {{
        background-color: {st.session_state.bg_color};
        color: {st.session_state.text_color};
        font-family: {st.session_state.font_family};
        font-size: {st.session_state.font_size}px;
    }}
    
    /* Başlıklar ve Metinler */
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown {{
        color: {st.session_state.text_color} !important;
        font-family: {st.session_state.font_family} !important;
    }}
    
    /* Buton Tasarımları */
    .stButton>button {{
        background-color: {st.session_state.primary_color};
        color: #ffffff !important;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }}
    
    .stButton>button:hover {{
        opacity: 0.85;
        transform: translateY(-1px);
    }}
    
    /* Giriş Kutusu */
    .stTextInput input {{
        font-size: {st.session_state.font_size}px;
        border-radius: 8px;
        border: 1px solid #ccc;
    }}

    /* Sidebar'ı Gizle */
    [data-testid="collapsedControl"] {{ display: none; }}
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ---------------------------------------------------------
# Sayfa 1: ANA SAYFA
# ---------------------------------------------------------
if st.session_state.current_page == "home":
    # Sağ üst köşeye Ayarlar Butonu
    top_col1, top_col2 = st.columns([0.9, 0.1])
    with top_col2:
        if st.button("⚙️ Ayarlar", key="btn_to_settings"):
            st.session_state.current_page = "settings"
            st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Karşılama ve Arama Alanı
    st.markdown("<h1 style='text-align: center;'>Merak ettiğiniz konuyu giriniz</h1>", unsafe_allow_html=True)
    
    col_left, col_center, col_right = st.columns([0.15, 0.7, 0.15])
    with col_center:
        user_input = st.text_input("", placeholder="Aramak istediğiniz kavram veya soruyu yazın...", label_visibility="collapsed")
        
        btn_col1, btn_col2, btn_col3 = st.columns([0.4, 0.2, 0.4])
        with btn_col2:
            if st.button("🔍 ARA", use_container_width=True):
                if user_input.strip():
                    st.session_state.search_query = user_input
                    st.session_state.current_page = "results"
                    st.rerun()
                else:
                    st.warning("Lütfen bir soru veya metin giriniz.")

    st.markdown("<br><br><hr><br>", unsafe_allow_html=True)
    
    # Alttaki Kaynaklar Butonu
    b_col1, b_col2, b_col3 = st.columns([0.4, 0.2, 0.4])
    with b_col2:
        if st.button("📚 Kaynaklar", use_container_width=True):
            st.session_state.current_page = "sources"
            st.rerun()

# ---------------------------------------------------------
# Sayfa 2: KAYNAKLAR
# ---------------------------------------------------------
elif st.session_state.current_page == "sources":
    # Sol Üst Geri Dön Butonu
    if st.button("⬅️ Geri Dön", key="back_from_sources"):
        st.session_state.current_page = "home"
        st.rerun()

    st.title("📚 Kaynak Yönetimi")
    st.markdown("---")

    # Mevcut Kaynakların Listelenmesi
    st.subheader("Kayıtlı Kaynaklar")
    if not st.session_state.sources_list:
        st.info("Henüz yüklenmiş bir kaynak bulunmuyor.")
    else:
        for idx, src in enumerate(st.session_state.sources_list, 1):
            st.write(f"**{idx}.** 📄 {src['name']} *({src['type'].upper()} - {src['size']} KB)*")

    st.markdown("---")

    # Yeni Kaynak Ekleme Alanı
    st.subheader("Yeni Kaynak Ekle")
    uploaded_files = st.file_uploader(
        "TXT veya PDF formatında dosyaları seçin", 
        type=["pdf", "txt"], 
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}"
    )

    if st.button("✅ Tamam (Ekle)"):
        if uploaded_files:
            for file in uploaded_files:
                st.session_state.sources_list.append({
                    "name": file.name,
                    "type": file.name.split(".")[-1],
                    "size": round(file.size / 1024, 2)
                })
            st.success("Yeni kaynaklar başarıyla eklendi!")
            # Uploader kutusunu temizlemek için key değerini değiştirip sayfayı yeniliyoruz
            st.session_state.uploader_key += 1
            st.rerun()
        else:
            st.warning("Lütfen önce yüklenecek bir dosya seçin.")

# ---------------------------------------------------------
# Sayfa 3: AYARLAR
# ---------------------------------------------------------
elif st.session_state.current_page == "settings":
    # Sol Üst Geri Dön
    if st.button("⬅️ Geri Dön", key="back_from_settings"):
        st.session_state.current_page = "home"
        st.rerun()

    st.title("⚙️ Arayüz ve Tema Ayarları")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        new_bg = st.color_picker("Arka Plan Rengi", st.session_state.bg_color)
        new_primary = st.color_picker("Buton ve Vurgu Rengi", st.session_state.primary_color)
        new_text = st.color_picker("Yazı Rengi", st.session_state.text_color)

    with col2:
        new_font_size = st.slider("Yazı Büyüklüğü (px)", 12, 24, st.session_state.font_size)
        new_font_family = st.selectbox(
            "Font Ailesi",
            ["sans-serif", "serif", "monospace", "Arial", "Courier New", "Trebuchet MS"],
            index=0
        )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Kaydet"):
        st.session_state.bg_color = new_bg
        st.session_state.primary_color = new_primary
        st.session_state.text_color = new_text
        st.session_state.font_size = new_font_size
        st.session_state.font_family = new_font_family
        st.success("Ayarlar başarıyla kaydedildi!")
        st.rerun()

# ---------------------------------------------------------
# Sayfa 4: SONUÇLAR VE CEVAP
# ---------------------------------------------------------
elif st.session_state.current_page == "results":
    if st.button("⬅️ Geri Dön", key="back_from_results"):
        st.session_state.current_page = "home"
        st.rerun()

    st.title("🔍 Arama ve Eşleşme Sonuçları")
    st.markdown(f"**Aranan Konu / Soru:** *{st.session_state.search_query}*")
    st.markdown("---")

    # MOCK / TEMSİLİ BULUNAN SAYFA GÖRSELLERİ (RAG Motoru bağlandığında buraya dinamik veriler gelecek)
    mock_results = [
        {"book": "Mekanik_Sistemler_Cilt1.pdf", "page": 42, "score": "%96 Alaka", "img_color": "lightblue", "text": "İlgili konunun ilk geçtiği temel tanım alanı."},
        {"book": "Mekanik_Sistemler_Cilt1.pdf", "page": 43, "score": "%88 Alaka", "img_color": "lightgreen", "text": "Açıklamanın devamı ve formül detayları."},
        {"book": "Tasarim_El_Kitabi.pdf", "page": 105, "score": "%75 Alaka", "img_color": "lightpink", "text": "Farklı bir kaynaktaki benzer kullanım örneği."}
    ]

    st.subheader("🖼️ Bulunan Sayfalar (Görsel İnceleme)")

    # Sayfalar Arası Kaydırma / Slayt Mantığı
    selected_index = st.slider("Sayfalar Arasında Geçiş Yapın", 1, len(mock_results), 1) - 1
    current_item = mock_results[selected_index]

    # Temsili Sayfa Görseli Oluşturma (Görsel olarak gösterme simülasyonu)
    img = Image.new("RGB", (700, 450), color=current_item["img_color"])
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()

    c1, c2, c3 = st.columns([0.1, 0.8, 0.1])
    with c2:
        st.image(
            img, 
            caption=f"Kitap: {current_item['book']} | Sayfa: {current_item['page']} ({current_item['score']})",
            use_container_width=True
        )

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # Alaka Sırasına Göre Liste
    st.subheader("📋 Alakalı Yerler Listesi (Alaka Sırasına Göre)")
    
    for idx, item in enumerate(mock_results, 1):
        with st.expander(f"{idx}. {item['book']} — Sayfa {item['page']} ({item['score']})"):
            st.write(f"**Özet/Metin Bölümü:** {item['text']}")

    st.markdown("<br>", unsafe_allow_html=True)

    # İndirme / Galeriye Kaydetme Butonu (📸 İkonlu)
    st.download_button(
        label="📸 Görseli Galeriye Kaydet",
        data=img_bytes,
        file_name=f"{current_item['book']}_Sayfa_{current_item['page']}.png",
        mime="image/png"
    )
