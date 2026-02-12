import sys
import asyncio
import io
import textwrap
import re
import os
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import time
import datetime
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
from modules import scraper, ai_engine, data_manager

# --- BU BLOĞU MUTLAKA EKLE ---
# Streamlit Cloud üzerinde Chromium tarayıcısını kurar
os.system("playwright install chromium")
# -----------------------------

# --- KRİTİK DÜZELTME: Windows & Playwright Uyumluluğu ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- KUPON GÖRSELİ OLUŞTURMA ---
def _normalize_coupon_items(coupon_data):
    items = coupon_data
    if isinstance(items, str):
        try:
            import json as _json
            items = _json.loads(items)
        except Exception:
            items = []
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        items = []
    return items

def _extract_odd_value(odd_val):
    import re
    val_str = str(odd_val).strip().replace(",", ".")

    # Aralık Kontrolü (Örn: "1.45 - 1.60")
    if "-" in val_str:
        try:
            parts = val_str.split("-")
            # Her parçadaki sayıyı bul (örn: " 1.45 " -> 1.45)
            nums = []
            for p in parts:
                match = re.search(r"\d+(?:\.\d+)?", p)
                if match:
                    nums.append(float(match.group(0)))
            
            if len(nums) >= 2:
                # Aralığın ortalamasını al
                return sum(nums) / len(nums)
            elif len(nums) == 1:
                return nums[0]
        except Exception:
            pass

    # Tekil Sayı Kontrolü (Eski usul devam)
    match_odd = re.search(r"\d+(?:\.\d+)?", val_str)
    if match_odd:
        try:
            return float(match_odd.group(0))
        except Exception:
            return None
    return None

def create_coupon_image(coupon_data, total_odd):
    items = _normalize_coupon_items(coupon_data)
    width = 400
    row_height = 60
    base_height = 260
    warning_text = (
        "UYARI: Bu oranlar yapay zeka tahminidir. Gerçek büro oranları farklı "
        "olabilir. Yatırım tavsiyesi değildir."
    )
    warning_lines = textwrap.wrap(warning_text, width=46)
    warning_line_height = 14
    warning_h = warning_line_height * len(warning_lines) + 16
    height = max(600, base_height + len(items) * row_height) + warning_h

    img = Image.new("RGB", (width, height), color="#f1f5f9")
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_date = ImageFont.truetype("arial.ttf", 12)
        font_match = ImageFont.truetype("arial.ttf", 14)
        font_body = ImageFont.truetype("arial.ttf", 12)
        font_footer = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font_title = ImageFont.load_default()
        font_date = ImageFont.load_default()
        font_match = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_footer = ImageFont.load_default()

    header_h = 70
    footer_h = 60
    footer_top = height - warning_h - footer_h
    draw.rectangle([0, 0, width, header_h], fill="#0f172a")
    draw.text((20, 15), "AKIL HOCASI PRO", fill="white", font=font_title)
    date_text = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    draw.text((20, 40), date_text, fill="white", font=font_date)

    y = header_h + 15
    for item in items:
        match = str(item.get("mac", "-"))
        prediction = str(item.get("tahmin", "-"))
        odd_val = str(item.get("oran_tahmini", "-"))

        draw.text((20, y), match, fill="black", font=font_match)
        y += 20
        draw.text((20, y), f"{prediction}", fill="#2563eb", font=font_body)
        draw.text((250, y), f"Oran: {odd_val}", fill="black", font=font_body)
        y += 22
        draw.line([(20, y), (width - 20, y)], fill="#e2e8f0", width=1)
        y += 18
        if y > footer_top - 20:
            break

    draw.rectangle([0, footer_top, width, footer_top + footer_h], fill="#22c55e")
    draw.text((20, footer_top + 18), f"TOPLAM ORAN: {total_odd}", fill="white", font=font_footer)

    warn_y = footer_top + footer_h + 8
    for line in warning_lines:
        text_w = draw.textlength(line, font=font_body)
        draw.text(((width - text_w) / 2, warn_y), line, fill="#64748b", font=font_body)
        warn_y += warning_line_height

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

def show_full_page_loader(status_text="Yapay Zeka Verileri İşliyor..."):
    """
    Tüm sayfayı kaplayan, blur efektli modern bir yükleme ekranı gösterir.
    """
    loading_html = f"""
    <style>
        /* Tam Ekran Kaplama */
        .stApp {{ overflow: hidden; }} /* Kaydırmayı engelle */
        .loader-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(11, 17, 32, 0.95); /* Derin Lacivert, Yüksek Opaklık */
            backdrop-filter: blur(8px);
            z-index: 999999;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            color: #4ade80;
            font-family: 'Poppins', sans-serif;
        }}
        
        /* Radar Animasyonu */
        .radar-container {{
            position: relative;
            width: 120px;
            height: 120px;
            margin-bottom: 30px;
        }}
        
        .radar-circle {{
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            border: 2px solid rgba(74, 222, 128, 0.3);
            border-radius: 50%;
            box-shadow: 0 0 30px rgba(74, 222, 128, 0.1);
        }}
        
        .radar-scanner {{
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            border-radius: 50%;
            background: conic-gradient(from 0deg, transparent 0%, transparent 60%, rgba(74, 222, 128, 0.6) 100%);
            animation: radar-spin 1.5s linear infinite;
        }}
        
        .football-core {{
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            width: 50px; height: 50px;
            background: #4ade80;
            border-radius: 50%;
            box-shadow: 0 0 20px #4ade80;
            animation: core-pulse 1.5s ease-in-out infinite;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            color: #0b1120;
        }}
        
        /* Animasyon Keyframes */
        @keyframes radar-spin {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}
        
        @keyframes core-pulse {{
            0% {{ transform: translate(-50%, -50%) scale(0.9); opacity: 0.8; }}
            50% {{ transform: translate(-50%, -50%) scale(1.1); opacity: 1; box-shadow: 0 0 40px #4ade80; }}
            100% {{ transform: translate(-50%, -50%) scale(0.9); opacity: 0.8; }}
        }}
        
        .loading-text {{
            font-size: 1.5rem;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            animation: text-blink 2s infinite;
        }}
        
        @keyframes text-blink {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
    </style>
    
    <div class="loader-overlay">
        <div class="radar-container">
            <div class="radar-circle"></div>
            <div class="radar-scanner"></div>
            <div class="football-core">⚽</div>
        </div>
        <div class="loading-text">{status_text}</div>
    </div>
    """
    
    # Placeholder oluştur ve HTML'i içine bas
    placeholder = st.empty()
    placeholder.markdown(loading_html, unsafe_allow_html=True)
    return placeholder

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Akıl Hocası Pro ⚽", page_icon="🏟️", layout="wide")

# --- 1. API KEY KONTROL VE GİRİŞ EKRANI ---
if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = ""

