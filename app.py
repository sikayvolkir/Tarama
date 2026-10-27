import streamlit as st
import io
import PyPDF2
from PIL import Image, ImageDraw
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

# OCR için gerekli kütüphaneler
try:
    from pdf2image import convert_from_bytes
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

# ---------------------------------------------------------
# 1. Supabase ve Model Bağlantısı
# ---------------------------------------------------------
SUPABASE_URL = "https://zmamzsmfpspenhslskmq.supabase.co"

if "SUPABASE_KEY" in st.secrets:
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
else:
    SUPABASE_KEY = "sb_publishable_U8ENbYwzvXhn5PXi9DNl8Q_hpKisi6x"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@st.cache_resource
def load_embedder():
    return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

try:
    supabase = init_supabase()
    embedder = load_embedder()
except Exception as e:
    st.error(f"Supabase / Model Bağlantı Hatası: {e}")

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
# Yardımcı Fonksiyonlar (OCR ve Anlamsal İşleme Dahil)
# ---------------------------------------------------------
def process_and_save_document(file):
    filename = file.name
    file_bytes = file.read()
    file_type = filename.split(".")[-1].lower()
    
    doc_res = supabase.table("documents").insert({"name": filename, "file_type": file_type}).execute()
    if not doc_res.data:
        st.error("Döküman ana tablosuna kaydedilemedi!")
        return
        
    doc_id = doc_res.data[0]["id"]
    chunks_to_insert = []

    if file_type == "pdf":
        pdf_file = io.BytesIO(file_bytes)
        reader = PyPDF2.PdfReader(pdf_file)
        
        extracted_pages_text = {}
        
        # 1. Adım: Standart PDF metin okuma denenir
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            extracted_pages_text[page_num] = text.strip()

        total_chars = sum(len(t) for t in extracted_pages_text.values())

        # 2. Adım: Eğer metin çıkmadıysa ve OCR kütüphaneleri yüklüyse taranmış görsel PDF olarak işlenir
        if total_chars == 0 and HAS_OCR:
            st.info(f"📷 '{filename}' taranmış görsel PDF olarak algılandı. OCR (Görselden metin okuma) uygulanıyor...")
            try:
                images = convert_from_bytes(file_bytes)
                for page_num, img in enumerate(images, start=1):
                    # Türkçe karakter desteğiyle OCR yapılıyor
                    ocr_text = pytesseract.image_to_string(img, lang='tur')
                    extracted_pages_text[page_num] = ocr_text.strip()
            except Exception as ocr_err:
                st.warning(f"OCR İşlem Hatası: {ocr_err}")

        # Okunan metinler parçalara (chunks) bölünerek vektörleştirilir
        for page_num, text in extracted_pages_text.items():
            if text.strip():
                words = text.split()
                chunk_words = []
                curr_len = 0
                for w in words:
                    chunk_words.append(w)
                    curr_len += len(w) + 1
                    if curr_len >= 500:
                        chunk_text = " ".join(chunk_words)
                        vec = embedder.encode(chunk_text).tolist()
                        chunks_to_insert.append({
                            "document_id": doc_id,
                            "document_name": filename,
                            "page_number": page_num,
                            "content": chunk_text,
                            "embedding": vec
                        })
                        chunk_words = []
                        curr_len = 0
                if chunk_words:
                    chunk_text = " ".join(chunk_words)
                    vec = embedder.encode(chunk_text).tolist()
                    chunks_to_insert.append({
                        "document_id": doc_id,
                        "document_name": filename,
                        "page_number": page_num,
                        "content": chunk_text,
                        "embedding": vec
                    })
                    
    elif file_type == "txt":
        text = file_bytes.decode("utf-8", errors="ignore")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for p_idx, para in enumerate(paragraphs, start=1):
            vec = embedder.encode(para).tolist()
            chunks_to_insert.append({
                "document_id": doc_id,
                "document_name": filename,
                "page_number": p_idx,
                "content": para,
                "embedding": vec
            })

    if chunks_to_insert:
        supabase.table("document_chunks").insert(chunks_to_insert).execute()
        st.success(f"✅ '{filename}' başarıyla işlendi ve {len(chunks_to_insert)} parça veritabanına kaydedildi!")
    else:
        st.error(f"❌ '{filename}' dosyasından hiç metin okunamadı! (Sunucuda Tesseract OCR araçlarının kurulu olduğundan emin olun).")

