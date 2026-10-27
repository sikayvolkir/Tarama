import streamlit as st
import io
import PyPDF2
from PIL import Image
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------
# 1. Supabase ve Model Bağlantısı
# ---------------------------------------------------------
# Streamlit Secrets (.streamlit/secrets.toml) veya direkt değerler ile kullanılabilir
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://YOUR_SUPABASE_URL.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "YOUR_SUPABASE_ANON_KEY")

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@st.cache_resource
def load_embedder():
    # Türkçe ve çok dilli metinler için hafif ve etkili açık kaynaklı vektör modeli (384 boyutlu)
    return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

try:
    supabase = init_supabase()
    embedder = load_embedder()
except Exception as e:
    st.error(f"Bağlantı Kurulamadı: {e}")

# ---------------------------------------------------------
# 2. Sayfa Yapılandırması ve Session State
# ---------------------------------------------------------
st.set_page_config(page_title="Akıllı Kaynak ve Arama Asistanı", layout="wide", initial_sidebar_state="collapsed")

if "current_page" not in st.session_state:
    st.session_state.current_page = "home"
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
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ---------------------------------------------------------
# 3. Dinamik CSS
# ---------------------------------------------------------
custom_css = f"""
    <style>
    .stApp {{ background-color: {st.session_state.bg_color}; color: {st.session_state.text_color}; font-family: {st.session_state.font_family}; font-size: {st.session_state.font_size}px; }}
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown {{ color: {st.session_state.text_color} !important; font-family: {st.session_state.font_family} !important; }}
    .stButton>button {{ background-color: {st.session_state.primary_color}; color: #ffffff !important; border-radius: 8px; border: none; padding: 0.5rem 1rem; font-weight: 600; }}
    [data-testid="collapsedControl"] {{ display: none; }}
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ---------------------------------------------------------
# Yardımcı Fonksiyonlar (Arama ve Döküman İşleme)
# ---------------------------------------------------------
def process_and_save_document(file):
    filename = file.name
    file_type = filename.split(".")[-1].lower()
    
    # 1. Supabase 'documents' tablosuna kayıt
    doc_res = supabase.table("documents").insert({"name": filename, "file_type": file_type}).execute()
    doc_id = doc_res.data[0]["id"]

    chunks_to_insert = []

    if file_type == "pdf":
        reader = PyPDF2.PdfReader(file)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                # Sayfa metnini parçala (her ~500 karakter)
                chunk_size = 500
                for i in range(0, len(text), chunk_size):
                    chunk_text = text[i:i+chunk_size]
                    vec = embedder.encode(chunk_text).tolist()
                    chunks_to_insert.append({
                        "document_id": doc_id,
                        "document_name": filename,
                        "page_number": page_num,
                        "content": chunk_text,
                        "embedding": vec
                    })
    elif file_type == "txt":
        text = file.read().decode("utf-8")
        chunk_size = 500
        for i in range(0, len(text), chunk_size):
            chunk_text = text[i:i+chunk_size]
            vec = embedder.encode(chunk_text).tolist()
            chunks_to_insert.append({
                "document_id": doc_id,
                "document_name": filename,
                "page_number": 1,
                "content": chunk_text,
                "embedding": vec
            })

    if chunks_to_insert:
        supabase.table("document_chunks").insert(chunks_to_insert).execute()

def search_in_supabase(query_text):
    # Sadece Supabase veritabanındaki kaynaklarda arama yapar
    query_vector = embedder.encode(query_text).tolist()
    
    response = supabase.rpc(
        "match_chunks",
        {
            "query_embedding": query_vector,
            "match_threshold": 0.25,  # Benzerlik eşiği (0-1 arası)
            "match_count": 5          # En alakalı ilk 5 sonuç
        }
    ).execute()
    
    return response.data

# ---------------------------------------------------------
# Sayfa 1: ANA SAYFA
# ---------------------------------------------------------
if st.session_state.current_page == "home":
    top_col1, top_col2 = st.columns([0.9, 0.1])
    with top_col2:
        if st.button("⚙️ Ayarlar", key="btn_to_settings"):
            st.session_state.current_page = "settings"
            st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
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
    b_col1, b_col2, b_col3 = st.columns([0.4, 0.2, 0.4])
    with b_col2:
        if st.button("📚 Kaynaklar", use_container_width=True):
            st.session_state.current_page = "sources"
            st.rerun()

# ---------------------------------------------------------
# Sayfa 2: KAYNAKLAR
# ---------------------------------------------------------
elif st.session_state.current_page == "sources":
    if st.button("⬅️ Geri Dön", key="back_from_sources"):
        st.session_state.current_page = "home"
        st.rerun()

    st.title("📚 Kaynak Yönetimi")
    st.markdown("---")

    st.subheader("Supabase'de Kayıtlı Kaynaklar")
    # Kayıtlı dökümanları doğrudan Supabase'den çek
    docs_res = supabase.table("documents").select("*").execute()
    existing_docs = docs_res.data if docs_res.data else []

    if not existing_docs:
        st.info("Henüz veritabanında yüklenmiş bir kaynak bulunmuyor.")
    else:
        for idx, src in enumerate(existing_docs, 1):
            st.write(f"**{idx}.** 📄 {src['name']} *({src['file_type'].upper()})*")

    st.markdown("---")
    st.subheader("Yeni Kaynak Ekle")
    uploaded_files = st.file_uploader(
        "TXT veya PDF formatında dosyaları seçin", 
        type=["pdf", "txt"], 
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}"
    )

    if st.button("✅ Tamam (Ekle)"):
        if uploaded_files:
            with st.spinner("Dosyalar Supabase veritabanına işleniyor..."):
                for file in uploaded_files:
                    process_and_save_document(file)
            st.success("Yeni kaynaklar veritabanına eklendi!")
            st.session_state.uploader_key += 1
            st.rerun()
        else:
            st.warning("Lütfen önce yüklenecek bir dosya seçin.")

# ---------------------------------------------------------
# Sayfa 3: AYARLAR
# ---------------------------------------------------------
elif st.session_state.current_page == "settings":
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

    if st.button("💾 Kaydet"):
        st.session_state.bg_color = new_bg
        st.session_state.primary_color = new_primary
        st.session_state.text_color = new_text
        st.session_state.font_size = new_font_size
        st.session_state.font_family = new_font_family
        st.success("Ayarlar kaydedildi!")
        st.rerun()

# ---------------------------------------------------------
# Sayfa 4: SONUÇLAR VE CEVAP (Sadece Gerçek Kaynaklar)
# ---------------------------------------------------------
elif st.session_state.current_page == "results":
    if st.button("⬅️ Geri Dön", key="back_from_results"):
        st.session_state.current_page = "home"
        st.rerun()

    st.title("🔍 Arama Sonuçları")
    st.markdown(f"**Aranan Konu:** *{st.session_state.search_query}*")
    st.markdown("---")

    # SADECE KAYITLI DÖKÜMANLARDA ARAMA YAP
    with st.spinner("Sadece yüklenen kaynaklar taranıyor..."):
        search_results = search_in_supabase(st.session_state.search_query)

    if not search_results:
        st.warning("❌ Yüklenen kaynaklar içerisinde aradığınız konuyla alakalı herhangi bir içerik bulunamadı.")
    else:
        st.subheader("🖼️ Bulunan Sayfalar ve Bölümler")

        selected_index = st.slider("Bulunan Sonuçlar Arasında Geçiş Yapın", 1, len(search_results), 1) - 1
        current_item = search_results[selected_index]
        similarity_pct = int(current_item["similarity"] * 100)

        # Metin Kartı Görselleştirmesi
        st.info(f"**Kitap / Döküman:** {current_item['document_name']} | **Sayfa:** {current_item['page_number']} | **Alaka Oranı:** %{similarity_pct}")
        
        # Temsili Sayfa Kartı Görseli Oluşturma
        img = Image.new("RGB", (700, 300), color="#ffffff")
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        st.markdown(f"> *\"{current_item['content']}\"*")

        st.markdown("<br><hr><br>", unsafe_allow_html=True)
        st.subheader("📋 Alakalı Yerler Listesi (Alaka Sırasına Göre)")

        for idx, item in enumerate(search_results, 1):
            score = int(item["similarity"] * 100)
            with st.expander(f"{idx}. {item['document_name']} — Sayfa {item['page_number']} (%{score} Alaka)"):
                st.write(item["content"])

        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            label="📸 Görseli Galeriye Kaydet",
            data=img_bytes,
            file_name=f"{current_item['document_name']}_Sayfa_{current_item['page_number']}.png",
            mime="image/png"
        )
