import json
import os
import time
import unicodedata
import re
import google.generativeai as genai
from modules import scraper

# API KEY
API_KEY = os.getenv("GOOGLE_API_KEY", "")
if API_KEY:
    genai.configure(api_key=API_KEY)

# --- MODEL AYARI ---
# Listeden teyit ettiğimiz kararlı ve hızlı model
CURRENT_MODEL = 'gemini-2.5-flash'

def set_api_key(api_key):
    """Uygulama içinde dinamik API key atamak için."""
    global API_KEY
    if api_key:
        API_KEY = api_key
        genai.configure(api_key=api_key)

def normalize_text(text):
    """Türkçe karakterleri ve boşlukları normalize eder."""
    if not text: return ""
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8').lower().strip()

def find_team_stats(team_name, stats_list):
    """
    Koca listeden sadece ilgili takımın satırını bulur.
    """
    if not stats_list: return "Veri yok"
    
    target_name = normalize_text(team_name)
    
    for line in stats_list:
        if "->" in line:
            line_team_part = line.split("->")[0]
            current_line_name = normalize_text(line_team_part)
            
            # Kapsama kontrolü (Örn: "Galatasaray A.Ş." ile "Galatasaray")
            if target_name in current_line_name or current_line_name in target_name:
                return line
                
    return f"{team_name} için detaylı veri bulunamadı."

def clean_json_response(response_text):
    """
    AI'dan gelen metni saf JSON'a çevirir.
    """
    try:
        # Markdown (```json ... ```) temizliği
        cleaned = re.sub(r"```json\s*", "", response_text, flags=re.IGNORECASE)
        cleaned = re.sub(r"```", "", cleaned)
        return json.loads(cleaned.strip())
    except Exception as e:
        print(f"JSON Parse Hatası: {e}")
        return {
            "ana_tercih": "Analiz Edildi",
            "guven_skoru": "%50",
            "surpriz_tercih": "Yok",
            "kritik_faktor": "Veri işleme hatası oluştu, metni aşağıdan okuyunuz.",
            "analiz_metni": response_text
        }