def search_in_supabase(query_text):
    query_vector = embedder.encode(query_text).tolist()
    
    response = supabase.rpc(
        "match_chunks",
        {
            "query_embedding": query_vector,
            "match_threshold": 0.55,
            "match_count": 5
        }
    ).execute()
    
    return response.data if response.data else []

def delete_document(doc_id):
    supabase.table("documents").delete().eq("id", doc_id).execute()

def generate_result_card(doc_name, page_num, content, score):
    img = Image.new("RGB", (900, 450), color="#ffffff")
    draw = ImageDraw.Draw(img)
    
    draw.rectangle([10, 10, 890, 440], outline="#1e3a8a", width=3)
    draw.rectangle([10, 10, 890, 60], fill="#1e3a8a")
    
    header_text = f"Kaynak: {doc_name} | Sayfa/Bölüm: {page_num} | Alaka: %{score}"
    draw.text((25, 25), header_text, fill="#ffffff")
    
    words = content.split()
    lines = []
    curr_line = ""
    for w in words:
        if len(curr_line) + len(w) > 75:
            lines.append(curr_line)
            curr_line = w + " "
        else:
            curr_line += w + " "
    lines.append(curr_line)
    
    y_pos = 90
    for line in lines[:12]:
        draw.text((30, y_pos), line, fill="#1f2937")
        y_pos += 25
        
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img, img_byte_arr.getvalue()

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
    docs_res = supabase.table("documents").select("*").execute()
    existing_docs = docs_res.data if docs_res.data else []

    if not existing_docs:
        st.info("Henüz veritabanında yüklenmiş bir kaynak bulunmuyor.")
    else:
        for idx, src in enumerate(existing_docs, 1):
            col_doc, col_del = st.columns([0.85, 0.15])
            with col_doc:
                st.write(f"**{idx}.** 📄 {src['name']} *({src['file_type'].upper()})*")
            with col_del:
                if st.button("🗑️ Sil", key=f"del_{src['id']}"):
                    delete_document(src['id'])
                    st.success(f"{src['name']} silindi.")
                    st.rerun()

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
            with st.spinner("Dosyalar okunuyor ve Supabase'e işleniyor..."):
                for file in uploaded_files:
                    process_and_save_document(file)
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
# Sayfa 4: SONUÇLAR VE CEVAP
# ---------------------------------------------------------
elif st.session_state.current_page == "results":
    if st.button("⬅️ Geri Dön", key="back_from_results"):
        st.session_state.current_page = "home"
        st.rerun()

    st.title("🔍 Arama Sonuçları")
    st.markdown(f"**Aranan Konu:** *{st.session_state.search_query}*")
    st.markdown("---")

    with st.spinner("Sadece yüklenen kaynaklar taranıyor..."):
        search_results = search_in_supabase(st.session_state.search_query)

    if not search_results or len(search_results) == 0:
        st.warning("❌ Yüklenen kaynaklar içerisinde aradığınız konuyla alakalı güçlü ve anlamlı bir içerik bulunamadı.")
    else:
        st.subheader("🖼️ Bulunan Sayfalar ve Bölümler (Görsel İnceleme)")

        max_val = len(search_results)
        if max_val > 1:
            selected_index = st.slider("Bulunan Sonuçlar Arasında Geçiş Yapın", 1, max_val, 1) - 1
        else:
            selected_index = 0
            st.info("Tek bir sonuç bulundu.")

        current_item = search_results[selected_index]
        similarity_pct = int(current_item.get("similarity", 0.0) * 100)

        card_img, card_bytes = generate_result_card(
            current_item['document_name'], 
            current_item['page_number'], 
            current_item['content'], 
            similarity_pct
        )

        st.image(card_img, caption=f"{current_item['document_name']} — Sayfa/Bölüm: {current_item['page_number']}", use_container_width=True)

        st.markdown("<br><hr><br>", unsafe_allow_html=True)
        st.subheader("📋 Alakalı Yerler Listesi (Alaka Sırasına Göre)")

        for idx, item in enumerate(search_results, 1):
            score = int(item.get("similarity", 0.0) * 100)
            with st.expander(f"{idx}. {item['document_name']} — Sayfa {item['page_number']} (%{score} Alaka)"):
                st.write(item["content"])

        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            label="📸 Görseli / Kartı Galeriye Kaydet",
            data=card_bytes,
            file_name=f"{current_item['document_name']}_Sayfa_{current_item['page_number']}.png",
            mime="image/png"
        )