if not st.session_state.get('api_key_submitted', False):
    st.markdown("""
    <style>
        .stApp { background-color: #0f172a; }
        .login-container {
            max-width: 500px;
            margin: 100px auto;
            padding: 40px;
            border-radius: 20px;
            background: rgba(30, 41, 59, 0.5);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
            text-align: center;
        }
        .login-title {
            background: linear-gradient(to right, #4ade80, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 3rem;
            font-weight: 800;
            margin-bottom: 10px;
        }
        .login-subtitle { color: #94a3b8; margin-bottom: 30px; font-size: 1.1rem; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-title">AKIL HOCASI PRO</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">Yapay Zeka Destekli Futbol Analiz Asistanı</div>', unsafe_allow_html=True)
        
        with st.form("key_form"):
            user_key = st.text_input("🔑 Google Gemini API Key", type="password", placeholder="AIzaSy... ile başlayan anahtarınızı girin")
            submitted = st.form_submit_button("Sisteme Giriş Yap 🚀", use_container_width=True)
            
            if submitted:
                if user_key.startswith("AIza"):
                    st.session_state.gemini_api_key = user_key
                    st.session_state.api_key_submitted = True
                    st.success("Giriş Başarılı! Yükleniyor...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Lütfen geçerli bir API Key giriniz.")
        
        with st.expander("❓ API Key Nasıl Alınır?"):
            st.markdown("Google AI Studio'dan (aistudio.google.com) ücretsiz API key alarak sistemi kullanmaya başlayabilirsiniz.")
            
    st.stop()

# --- API KEY KONFİGÜRASYONU ---
try:
    genai.configure(api_key=st.session_state.gemini_api_key)
    ai_engine.set_api_key(st.session_state.gemini_api_key)
except Exception as e:
    st.error(f"API Key hatası: {e}")
    st.stop()

# --- CHAT STATE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_analysis_context" not in st.session_state:
    st.session_state.current_analysis_context = None
if "current_analysis_match" not in st.session_state:
    st.session_state.current_analysis_match = {}
if "league_cache" not in st.session_state:
    st.session_state.league_cache = {}
if "wizard_step" not in st.session_state:
    st.session_state.wizard_step = 1
if "show_wizard" not in st.session_state:
    st.session_state.show_wizard = False
if "risk_profile" not in st.session_state:
    st.session_state.risk_profile = "🛡️ BANKO"
if "game_focus" not in st.session_state:
    st.session_state.game_focus = "🤖 Yapay Zeka Tercihi"
if "analyze_limit" not in st.session_state:
    st.session_state.analyze_limit = 8
if "wizard_date_range" not in st.session_state:
    st.session_state.wizard_date_range = (
        datetime.date.today(),
        datetime.date.today() + datetime.timedelta(days=1)
    )
if "start_analysis" not in st.session_state:
    st.session_state.start_analysis = False
if "wizard_leagues" not in st.session_state:
    st.session_state.wizard_leagues = []
if "wizard_combined_matches" not in st.session_state:
    st.session_state.wizard_combined_matches = []
if "wizard_blacklist" not in st.session_state:
    st.session_state.wizard_blacklist = []
if "wizard_c_count" not in st.session_state:
    st.session_state.wizard_c_count = 3
if "wizard_only_big_teams" not in st.session_state:
    st.session_state.wizard_only_big_teams = False
if "wizard_analyze_limit" not in st.session_state:
    st.session_state.wizard_analyze_limit = 8
if "wizard_params" not in st.session_state:
    st.session_state.wizard_params = {}

combined_matches = []
create_btn = False
wiz_leagues = []

# --- DEVLER LİSTESİ (KUPON MÜHENDİSİ FİLTRESİ) ---
BIG_TEAMS = [
    "Galatasaray", "Fenerbahçe", "Beşiktaş", "Trabzonspor",
    "Manchester City", "Liverpool", "Arsenal", "Manchester Utd", "Chelsea",
    "Real Madrid", "Barcelona", "Atletico Madrid",
    "Bayern Munchen", "Dortmund", "Leverkusen",
    "PSG", "Monaco", "Lille",
    "Inter", "Milan", "Juventus", "Napoli"
]

def _is_big_team(team_name):
    if not team_name:
        return False
    team_lower = str(team_name).lower()
    return any(big_team.lower() in team_lower for big_team in BIG_TEAMS)

def open_wizard_trigger():
    st.session_state.show_wizard = True
    st.session_state.wizard_step = 1

@st.dialog("🎯 Kupon Tasarım Sihirbazı")
def show_coupon_wizard():
    with st.container():
        # --- ADIM 3: FİNAL AYARLAR (Limitler ve Tarih) ---
        if st.session_state.wizard_step == 3:
            st.markdown("### 🛠️ Adım 3: İnce Ayarlar")
            
            # 1. TARİH FİLTRESİ (YENİ EKLENDİ)
            st.markdown("#### 📅 Tarih Aralığı")
            st.session_state.wizard_date_range = st.date_input(
                "Hangi tarihli maçlar taransın?",
                value=st.session_state.wizard_date_range,
                min_value=datetime.date.today(),
                format="DD.MM.YYYY"
            )
            
            col_limit, col_count = st.columns(2)
            
            # 2. TARANACAK HAVUZ SLIDER (YENİ EKLENDİ)
            with col_limit:
                st.markdown("#### 🔍 Tarama Havuzu")
                st.session_state.analyze_limit = st.slider(
                    "Kaç maç analiz edilsin?",
                    min_value=5,
                    max_value=20,
                    value=st.session_state.analyze_limit,
                    help="Sayı arttıkça yapay zeka daha fazla maçı inceler ama işlem süresi uzar."
                )
                st.caption(f"⚠️ Tahmini Süre: ~{st.session_state.analyze_limit * 8} saniye")

            # 3. KUPON MAÇ SAYISI
            with col_count:
                st.markdown("#### 🎫 Maç Sayısı")
                st.session_state.wizard_c_count = st.slider(
                    "Kuponda kaç maç olsun?",
                    min_value=1,
                    max_value=5,
                    value=st.session_state.wizard_c_count
                )

            st.markdown("---")
            
            # 4. FİLTRELER
            st.session_state.wizard_only_big_teams = st.checkbox(
                "🏆 Sadece Büyük Takımlar (Devler Ligi)",
                value=st.session_state.wizard_only_big_teams
            )

            combined_matches = st.session_state.get("wizard_combined_matches", [])
            all_teams = sorted(
                {m.get("home") for m in combined_matches if m.get("home")}
                | {m.get("away") for m in combined_matches if m.get("away")}
            )
            st.session_state.wizard_blacklist = st.multiselect(
                "⛔ Kara Liste (Bu Takımları Pas Geç)",
                options=all_teams,
                default=st.session_state.wizard_blacklist
            )

            col_back, col_finish = st.columns([1, 2])
            with col_back:
                if st.button("⬅️ Geri", use_container_width=True):
                    st.session_state.wizard_step = 2
                    st.session_state.show_wizard = True
                    st.rerun()
            
            with col_finish:
                if st.button("Mühendisliği Başlat ve Kuponu Yarat 🚀", type="primary", use_container_width=True):
                    st.session_state.wizard_params = {
                        "c_count": st.session_state.wizard_c_count,
                        "analyze_limit": st.session_state.analyze_limit,
                        "risk_profile": st.session_state.risk_profile,
                        "game_focus": st.session_state.game_focus,
                        "blacklist": st.session_state.wizard_blacklist,
                        "only_big_teams": st.session_state.wizard_only_big_teams,
                        "date_range": st.session_state.wizard_date_range
                    }
                    st.session_state.start_analysis = True
                    st.session_state.show_wizard = False
                    st.session_state.wizard_step = 1
                    st.rerun()
            return

        # --- ADIM 2: STRATEJİ ---
        if st.session_state.wizard_step == 2:
            st.markdown("""
            <style>
            .wizard-card {
                border: 1px solid #334155;
                border-radius: 14px;
                padding: 16px;
                background: rgba(15, 23, 42, 0.6);
                text-align: center;
                margin-bottom: 10px;
                cursor: pointer;
                transition: all 0.3s;
            }
            .wizard-card:hover { border-color: #60a5fa; }
            .wizard-card.selected {
                border: 2px solid #3b82f6;
                background: rgba(59, 130, 246, 0.1);
                box-shadow: 0 0 16px rgba(59, 130, 246, 0.35);
            }
            .wizard-icon { font-size: 2rem; margin-bottom: 6px; }
            .wizard-title { font-weight: 800; font-size: 1.05rem; color: white; }
            .wizard-desc { color: #94a3b8; font-size: 0.85rem; margin-top: 6px; }
            </style>
            """, unsafe_allow_html=True)

            st.write("### Adım 2: Kupon Stratejisi")
            
            # Risk Kartları
            st.markdown("#### Risk Profili")
            risk_options = [
                ("🛡️ BANKO", "Düşük Risk, Yüksek Olasılık"),
                ("⚖️ İDEAL", "Dengeli Kazanç ve Risk"),
                ("💣 SÜRPRİZ", "Yüksek Oran, Maksimum Risk")
            ]
            cols = st.columns(3)
            for idx, (title, desc) in enumerate(risk_options):
                with cols[idx]:
                    is_selected = st.session_state.risk_profile == title
                    card_class = "wizard-card selected" if is_selected else "wizard-card"
                    st.markdown(
                        f"""
                        <div class="{card_class}">
                            <div class="wizard-icon">{title.split()[0]}</div>
                            <div class="wizard-title">{title}</div>
                            <div class="wizard-desc">{desc}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    if st.button("Seç", key=f"risk_btn_{idx}", use_container_width=True):
                        st.session_state.risk_profile = title
                        st.session_state.show_wizard = True
                        st.rerun() # Seçim yapınca görsel güncellensin

            # Odak Noktası
            st.markdown("#### Oyun Odak Noktası")
            focus_options = ["🤖 Yapay Zeka Tercihi", "⚽ Gol Odaklı", "🥅 Taraf Odaklı", "🚩 Özel Bahisler"]
            
            # Pills varsa kullan yoksa radio
            if hasattr(st, "pills"):
                st.session_state.game_focus = st.pills("Odak", focus_options, default=st.session_state.game_focus, label_visibility="collapsed")
            else:
                st.session_state.game_focus = st.radio("Odak", focus_options, horizontal=True, label_visibility="collapsed")

            nav_l, nav_r = st.columns(2)
            with nav_l:
                if st.button("⬅️ Geri", use_container_width=True):
                    st.session_state.wizard_step = 1
                    st.session_state.show_wizard = True
                    st.rerun()
            with nav_r:
                if st.button("Sonraki Adım ➡️", use_container_width=True):
                    st.session_state.wizard_step = 3
                    st.session_state.show_wizard = True
                    st.rerun()
            return

        # --- ADIM 1: LİG SEÇİMİ ---
        st.write("### Adım 1: Kapsam Belirleme")
        
        # Lig listesi cache kontrolü
        available_leagues = list(st.session_state.leagues_map.keys())
        pre_selected = list(st.session_state.league_cache.keys())
        
        wiz_leagues = st.multiselect(
            "Ligleri Seç",
            options=available_leagues,
            default=pre_selected
        )
        st.session_state.wizard_leagues = wiz_leagues

        # Eksik veri kontrolü
        missing_leagues = [L for L in wiz_leagues if L not in st.session_state.league_cache]
        
        if missing_leagues:
            st.warning(f"⚠️ Verisi eksik ligler: {', '.join(missing_leagues)}")
            if st.button("📥 Eksik Verileri Şimdi İndir", type="primary"):
                progress = st.progress(0)
                for i, lname in enumerate(missing_leagues):
                    l_val = st.session_state.leagues_map[lname]
                    data = scraper.get_fixture_and_standings(l_val)
                    for m in data["matches"]:
                        m["league_name"] = lname
                    st.session_state.league_cache[lname] = data["matches"]
                    progress.progress((i+1)/len(missing_leagues))
                st.success("Veriler tamamlandı!")
                st.rerun()
        else:
            # Maç sayısını hesapla
            total_m = sum([len(st.session_state.league_cache.get(l, [])) for l in wiz_leagues])
            st.session_state.wizard_combined_matches = []
            for l in wiz_leagues:
                st.session_state.wizard_combined_matches.extend(st.session_state.league_cache.get(l, []))
                
            if total_m > 0:
                st.success(f"✅ Analize Hazır: {total_m} Maç")
                if st.button("Sonraki Adım ➡️", use_container_width=True):
                    st.session_state.wizard_step = 2
                    st.session_state.show_wizard = True
                    st.rerun()
            else:
                st.info("Lütfen en az bir lig seçin.")

# --- MODERN CSS & TASARIM ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Poppins:wght@500;700;800&display=swap');

    /* Genel Ayarlar */
    .stApp { background-color: #0B1120; } /* Derin Lacivert */
    body, p, span, .metric-label {
        font-family: 'Inter', sans-serif;
    }
    h1, h2, h3, .main-title, .team-name, .league-name {
        font-family: 'Poppins', sans-serif;
    }

    /* Buton Hiyerarşisi */
    .stButton > button {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: white;
        padding: 0.5rem 1rem;
        min-height: 45px;
        font-size: 16px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        border-color: #3b82f6;
        color: #3b82f6;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        border: none;
        color: white;
        font-weight: 700;
        box-shadow: 0 6px 18px rgba(59, 130, 246, 0.25);
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 8px 24px rgba(139, 92, 246, 0.35);
    }

    /* Custom Scrollbar */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #0B1120; }
    ::-webkit-scrollbar-thumb { background: #1f2937; border-radius: 6px; }
    ::-webkit-scrollbar-thumb:hover { background: #334155; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #0B1120;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    section[data-testid="stSidebar"] .sidebar-logo {
        width: 90px;
        height: 90px;
        border-radius: 50%;
        padding: 8px;
        background: radial-gradient(circle at center, rgba(59,130,246,0.35), rgba(15,23,42,0.2));
        box-shadow: 0 0 20px rgba(59,130,246,0.45);
        margin: 0 auto 10px;
        display: block;
    }
    section[data-testid="stSidebar"] .sidebar-section-title {
        font-family: 'Poppins', sans-serif;
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 1px;
        color: #e2e8f0;
        text-transform: uppercase;
        margin-bottom: 0.6rem;
    }
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(59, 130, 246, 0.5);
        color: #e2e8f0;
    }
    section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {
        color: #e2e8f0;
    }
    section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[role="slider"] {
        background: #3b82f6;
        border: 2px solid #60a5fa;
    }
    section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[aria-hidden="true"] {
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
    }
    
    /* Başlık Stili */
    .main-title {
        font-size: 3.5rem;
        font-weight: 900;
        text-align: center;
        background: linear-gradient(to right, #60a5fa, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
        letter-spacing: -2px;
    }
    .sub-title {
        font-size: 1.2rem;
        color: #94a3b8;
        text-align: center;
        margin-bottom: 3rem;
        font-weight: 300;
    }

    /* --- SKORBORD TASARIMI --- */
    .match-header-container {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 40px 20px;
        border-radius: 24px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        display: flex;
        justify-content: space-around;
        align-items: center;
        margin-bottom: 30px;
        box-shadow: 0 20px 50px -12px rgba(0, 0, 0, 0.5);
        position: relative;
        overflow: hidden;
    }
    .match-header-container::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: radial-gradient(circle at center, rgba(59, 130, 246, 0.15) 0%, transparent 70%);
        pointer-events: none;
    }
    
    .team-container { text-align: center; width: 35%; z-index: 1; }
    
    .team-avatar {
        width: 90px;
        height: 90px;
        border-radius: 50%;
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
        font-size: 2.5rem;
        font-weight: 800;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 15px auto;
        box-shadow: 0 0 30px rgba(59, 130, 246, 0.4);
        border: 4px solid rgba(255,255,255,0.1);
    }
    .team-avatar.away {
        background: linear-gradient(135deg, #ef4444, #dc2626);
        box-shadow: 0 0 30px rgba(239, 68, 68, 0.4);
    }
    
    .team-name {
        font-size: 1.6rem;
        font-weight: 800;
        color: #f8fafc;
        text-transform: uppercase;
        letter-spacing: 1px;
        text-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }
    .team-role {
        font-size: 0.75rem;
        font-weight: 700;
        color: #94a3b8;
        background: rgba(15, 23, 42, 0.6);
        padding: 6px 12px;
        border-radius: 20px;
        display: inline-block;
        margin-top: 8px;
        border: 1px solid rgba(255,255,255,0.05);
    }

    .league-card {
        background: linear-gradient(145deg, #1e293b, #0f172a);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.05);
        transition: transform 0.3s, box-shadow 0.3s;
        cursor: pointer;
        height: 200px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        align-items: center;
    }
    .league-card:hover {
        transform: translateY(-10px);
        box-shadow: 0 20px 40px rgba(0,0,0,0.4);
        border-color: #3b82f6;
    }
    .league-img {
        height: 80px;
        object-fit: contain;
        margin-bottom: 15px;
        filter: drop-shadow(0 0 10px rgba(255,255,255,0.2));
    }
    .league-name {
        color: white;
        font-weight: bold;
        font-size: 1.1rem;
    }
    
    .vs-badge {
        width: 70px;
        height: 70px;
        background: #0f172a;
        color: #cbd5e1;
        border-radius: 50%;
        font-weight: 900;
        font-style: italic;
        font-size: 1.8rem;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 2px solid #334155;
        z-index: 2;
        box-shadow: 0 0 20px rgba(0,0,0,0.5);
    }

    /* --- GLASSMORPHISM KARTLAR --- */
    .metric-card {
        background: rgba(30, 41, 59, 0.4);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 25px;
        text-align: center;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        position: relative;
        overflow: hidden;
    }
    .metric-card:hover {
        transform: translateY(-8px);
        background: rgba(30, 41, 59, 0.7);
        border-color: rgba(59, 130, 246, 0.5);
        box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.3);
    }
    .metric-label {
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 10px;
        font-weight: 600;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: white;
    }
    
    /* Kart Renkleri */
    .card-green .metric-value { color: #4ade80; text-shadow: 0 0 20px rgba(74, 222, 128, 0.3); }
    .card-blue .metric-value { color: #60a5fa; text-shadow: 0 0 20px rgba(96, 165, 250, 0.3); }
    .card-yellow .metric-value { color: #facc15; text-shadow: 0 0 20px rgba(250, 204, 21, 0.3); }
    .card-purple .metric-value { color: #c084fc; text-shadow: 0 0 20px rgba(192, 132, 252, 0.3); }

    /* --- KUPON & TOOLTIP --- */
    .bet-pick-row { display: flex; align-items: center; gap: 6px; }
    .reason-toggle { 
        display: inline-flex; align-items: center; 
        cursor: pointer; 
        user-select: none;
    }
    .reason-toggle summary {
        list-style: none;
    }
    .reason-toggle summary::-webkit-details-marker { display: none; }
    .reason-icon { 
        display: inline-flex; justify-content: center; align-items: center; 
        width: 18px; height: 18px; 
        background: rgba(59, 130, 246, 0.2); 
        color: #60a5fa; 
        border-radius: 50%; 
        font-size: 11px; font-weight: bold; 
        border: 1px solid rgba(96, 165, 250, 0.3);
        transition: all 0.2s;
    }
    .reason-toggle[open] .reason-icon { background: #3b82f6; color: white; }
    .reason-icon.riskli { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
    .reason-toggle[open] .reason-icon.riskli { background: #ef4444; color: white; }
    .reason-text { 
        margin-top: 8px;
        background-color: #0f172a; 
        color: #cbd5e1; 
        text-align: left; 
        border-radius: 8px; 
        padding: 12px; 
        font-size: 0.8rem; font-weight: 400; line-height: 1.5;
        border: 1px solid #334155; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.5); 
        white-space: normal;
        box-sizing: border-box;
    }
    
    /* Kupon Modal */
    .coupon-toggle { 
        position: fixed; bottom: 30px; right: 30px; 
        background-color: #1e293b; 
        color: #4ade80; 
        border: 1px solid #334155; 
        border-radius: 50px; 
        padding: 12px 20px; 
        cursor: pointer; z-index: 9999; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.4); 
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); 
        display: flex; align-items: center; gap: 10px; 
        min-height: 52px;
        text-decoration: none;
    }
    .coupon-toggle > span { font-size: 1.3rem; line-height: 1; }
    .coupon-toggle-text { display: flex; flex-direction: column; line-height: 1.1; }
    .coupon-toggle-label { font-size: 0.7rem; color: #94a3b8; }
    .coupon-toggle-value { font-size: 1.05rem; font-weight: 700; }
    .coupon-toggle:hover { transform: scale(1.05) translateY(-5px); background-color: #334155; }
    
    .coupon-modal { 
        position: fixed; bottom: 100px; right: 30px; 
        width: 380px; 
        background-color: #1e293b; 
        border-radius: 16px; 
        border: 1px solid #334155; 
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); 
        z-index: 9998; 
        opacity: 0; visibility: hidden; 
        transform: translateY(20px) scale(0.95); 
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); 
        overflow: visible; 
        pointer-events: none;
    }
    .coupon-modal:target { opacity: 1; visibility: visible; transform: translateY(0) scale(1); pointer-events: auto; }
    
    .modal-header { background: #0f172a; padding: 16px 20px; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; color: white; font-weight: 700; font-size: 1rem; }
    .modal-body { max-height: 450px; overflow-y: auto; overflow-x: hidden; padding: 0; }
    .bet-item { padding: 16px 20px; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; transition: background 0.2s; overflow: visible; position: relative; }
    .bet-item:hover { background: rgba(255,255,255,0.02); }
    .bet-item.riskli { background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; }
    .bet-match { font-weight: 700; margin-bottom: 4px; color: #f1f5f9; font-size: 0.95rem; }
    .bet-pick { color: #60a5fa; font-size: 0.9rem; font-weight: 600; }
    .bet-item.riskli .bet-pick { color: #fca5a5; }
    .bet-conf { color: #64748b; font-size: 0.8rem; }
    .bet-odd { background: #0f172a; color: #4ade80; padding: 6px 12px; border-radius: 8px; font-weight: 700; border: 1px solid #334155; font-size: 0.95rem; min-width: 60px; text-align: center;}
    .modal-footer { background: #0f172a; padding: 20px; border-top: 1px solid #334155; }
    .total-row { display: flex; justify-content: space-between; align-items: center; color: white; font-size: 1.2rem; font-weight: 800; margin-bottom: 10px; }
    .total-val { color: #4ade80; text-shadow: 0 0 15px rgba(74, 222, 128, 0.4); }
    .disclaimer { font-size: 0.7rem; color: #64748b; text-align: center; line-height: 1.4; }
</style>
""", unsafe_allow_html=True)

# --- YAN MENÜ ---
with st.sidebar:
    st.markdown(
        "<img class='sidebar-logo' src='https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Football_icon.svg/1024px-Football_icon.svg.png'/>",
        unsafe_allow_html=True
    )

    if 'leagues_map' not in st.session_state:
        with st.spinner("Lig listesi yükleniyor..."):
            st.session_state.leagues_map = scraper.get_leagues_list()

    if st.session_state.leagues_map:
        league_names = list(st.session_state.leagues_map.keys())
        default_idx = next((i for i, n in enumerate(league_names) if "TÜRKİYE Süper Lig" in n), 0)
        if st.session_state.get("pending_league_key"):
            st.session_state.sb_selected_league = st.session_state.pending_league_key
            del st.session_state.pending_league_key
        elif "sb_selected_league" not in st.session_state:
            st.session_state.sb_selected_league = league_names[default_idx]

        with st.expander("📍 LİG VE TARİH", expanded=True):
            st.markdown("<div class='sidebar-section-title'>Lig Seçimi</div>", unsafe_allow_html=True)
            selected_league_name = st.selectbox("Lig Seç", league_names, key="sb_selected_league")
            selected_league_value = st.session_state.leagues_map[selected_league_name]

            if st.button("📥 Verileri Getir", type="primary", use_container_width=True):
                # --- LOADER BAŞLAT ---
                loader = show_full_page_loader("📥 Lig Verileri İndiriliyor...")
                try:
                    data = scraper.get_fixture_and_standings(selected_league_value)
                    for m in data["matches"]:
                        m["league_name"] = selected_league_name
                    st.session_state.current_fixture = data["matches"]
                    st.session_state.league_cache[selected_league_name] = data["matches"]
                    st.session_state.current_standings = data["standings"]
                    if 'league_stats' in st.session_state: del st.session_state.league_stats
                    
                    st.success("Hazır!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Veri hatası: {e}")
                finally:
                    # İşlem bitince animasyonu kaldır
                    loader.empty()

        with st.expander("⚙️ KUPON AYARLARI", expanded=True):
            st.markdown("<div class='sidebar-section-title'>Sihirbaz</div>", unsafe_allow_html=True)
            st.button(
                "🎯 Yeni Kupon Tasarla",
                use_container_width=True,
                on_click=open_wizard_trigger
            )

        with st.expander("🔑 SİSTEM", expanded=False):
            st.markdown("<div class='sidebar-section-title'>Hesap</div>", unsafe_allow_html=True)
            if st.button("🚪 Çıkış Yap / Key Değiştir", use_container_width=True):
                st.session_state.api_key_submitted = False
                st.rerun()

        with st.container():
            st.markdown("---")
            st.markdown("<div class='sidebar-section-title'>Sistem Durumu</div>", unsafe_allow_html=True)
            is_active = bool(st.session_state.get("gemini_api_key"))
            status_color = "#22c55e" if is_active else "#ef4444"
            status_text = "Sistem Aktif" if is_active else "Bağlantı Yok"
            st.markdown(
                f"<div style='display:flex; align-items:center; gap:8px;'>"
                f"<span style='width:10px; height:10px; border-radius:50%; background:{status_color}; display:inline-block;'></span>"
                f"<span style='color:#e2e8f0;'>{status_text}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

if st.session_state.show_wizard:
    show_coupon_wizard()


# --- ANA EKRAN ---
st.markdown('<div class="main-title">AKIL HOCASI PRO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Yapay Zeka Destekli Futbol Analiz Asistanı</div>', unsafe_allow_html=True)

# --- KUPON OLUŞTURMA ---
if st.session_state.get("start_analysis"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    collected_matches = []
    combined_matches = st.session_state.get("wizard_combined_matches", [])
    total_matches = len(combined_matches)
    wizard_params = st.session_state.get("wizard_params", {})
    c_count = wizard_params.get("c_count", st.session_state.wizard_c_count)
    analyze_limit = wizard_params.get("analyze_limit", st.session_state.analyze_limit)
    only_big_teams = wizard_params.get("only_big_teams", st.session_state.wizard_only_big_teams)
    blacklist = wizard_params.get("blacklist", st.session_state.wizard_blacklist)
    date_range = wizard_params.get("date_range", st.session_state.wizard_date_range)
    if isinstance(date_range, datetime.date):
        date_range = (date_range, date_range)
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        date_start, date_end = date_range
    else:
        date_start, date_end = None, None
    
    status_text.text("🔍 Havuz filtreleniyor (Tarih ve Kriterler)...")
    for idx, m in enumerate(combined_matches):
        match_date = None
        raw_date = m.get("date", "")
        if isinstance(raw_date, datetime.datetime):
            match_date = raw_date.date()
        elif isinstance(raw_date, datetime.date):
            match_date = raw_date
        elif raw_date:
            date_text = str(raw_date)
            date_match = re.search(r"(\d{1,2})[./-](\d{1,2})", date_text)
            if date_match:
                try:
                    day = int(date_match.group(1))
                    month = int(date_match.group(2))
                    year = datetime.date.today().year
                    match_date = datetime.date(year, month, day)
                except Exception:
                    match_date = None

        if date_start and date_end:
            if match_date is None:
                continue
            if not (date_start <= match_date <= date_end):
                continue
        if only_big_teams:
            if not (_is_big_team(m.get("home")) or _is_big_team(m.get("away"))):
                continue
        if blacklist:
            if m.get("home") in blacklist or m.get("away") in blacklist:
                continue
        collected_matches.append(m)
        if total_matches:
            progress_bar.progress((idx + 1) / total_matches)
    
    if only_big_teams:
        status_text.text(f"🔍 Kriterlere uygun {len(collected_matches)} Dev Maç bulundu")
    
    if not collected_matches:
        st.error(f"❌ Kriterlere uygun maç bulunamadı.")
    else:
        # --- LOADER BAŞLAT ---
        loader_placeholder = show_full_page_loader("🧠 Yapay Zeka Kuponu Tasarlıyor...")
        try:
            status_text.text(f"🧠 {len(collected_matches)} maç analiz ediliyor...")
            pool = collected_matches[:analyze_limit]
            ai_pool = []
            
            for i, m in enumerate(pool):
                status_text.text(f"Analiz: {m['home']} vs {m['away']}")
                try:
                    details = scraper.get_match_deep_stats(m['url'])
                    ai_pool.append({
                        "home": m['home'], "away": m['away'], "lig": m['league_name'],
                        "insights": details["yellow_box"],
                        "stats": "Detaylı analiz yapılıyor..."
                    })
                except: pass
                progress_bar.progress((i+1)/len(pool))
                
            status_text.text("🤖 Kupon oluşturuluyor...")
            c_type = (
                f"{wizard_params.get('risk_profile', st.session_state.risk_profile)} | "
                f"Odak: {wizard_params.get('game_focus', st.session_state.game_focus)}. "
                "(ÖNEMLİ: Banko seçildiyse taraf bahsi zorunlu değil, "
                "istatistiksel olasılığı en yüksek tercihi yap.)"
            )
            coupon = ai_engine.generate_smart_coupon(ai_pool, c_count, c_type)
            if coupon:
                st.session_state.generated_coupon = coupon

                total_odd = 1.0
                coupon_items = coupon
                if isinstance(coupon_items, str):
                    try:
                        import json as _json
                        coupon_items = _json.loads(coupon_items)
                    except Exception:
                        coupon_items = []
                if isinstance(coupon_items, dict):
                    coupon_items = [coupon_items]
                if isinstance(coupon_items, list):
                    for pick in coupon_items:
                        odd_str = pick.get('oran_tahmini', '1.0')
                        try:
                            import re as _re
                            match = _re.search(r"\d+(?:[.,]\d+)?", odd_str)
                            if match:
                                val = float(match.group(0).replace(',', '.'))
                                total_odd *= val
                        except Exception:
                            pass

                total_odd_string = f"{total_odd:.2f}"
                data_manager.add_coupon(coupon, total_odd_string)

                st.toast("Kupon hazırlandı ve kaydedildi! Sağ alttaki butona tıklayın.", icon="🎫")
        finally:
            loader_placeholder.empty()
        
    progress_bar.empty()
    status_text.empty()
    st.session_state.start_analysis = False

@st.dialog("🔥 AKIL HOCASI KUPONU")
def show_coupon_modal():
    coupon_items = _normalize_coupon_items(st.session_state.get("generated_coupon", []))
    if not coupon_items:
        st.info("Henüz kupon bulunamadı.")
        return

    total_odd = 1.0
    items_html_parts = []
    for pick in coupon_items:
        odd_str = pick.get('oran_tahmini', '1.0')
        odd_num = _extract_odd_value(odd_str)
        if odd_num:
            total_odd *= odd_num

        reason_text = pick.get('neden', 'İstatistiksel veriler bu tercihi destekliyor.').replace('"', "'")
        is_riskli = pick.get("uygunluk") == "riskli"
        item_class = "bet-item riskli" if is_riskli else "bet-item"
        icon_class = "reason-icon riskli" if is_riskli else "reason-icon"

        items_html_parts.append("".join([
            f"<div class='{item_class}'>",
            "<div style='flex-grow: 1;'>",
            f"<div class='bet-match'>{pick.get('mac', '-')}</div>",
            "<div class='bet-pick-row'>",
            f"<span class='bet-pick'>{pick.get('tahmin', '-')}</span>",
            f"<span class='bet-conf'>({pick.get('guven', '')})</span>",
            "<details class='reason-toggle'>",
            f"<summary><span class='{icon_class}'>!</span></summary>",
            f"<div class='reason-text'>{reason_text}</div>",
            "</details></div></div>",
            f"<div class='bet-odd'>{odd_str}</div>",
            "</div>"
        ]))

    st.markdown("".join(items_html_parts), unsafe_allow_html=True)
    st.markdown("---")

    coupon_text = "🔥 AKIL HOCASI KUPONU 🔥\n\n"
    for item in coupon_items:
        match = item.get("mac", "-")
        prediction = item.get("tahmin", "-")
        odd_val = item.get("oran_tahmini", "-")
        coupon_text += f"⚽ {match}\n👉 {prediction} (Oran: {odd_val})\n\n"
    coupon_text += f"💰 Toplam Oran: {total_odd:.2f}"

    st.caption("👇 Metni kopyalayıp paylaşabilirsin:")
    st.code(coupon_text, language="text")

    img_bytes = create_coupon_image(coupon_items, f"{total_odd:.2f}")
    st.download_button(
        label="📸 Kuponu Resim Olarak İndir",
        data=img_bytes,
        file_name="akil_hocasi_kupon.png",
        mime="image/png",
        use_container_width=True
    )

# --- FLOATING BUTTON (Çapa Yöntemi ile Sabitleme) ---
has_coupon = bool(st.session_state.get("generated_coupon"))
total_odd = 0.0

if has_coupon:
    coupon_items = _normalize_coupon_items(st.session_state.generated_coupon)
    total_odd = 1.0
    for item in coupon_items:
        odd_num = _extract_odd_value(item.get("oran_tahmini", ""))
        if odd_num:
            total_odd *= odd_num

label_suffix = f"{total_odd:.2f} Oran" if has_coupon else "Hazır Değil"

if has_coupon:
    # 1. ADIM: Butonu hedeflemek için benzersiz bir görünmez 'Çapa' (Anchor) ekliyoruz.
    st.markdown('<div id="floating-coupon-anchor"></div>', unsafe_allow_html=True)

    # 2. ADIM: CSS ile bu çapanın hemen yanındaki butonu yakalıyoruz.
    st.markdown("""
    <style>
    /* MANTIK: "floating-coupon-anchor" ID'sine sahip div'i içeren markdown elementinin 
       hemen sonrasındaki (sibling) .stButton div'ini bul ve sabitle.
       Bu yöntem Sidebar'daki butonları ASLA etkilemez.
    */
    div[data-testid="stMarkdown"]:has(div#floating-coupon-anchor) + div.stButton {
        position: fixed !important;
        bottom: 30px !important;
        right: 30px !important;
        z-index: 99999 !important;
        width: auto !important;
    }

    /* Butonun Görsel Tasarımı */
    div[data-testid="stMarkdown"]:has(div#floating-coupon-anchor) + div.stButton > button {
        border-radius: 50px !important;
        background-color: #0f172a !important;
        color: #4ade80 !important;
        border: 2px solid #334155 !important;
        box-shadow: 0 10px 20px rgba(0,0,0,0.5) !important;
        padding: 15px 30px !important;
        font-weight: bold !important;
        font-size: 1.1rem !important;
        transition: all 0.3s ease !important;
    }

    /* Hover Efekti */
    div[data-testid="stMarkdown"]:has(div#floating-coupon-anchor) + div.stButton > button:hover {
        background-color: #1e293b !important;
        transform: scale(1.05);
        border-color: #4ade80 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 3. ADIM: Butonu çiziyoruz. (Çapa'nın hemen altında olduğu için CSS bunu yakalar)
    if st.button(f"🎫 KUPONU AÇ ({label_suffix})", key="fab_open_coupon"):
        show_coupon_modal()

# --- İÇERİK SEKMELERİ (GÜNCELLENMİŞ YAPI) ---
# Ana sekmeleri en dışta tanımlıyoruz ki her zaman erişilebilir olsunlar.
main_tab1, main_tab2, main_tab3 = st.tabs(["⚽ Lig Merkezi", "🇹🇷 Spor Toto", "🗂️ Kupon Geçmişi"])

# -------------------------
# SEKME 1: LİG MERKEZİ
# -------------------------
with main_tab1:
    # Eğer veri çekildiyse (Analiz Modu)
    if 'current_fixture' in st.session_state and st.session_state.current_fixture:
        # Alt sekmeler (Analiz, Chat, Röntgen)
        sub_t1, sub_t2, sub_t3 = st.tabs(["Analiz Masası", "Asistana Sor", "Lig Röntgeni"])
        
        with sub_t1:
            col_sel, col_btn = st.columns([3, 1])
            with col_sel:
                match_options = [f"{m['home']} - {m['away']}" for m in st.session_state.current_fixture]
                selected_match_label = st.selectbox("Analiz Edilecek Maç:", match_options)
            
            selected_match_obj = next((m for m in st.session_state.current_fixture if f"{m['home']} - {m['away']}" == selected_match_label), None)

            if selected_match_obj:
                # SKORBORD GÖRÜNÜMÜ
                home_avatar = selected_match_obj['home'][0]
                away_avatar = selected_match_obj['away'][0]
                
                st.markdown(f"""
                <div class="match-header-container">
                    <div class="team-container">
                        <div class="team-avatar">{home_avatar}</div>
                        <div class="team-name">{selected_match_obj['home']}</div>
                        <div class="team-role">EV SAHİBİ</div>
                    </div>
                    <div class="vs-badge">VS</div>
                    <div class="team-container">
                        <div class="team-avatar away">{away_avatar}</div>
                        <div class="team-name">{selected_match_obj['away']}</div>
                        <div class="team-role">DEPLASMAN</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("🚀 MAÇI ANALİZ ET", type="primary", use_container_width=True):
                    # --- LOADER BAŞLAT ---
                    loader_placeholder = show_full_page_loader("⚡ Maç Simüle Ediliyor...")
                    try:
                        st.session_state.chat_history = []
                        st.session_state.current_analysis_context = None
                        st.session_state.current_analysis_match = {}
                        
                        # Lig istatistikleri yoksa çek
                        league_stats_data = st.session_state.get('league_stats', None)
                        if not league_stats_data:
                            try:
                                league_stats_data = scraper.get_league_detailed_stats(st.session_state.leagues_map[st.session_state.sb_selected_league])
                                st.session_state.league_stats = league_stats_data
                            except: pass

                        @st.cache_data(show_spinner=False, ttl=3600)
                        def get_cached_analysis(home, away, url, standings, stats):
                            return ai_engine.analyze_match_deep(home, away, url, standings, stats)

                        ai_response = get_cached_analysis(
                            selected_match_obj['home'], selected_match_obj['away'], selected_match_obj['url'],
                            st.session_state.current_standings, league_stats_data
                        )
                        
                        if ai_response:
                            match_name = f"{selected_match_obj['home']} - {selected_match_obj['away']}"
                            data_manager.add_analysis(match_name, ai_response)
                            st.session_state.current_analysis_context = ai_response
                            st.session_state.current_analysis_match = {
                                "home_team": selected_match_obj["home"],
                                "away_team": selected_match_obj["away"]
                            }
                            
                            # Grafik ve Kartlar
                            st.markdown("### 🎯 HIZLI BAKIŞ")
                            c1, c2, c3, c4 = st.columns(4)
                            with c1: st.markdown(f"<div class='metric-card card-green'><div class='metric-label'>🔥 ANA TERCİH</div><div class='metric-value'>{ai_response.get('ana_tercih', '-')}</div></div>", unsafe_allow_html=True)
                            with c2: st.markdown(f"<div class='metric-card card-blue'><div class='metric-label'>🛡️ GÜVEN</div><div class='metric-value'>{ai_response.get('guven_skoru', '-')}</div></div>", unsafe_allow_html=True)
                            with c3: st.markdown(f"<div class='metric-card card-yellow'><div class='metric-label'>🎲 SÜRPRİZ</div><div class='metric-value'>{ai_response.get('surpriz_tercih', '-')}</div></div>", unsafe_allow_html=True)
                            with c4: st.markdown(f"<div class='metric-card card-purple'><div class='metric-label'>⭐ YILDIZ</div><div class='metric-value'>{ai_response.get('macin_yildizi', '-')}</div></div>", unsafe_allow_html=True)
                            
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.info(f"💡 **Kritik Faktör:** {ai_response.get('kritik_faktor', '')}")
                            st.markdown("---")
                            st.subheader("📝 Detaylı Analiz Raporu")
                            st.markdown(ai_response.get('analiz_metni', ''))
                        else:
                            st.error("Analiz hatası.")
                    finally:
                        loader_placeholder.empty()

        with sub_t2:
            st.subheader("💬 Bağlama Duyarlı Maç Asistanı")
            if not st.session_state.get("current_analysis_context"):
                st.markdown("## 🔒")
                st.info("Bu özelliği kullanmak için önce 'Analiz Masası'ndan bir maçı analiz etmelisiniz.")
            else:
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

                user_question = st.chat_input("Maçla ilgili merak ettiğin nedir?")
                if user_question:
                    st.session_state.chat_history.append({"role": "user", "content": user_question})
                    with st.chat_message("user"):
                        st.markdown(user_question)

                    context_data = {
                        "home_team": st.session_state.current_analysis_match.get("home_team", "Ev Sahibi"),
                        "away_team": st.session_state.current_analysis_match.get("away_team", "Deplasman"),
                        "analysis": st.session_state.current_analysis_context
                    }
                    answer = ai_engine.get_chat_response(user_question, context_data)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})
                    with st.chat_message("assistant"):
                        st.markdown(answer)

        with sub_t3:
            st.subheader(f"📈 Lig İstatistikleri")
            if st.button("📊 Ligin Röntgenini Çek / Yenile", use_container_width=True):
                loader_placeholder = show_full_page_loader("🛰️ Lig İstatistikleri Taranıyor...")
                try:
                    league_stats = scraper.get_league_detailed_stats(st.session_state.leagues_map[st.session_state.sb_selected_league])
                    st.session_state.league_stats = league_stats
                    st.session_state.league_comment = ai_engine.analyze_league_overview(
                        st.session_state.sb_selected_league,
                        league_stats
                    )
                except Exception as e:
                    st.error(f"Veri çekme hatası: {e}")
                finally:
                    loader_placeholder.empty()
            
            if st.session_state.get("league_comment"):
                st.markdown("### 🧠 Lig Özeti")
                st.info(st.session_state.league_comment)

            if 'league_stats' in st.session_state:
                raw_data = st.session_state.league_stats.get("team_stats", [])
                if raw_data:
                    parsed_data = []
                    for item in raw_data:
                        try:
                            parts = item.split("->")
                            if len(parts) < 2: continue
                            team = parts[0].strip()
                            stats_part = parts[1]
                            stats_dict = {"Takım": team}
                            for stat in stats_part.split(","):
                                if ":" in stat:
                                    k, v = stat.split(":")
                                    clean_v = v.strip().replace('%', '')
                                    try: stats_dict[k.strip()] = float(clean_v)
                                    except: stats_dict[k.strip()] = clean_v
                            parsed_data.append(stats_dict)
                        except: continue
                    
                    if parsed_data:
                        df = pd.DataFrame(parsed_data)
                        st.dataframe(
                            df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Takım": st.column_config.TextColumn("Takım", width="medium"),
                                "Gol/M": st.column_config.ProgressColumn("Gol Ort.", format="%.2f", min_value=0, max_value=3.5),
                                "Şut/M": st.column_config.ProgressColumn("Şut Ort.", format="%.1f", min_value=0, max_value=20),
                                "TSO": st.column_config.ProgressColumn("Topla Oynama %", format="%d%%", min_value=30, max_value=70)
                            }
                        )
    
    else:
        # --- VERİ YOKSA LANDING PAGE (KARTLAR) GÖSTER ---
        POPULAR_LEAGUES = [
            {"name": "TÜRKİYE Süper Lig", "image": "https://upload.wikimedia.org/wikipedia/tr/9/94/S%C3%BCper_Lig_logo.png"},
            {"name": "İNGİLTERE Premier Lig", "image": "https://upload.wikimedia.org/wikipedia/en/f/f2/Premier_League_Logo.svg"},
            {"name": "İSPANYA LaLiga", "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/LaLiga_logo_2023.svg/1200px-LaLiga_logo_2023.svg.png"},
            {"name": "ALMANYA Bundesliga", "image": "https://upload.wikimedia.org/wikipedia/en/d/df/Bundesliga_logo_%282017%29.svg"},
            {"name": "İTALYA Serie A", "image": "https://upload.wikimedia.org/wikipedia/commons/e/e9/Serie_A_logo_2019.svg"},
            {"name": "FRANSA Ligue 1", "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Ligue_1_Uber_Eats_logo.svg/1200px-Ligue_1_Uber_Eats_logo.svg.png"}
        ]

        st.markdown("## 🏆 GÜNÜN FUTBOL MENÜSÜ")

        if 'leagues_map' not in st.session_state or not st.session_state.leagues_map:
            with st.spinner("Lig listesi yükleniyor..."):
                st.session_state.leagues_map = scraper.get_leagues_list()

        def _find_league_key(target_name, leagues_map):
            target_upper = target_name.upper()
            for key in leagues_map.keys():
                key_upper = key.upper()
                if target_upper in key_upper or key_upper in target_upper:
                    return key
            return None

        cols = st.columns(3)
        for idx, league in enumerate(POPULAR_LEAGUES):
            col = cols[idx % 3]
            with col:
                st.markdown(
                    f"""
                    <div class="league-card">
                        <img class="league-img" src="{league['image']}" />
                        <div class="league-name">{league['name']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                if st.button("Analiz Et 🚀", key=f"quick_{league['name']}"):
                    loader = show_full_page_loader(f"🚀 {league['name']} Verileri İşleniyor...")
                    try:
                        leagues_map = st.session_state.get("leagues_map", {})
                        target_name = league["name"]
                        league_key = None
                        for k in leagues_map.keys():
                            if target_name.lower() in k.lower() or k.lower() in target_name.lower():
                                league_key = k
                                break
                        
                        if league_key:
                            st.session_state.pending_league_key = league_key
                            st.session_state.sb_selected_league = league_key # Seçili ligi güncelle
                            league_val = leagues_map[league_key]
                            
                            data = scraper.get_fixture_and_standings(league_val)
                            st.session_state.current_fixture = data["matches"]
                            st.session_state.current_standings = data["standings"]
                            
                            league_stats = scraper.get_league_detailed_stats(league_val)
                            st.session_state.league_stats = league_stats
                            st.session_state.league_comment = ai_engine.analyze_league_overview(
                                league_key,
                                league_stats
                            )
                            st.rerun()
                        else:
                            st.error("Seçilen lig bulunamadı.")
                    except Exception as e:
                        st.error(f"Bir hata oluştu: {e}")
                    finally:
                        loader.empty()

# -------------------------
# SEKME 2: SPOR TOTO
# -------------------------
with main_tab2:
    st.markdown("## 🇹🇷 SPOR TOTO: Haftanın 15'lisi")
    st.info("Bu modül, resmi Spor Toto listesindeki 15 maçı çeker ve yapay zeka ile ideal kolonu oluşturur.")
    
    if 'st_matches' not in st.session_state:
        st.session_state.st_matches = []
        
    col_act, col_info = st.columns([1, 2])
    
    with col_act:
        if st.button("📅 Bu Haftanın Listesini Getir", use_container_width=True):
            loader = show_full_page_loader("Spor Toto Listesi Çekiliyor...")
            try:
                matches = asyncio.run(scraper.get_spor_toto_week_list())
                if matches:
                    st.session_state.st_matches = matches
                    st.success("Liste başarıyla çekildi!")
                else:
                    st.error("Liste çekilemedi. Siteye erişim sorunu olabilir.")
            except Exception as e:
                st.error(f"Hata: {e}")
            finally:
                loader.empty()
                
    if st.session_state.st_matches:
        st.dataframe(st.session_state.st_matches, use_container_width=True)
        
        if st.button("🧠 15 Maçlık AI Kolonu Oluştur", type="primary", use_container_width=True):
            loader = show_full_page_loader("Yapay Zeka 15 Maçı Analiz Ediyor...")
            try:
                prediction = ai_engine.analyze_spor_toto_column(st.session_state.st_matches)
                st.session_state.st_prediction = prediction
            finally:
                loader.empty()
                
        if 'st_prediction' in st.session_state and st.session_state.st_prediction:
            st.markdown("### 🎫 Yapay Zeka: Toto + Banko Önerileri")
            
            results = st.session_state.st_prediction
            if isinstance(results, list):
                for item in results:
                    # Toto Tahmini Rengi
                    tahmin = str(item['tahmin'])
                    color = "#3b82f6" # Mavi (1)
                    if tahmin == '0': color = "#eab308" # Sarı (0)
                    if tahmin == '2': color = "#ef4444" # Kırmızı (2)
                    
                    # Banko Tercihini Al
                    import html as _html
                    banko = _html.escape(item.get('banko_tercih', 'Analiz Ediliyor...'))
                    # String çevrimi ve Escape işlemi (Hata önleyici)
                    karsilasma = _html.escape(str(item.get('karsilasma', '')))
                    neden = _html.escape(str(item.get('neden', '')))
                    
                    # HTML Kodunu Girintisiz (Sola Yaslı) Olarak Tanımlıyoruz
                    card_html = f"""
<div style="display:flex; justify-content:space-between; align-items:center; padding:12px; margin-bottom:8px; background: rgba(30, 41, 59, 0.5); border-radius: 8px; border-left: 4px solid {color};">
    <div style="flex: 2;">
        <div style="font-weight:bold; color:white; font-size:14px;">{item['mac_no']}. {karsilasma}</div>
        <div style="font-size:11px; color:#94a3b8; margin-top:2px;">{neden}</div>
    </div>
    <div style="flex: 1; display:flex; flex-direction:column; align-items:end; gap:4px;">
        <span style="background:{color}; color:white; padding:2px 10px; border-radius:4px; font-weight:bold; font-size:12px; min-width: 30px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">{tahmin}</span>
        <span style="background: rgba(74, 222, 128, 0.15); color: #4ade80; border: 1px solid #4ade80; padding:2px 8px; border-radius:4px; font-weight:600; font-size:11px; white-space: nowrap;">🎯 {banko}</span>
    </div>
</div>
"""
                    st.markdown(card_html, unsafe_allow_html=True)
            else:
                st.error("AI yanıtı işlenemedi.")

# -------------------------
# SEKME 3: KUPON GEÇMİŞİ
# -------------------------
with main_tab3:
    import re as _re
    import html as _html
    def _clean_text(value):
        if value is None: return ""
        text = _html.unescape(str(value))
        text = _re.sub(r"<[^>]+>", "", text)
        return text.strip()

    st.subheader("🗂️ Analiz ve Kupon Arşivi")
    ht1, ht2 = st.tabs(["Kuponlarım", "Maç Analizlerim"])
    
    with ht1:
        coupons = data_manager.get_user_coupons()
        if coupons:
            for coupon in coupons:
                title = f"{coupon.get('date', 'Tarih Yok')} • Toplam Oran: {coupon.get('total_odd', '-')}"
                with st.expander(title):
                    items = coupon.get("items", [])
                    if isinstance(items, str):
                        try:
                            import json as _json
                            items = _json.loads(items)
                        except: items = []
                    if isinstance(items, dict): items = [items]

                    if items:
                        coupon_text = "🔥 AKIL HOCASI KUPONU 🔥\n\n"
                        total_odd = 1.0
                        for idx, pick in enumerate(items, start=1):
                            match = _clean_text(pick.get("mac", "-"))
                            prediction = _clean_text(pick.get("tahmin", "-"))
                            confidence = _clean_text(pick.get("guven", ""))
                            odd_val = _clean_text(pick.get("oran_tahmini", "-"))
                            reason = _clean_text(pick.get("neden", ""))

                            st.markdown(f"**{idx}. {match}**")
                            st.write(f"{prediction} {f'({confidence})' if confidence else ''} • Oran: {odd_val}")
                            if reason: st.caption(f"Neden: {reason}")
                            st.markdown("---")
                            
                            coupon_text += f"⚽ {match}\n👉 {prediction} (Oran: {odd_val})\n\n"
                            odd_num = _extract_odd_value(odd_val)
                            if odd_num: total_odd *= odd_num

                        coupon_text += f"💰 Toplam Oran: {total_odd:.2f}"
                        st.code(coupon_text, language="text")

                        img_bytes = create_coupon_image(items, f"{total_odd:.2f}")
                        st.download_button(
                            label="📸 İndir",
                            data=img_bytes,
                            file_name=f"kupon_{coupon.get('id', idx)}.png",
                            mime="image/png",
                            use_container_width=True,
                            key=f"hist_btn_new_{coupon.get('id', idx)}"
                        )
        else:
            st.info("Henüz kayıtlı kupon yok.")

    with ht2:
        analyses = data_manager.get_user_analyses()
        if analyses:
            for analysis in analyses:
                title = f"{analysis.get('match', 'Maç')} • {analysis.get('date', '')}".strip(" •")
                with st.expander(title):
                    summary = analysis.get("summary", {})
                    if isinstance(summary, str):
                        try:
                            import json as _json
                            summary = _json.loads(summary)
                        except: summary = _clean_text(summary)

                    if isinstance(summary, dict):
                        st.markdown(f"**Ana Tercih:** {_clean_text(summary.get('ana_tercih', '-'))}")
                        st.markdown(f"**Güven:** {_clean_text(summary.get('guven_skoru', '-'))}")
                        st.markdown("**Detaylı Analiz:**")
                        st.write(_clean_text(summary.get("analiz_metni", "")))
                    else:
                        st.write(_clean_text(summary))
        else:
            st.info("Henüz kayıtlı analiz yok.")