def call_ai_with_retry(system_prompt, user_data):
    """
    Yapay Zeka çağrısını yapar. 429 (Kota) hatası alırsa bekler.
    JSON formatında yanıt zorlar.
    """
    if not API_KEY:
        return {
            "ana_tercih": "Hata",
            "analiz_metni": "API key bulunamadı. Lütfen Google API key giriniz."
        }
    # JSON modunu zorluyoruz
    model = genai.GenerativeModel(CURRENT_MODEL, 
                                  generation_config={"response_mime_type": "application/json"})
    
    max_retries = 5
    wait_time = 10 
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(f"{system_prompt}\n\nVeriler:\n{json.dumps(user_data)}")
            return clean_json_response(response.text)
        except Exception as e:
            error_msg = str(e)
            # Hata kodu 429 veya Quota ise bekle
            if "429" in error_msg or "Quota" in error_msg or "Resource has been exhausted" in error_msg:
                print(f"⚠️ {CURRENT_MODEL} kotası dolu. {wait_time} saniye bekleniyor... (Deneme {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                wait_time += 10 # Bekleme süresini artır
            else:
                return {
                    "ana_tercih": "Hata",
                    "analiz_metni": f"Kritik API Hatası: {error_msg}"
                }
    return {
        "ana_tercih": "Trafik Yoğun",
        "analiz_metni": "Üzgünüm, Google API şu an aşırı yoğun. Lütfen 1 dakika sonra tekrar deneyiniz."
    }

def analyze_league_overview(league_name, stats_data):
    """
    Ligin TAKIM İSTATİSTİKLERİNİ yorumlar (JSON değil Text dönebilir).
    """
    raw_stats = stats_data.get("team_stats", [])
    if not raw_stats: return "⚠️ Veri çekilemedi."
    stats_text = "\n".join(raw_stats)

    # Burası düz metin (text) dönebilir
    model = genai.GenerativeModel(CURRENT_MODEL)
    try:
        response = model.generate_content(f"Bu lig istatistiklerini analiz et, liderleri ve sürprizleri yaz:\n{stats_text}")
        return response.text
    except:
        return "Analiz yapılamadı."

def generate_smart_coupon(matches_data, match_count, bet_preference):
    """
    Toplu maç verilerini alır ve seçilen stratejiye göre en iyi kombinasyonu oluşturur.
    """
    
    # AI'ya gönderilecek özet veri metnini hazırla
    matches_text = ""
    for i, m in enumerate(matches_data):
        matches_text += f"""
        MAÇ {i+1}: {m['home']} vs {m['away']} ({m.get('lig', 'Lig Belirsiz')})
        - Kritik Seri (Sarı Kutu): {m['insights']}
        - Teknik Veriler: {m['stats']}
        --------------------------------------------------
        """

    # Stratejiye göre ek talimat belirle
    strategy_instruction = ""
    if "Banko" in bet_preference:
        strategy_instruction = """
        KRİTİK KURAL: Asla sadece 'Maç Sonucu' (MS) bahsine odaklanma!
        Hedefimiz en yüksek kazanma ihtimali (%85 ve üzeri).
        - Eğer favori takım riskliyse ama gol bekleniyorsa '1.5 ÜST' veya 'KG VAR' öner.
        - Eğer favori kaybetmez gibiyse ama kazanması garanti değilse 'Çifte Şans (1X veya X2)' öner.
        - Sadece ve sadece galibiyet çok netse (Örn: Lider vs Sonuncu) 'MS' öner.
        - Oran düşük olsa bile en 'Yeşil' (Güvenli) tercihi seç.
        """
    elif "Gol Şov" in bet_preference:
        strategy_instruction = "Taraf bahsinden kaçın. İki takımın da golcü olduğu, savunmaların zayıf olduğu maçları seç. Hedef: KG VAR veya 2.5 ÜST."
    elif "Kısır" in bet_preference:
        strategy_instruction = "Gollü maçlardan uzak dur. Savunma takımlarını, 0-0 veya 1-0 bitmeye aday maçları seç. Hedef: 2.5 ALT veya KG YOK."
    elif "Sürpriz" in bet_preference:
        strategy_instruction = "Favorilerin formsuz olduğu maçları bul. Oranı yüksek olacak 'Sürpriz' tahminler yap (Örn: Deplasman kazanır, İY 0)."
    else: # Karma
        strategy_instruction = "En dengeli kuponu yap. İster taraf, ister gol, ister korner... Veriler en çok hangi bahsi destekliyorsa onu seç."

    system_prompt = f"""
    Sen "Akıl Hocası"sın. Profesyonel bir bahis stratejistisin.
    
    GÖREVİN:
    Aşağıdaki maç havuzunu analiz et ve kullanıcının seçtiği stratejiye EN UYGUN {match_count} maçlık bir kupon oluştur.
    
    KULLANICI STRATEJİSİ: {bet_preference}
    ⚠️ BU STRATEJİ İÇİN ÖZEL TALİMAT: {strategy_instruction}

    EK KURAL:
    Eğer eldeki maçlardan biri, kullanıcının seçtiği stratejiye (Örn: Kısır Döngü/Alt) HİÇ UYMUYORSA ama sayı tamamlamak için eklemek zorundaysan;
    Tahminini yine de yap (Stratejiye en yakın olanı).
    JSON çıktısına "uygunluk": "riskli" alanını ekle (Normal maçlar için "tam_uyumlu" olsun).
    "neden" alanına dürüstçe şunu yaz: 'UYARI: Bu maç stratejinize ters (Takımlar çok golcü) ancak maç sayısını tamamlamak için eklendi.'
    
    VERİLER:
    {matches_text}
    
    ÇIKTI FORMATI (JSON LİSTESİ):
    [
      {{
        "mac": "Takım A - Takım B",
        "tahmin": "Tahmin (Örn: MS 1)",
        "oran_tahmini": "Tahmini Oran (Örn: 1.55)",
        "guven": "Güven Skoru (Örn: %85)",
        "neden": "Kısa gerekçe (Örn: Ev sahibi son 5 maçını kazandı, rakip çok eksik)",
        "uygunluk": "riskli"
      }},
      ... (İstenen sayı kadar maç)
    ]
    """
    
    # JSON formatında yanıt almaya zorla
    return call_ai_with_retry(system_prompt, {"task": "coupon_generation"})

def analyze_match_deep(home_team, away_team, match_url, standings_summary, league_stats=None):
    """
    Maçkolik detayları + Lig Genel İstatistiklerini birleştirir.
    JSON ÇIKTISI ÜRETİR.
    """
    
    # 1. Maçın Kendi Detaylarını Çek
    details = scraper.get_match_deep_stats(match_url)
    
    # 2. Lig Genel İstatistiklerinden Takımları Bul
    home_general_stats = "Veri Yok"
    away_general_stats = "Veri Yok"
    
    if league_stats and "team_stats" in league_stats:
        home_general_stats = find_team_stats(home_team, league_stats["team_stats"])
        away_general_stats = find_team_stats(away_team, league_stats["team_stats"])

    match_data = {
        "fixture": f"{home_team} vs {away_team}",
        "league_standings_top": standings_summary[:5], 
        "critical_insights": details["yellow_box"],
        "key_players": details["player_stats"],
        "form_patterns": details.get("form_patterns", []),
        "comparison_stats": details.get("comparison_stats", ""),
        "h2h_notes": details["h2h"],
        "home_technical_stats": home_general_stats,
        "away_technical_stats": away_general_stats
    }

    system_prompt = f"""
    BAĞLAM ZAMANI: Şubat 2026.
    ⚠️ KRİTİK KURAL: Sana verilen 'critical_insights' ve 'key_players' verileri MUTLAK GERÇEKTİR.
    - Kendi eğitim verindeki (2024/2025) kadroları UNUT.
    - Eğer verilerde "Fenerbahçe Teknik Direktörü Tedesco" veya "Forvet Talisca" yazıyorsa bunu sorgulama, doğru kabul et ve analizini buna göre yap.
    - Asla "İsim hatası" veya "Yanlış veri" uyarısı verme. Senin gerçekliğin, sana gönderilen bu JSON verisidir.

    🚫 HALÜSİNASYON YASAKLARI:
    1. SANA VERİLEN JSON İÇİNDE NET OLARAK YOKSA, ASLA SAYISAL İSTATİSTİK UYDURMA.
       - Örn: Eğer input verisinde "Son 5 maç: G-G-B-M-G" yazmıyorsa, metinde "Son 5 maçta 4 galibiyet aldı" deme.
    2. FORM DURUMU BİLİNMİYORSA GENEL KONUŞ.
       - Yanlış: "Son 3 maçını kazandı." (Veride yoksa yasak)
       - Doğru: "Ligdeki konumu itibariyle zorlu bir dönemden geçiyor." (Puan tablosuna bakarak çıkarım yapabilirsin)
    3. VERİ TUTARLILIĞI:
       - Bir takım ligin dibindeyse ona "Harika bir form grafiği var" deme. Puan tablosu (standings) ile yorumların tutarlı olsun.

    Sen "Akıl Hocası"sın. Sıradan bir bahisçi değil, verilerin fısıldadığı detayları duyan usta bir analistsin.

    ELİNDEKİ VERİLER:
    1. **OPTA & Form Analizi:** {match_data['critical_insights']}
       - Bu verilerde gizli hazineler var. Örneğin "İkinci yarılarda açılıyorlar" diyorsa yarı bahsine yönel.
    1.1 **Takımların Form Dizilimi (G/B/M veya W/D/L):** {match_data['form_patterns']}
       - Bu alan boş değilse, mutlaka analizine yedir ve yorumlarına kanıt olarak kullan.
    1.2 **Karşılaştırma / Opta Verileri:** {match_data['comparison_stats']}
       - Bu metindeki Opta analizlerini, sakat/cezalı bilgilerini ve tarihsel istatistikleri kullanarak daha derin ve tutarlı yorum üret.
    2. **Teknik Veriler:** {match_data['home_technical_stats']} VS {match_data['away_technical_stats']}
    3. **Kilit Oyuncular:** {match_data['key_players']}

    GÖREVİN:
    Maçı analiz et ve EN YÜKSEK OLASILIKLI tahmini yap.
    
    ⚠️ ÖNEMLİ KURAL:
    - Kendini sadece "Maç Sonucu" veya "Alt/Üst" ile sınırlama!
    - Eğer veriler "Ev Sahibi Gol Yemez", "Deplasman En Az Bir Yarı Kazanır", "En Çok Gol 2. Yarı", "KG VAR" veya "Korner Üst" gibi özel tercihleri işaret ediyorsa, çekinmeden bunları öner.
    - Amacımız klişe tahmin değil, isabetli tahmin.

    İSTENEN JSON FORMATI:
    {{
        "ana_tercih": "Tahmin (Örn: Deplasman 1.5 ÜST veya Ev Sahibi Yarı Kazanır)",
        "guven_skoru": "Yüzde (Örn: %85)",
        "surpriz_tercih": "Alternatif (Örn: İlk Yarı 0)",
        "macin_yildizi": "Oyuncu İsmi",
        "kritik_faktor": "Maçı belirleyecek en önemli etken (Tek cümle)",
        "analiz_metni": "Verilere dayalı, ikna edici ve akıcı analiz paragrafı."
    }}
    """
    
    return call_ai_with_retry(system_prompt, match_data)