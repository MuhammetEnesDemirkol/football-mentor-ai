import time
import re
from difflib import SequenceMatcher
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Başlangıç noktası
BASE_URL = "https://arsiv.mackolik.com/Puan-Durumu/s=70381/Turkiye-Super-Lig"

# İddaa lig ID sözlüğü
IDDAA_LEAGUE_IDS = {
    "UEFA": 8,
    "Premier Lig": 1,
    "Süper Lig": 2,
    "LaLiga": 3,
    "Serie A": 4,
    "Bundesliga": 5,
    "Ligue 1": 6,
    "Şampiyonlar Ligi": 8,
    "Avrupa Ligi": 18
}

def _normalize_team_name(text):
    if not text:
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9ğüşöçıİĞÜŞÖÇ ]+", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned

def _similarity(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()

def _match_teams_in_text(home, away, text):
    if not text:
        return False
    norm_text = _normalize_team_name(text)
    home_norm = _normalize_team_name(home)
    away_norm = _normalize_team_name(away)
    if home_norm in norm_text and away_norm in norm_text:
        return True
    return _similarity(home_norm, norm_text) > 0.65 and _similarity(away_norm, norm_text) > 0.65

async def get_real_odds_from_iddaa(match_name, league_id):
    """
    iddaa.com üzerinden gerçek oranları çeker.
    Dönen veri örneği:
    {
        "match": "Ev - Dep",
        "ms1": "1.85",
        "msx": "3.40",
        "ms2": "4.10",
        "alt_2_5": "1.72",
        "ust_2_5": "1.98"
    }
    """
    if not match_name or not league_id:
        return None

    parts = re.split(r"\s*-\s*|\s+vs\s+|\s+v\s+", match_name, flags=re.IGNORECASE)
    if len(parts) >= 2:
        home_team = parts[0].strip()
        away_team = parts[1].strip()
    else:
        home_team, away_team = match_name, ""

    url = f"https://www.iddaa.com/program/futbol?league={league_id}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1500)

            soup = BeautifulSoup(await page.content(), "html.parser")
            grouped_wrappers = soup.find_all("div", class_=lambda c: c and "grouped-wrapper" in c)
            if not grouped_wrappers:
                return None

            for wrapper in grouped_wrappers:
                wrapper_text = wrapper.get_text(" ", strip=True)
                if not _match_teams_in_text(home_team, away_team, wrapper_text):
                    continue

                odd_buttons = wrapper.find_all("button", class_=lambda c: c and "o_all__fRvUM" in c)
                odds = []
                for btn in odd_buttons:
                    odd_text = btn.get_text(strip=True)
                    if re.search(r"\d+(?:[.,]\d+)?", odd_text):
                        odds.append(odd_text.replace(",", "."))

                if not odds:
                    return None

                odds_data = {"match": f"{home_team} - {away_team}"}
                if len(odds) >= 3:
                    odds_data.update({
                        "ms1": odds[0],
                        "msx": odds[1],
                        "ms2": odds[2]
                    })
                if len(odds) >= 5:
                    odds_data.update({
                        "alt_2_5": odds[3],
                        "ust_2_5": odds[4]
                    })
                return odds_data

            return None
        except Exception:
            return None
        finally:
            await browser.close()

def handle_cookie_consent(page):
    """Cookie pencerelerini ve reklam overlay'lerini temizler."""
    try:
        page.evaluate("""() => {
            const selectors = ['.fc-consent-root', '.fc-dialog-overlay', 'div[id^="cmp-"]', '.cookie-banner', '#dvBanner'];
            selectors.forEach(sel => {
                const elements = document.querySelectorAll(sel);
                elements.forEach(el => el.remove());
            });
        }""")
    except: pass

def get_leagues_list():
    """Lig listesini çeker."""
    leagues = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        try:
            page.goto(BASE_URL, timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            options = page.query_selector_all("#cboLeague option")
            for opt in options:
                name = opt.inner_text()
                val = opt.get_attribute("value")
                if val: leagues[name] = val
            return leagues
        except: return {}
        finally: browser.close()

def get_fixture_and_standings(league_value):
    """Seçilen ligin fikstürünü (TARİHLİ) ve puan durumunu çeker."""
    data = {"matches": [], "standings": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        try:
            page.goto(BASE_URL, timeout=60000)
            handle_cookie_consent(page)
            if league_value != "1-1":
                page.select_option("#cboLeague", value=league_value)
                time.sleep(3)
            
            soup = BeautifulSoup(page.content(), 'html.parser')
            
            # Fikstür Tablosu
            table = soup.find("table", {"id": "tblFixture"})
            if table:
                rows = table.find_all("tr")
                current_date = ""
                for row in rows:
                    # Tarih satırı mı? (Genelde colspan olan satırlar veya tarih içeren td)
                    # Maçkolik yapısında tarih genelde ilk sütundadır (13/02 gibi)
                    # veya maç satırının ilk hücresindedir.
                    
                    cols = row.find_all("td")
                    if len(cols) > 5:
                        date_str = cols[0].get_text(strip=True) # Örn: 13/02
                        time_str = cols[1].get_text(strip=True) # Örn: 20:00
                        home = row.find("td", align="right")
                        away = row.find("td", align="left")
                        vs = row.find("td", align="center")
                        
                        if home and away and vs:
                            link = vs.find("a")
                            if link:
                                url = link['href']
                                if url.startswith("//"): url = "https:" + url
                                
                                data["matches"].append({
                                    "date": date_str, # Filtreleme için kritik
                                    "time": time_str,
                                    "home": home.get_text(strip=True), 
                                    "away": away.get_text(strip=True), 
                                    "url": url
                                })
            
            # Puan Durumu
            stand_tbl = soup.find("table", {"id": "tblStanding"})
            if stand_tbl:
                rows = stand_tbl.find_all("tr", {"class": "puan_row"})
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) > 9:
                        data["standings"].append(f"{cols[1].get_text(strip=True)} ({cols[9].get_text(strip=True)} P)")
            return data
        except: return data
        finally: browser.close()

def get_match_deep_stats(match_url):
    """
    Maç detaylarını (OPTA Facts, Son Form Durumu + TARİHLER, Kadrolar) çeker.
    """
    stats = {"yellow_box": [], "player_stats": [], "h2h": [], "comparison_stats": "", "form_patterns": []}
    
    print(f"🕵️‍♂️ Derin Analiz Başlıyor: {match_url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        try:
            page.goto(match_url, timeout=60000)
            handle_cookie_consent(page)
            time.sleep(2)
            
            soup = BeautifulSoup(page.content(), 'html.parser')

            # --- 1. OPTA FACTS ---
            opta_ul = soup.find("ul", class_="opta-facts")
            if opta_ul:
                facts = opta_ul.find_all("li")
                for fact in facts:
                    text = fact.get_text(strip=True)
                    if "Daha" not in text and len(text) > 10:
                        stats["yellow_box"].append(f"📌 {text}")
            
            yellows = soup.find_all("div", style=lambda v: v and '#FBFCC8' in v)
            for y in yellows: 
                stats["yellow_box"].append(f"⚠️ {y.get_text(' ', strip=True)}")

            # --- 1.5 OPTA / KARŞILAŞTIRMA VERİLERİ (compare-right-coll) ---
            try:
                compare_el = page.query_selector("#compare-right-coll")
                if compare_el:
                    compare_text = compare_el.inner_text().strip()
                    compare_text = re.sub(r"\s+", " ", compare_text)
                    stats["comparison_stats"] = compare_text

                    # Form durumuna benzeyen dizileri yakala (G, B, M, W, D, L)
                    form_patterns = re.findall(r"[GBMWDL]{3,}", compare_text)
                    if form_patterns:
                        stats["form_patterns"] = [p.strip() for p in form_patterns if p.strip()]
                else:
                    stats["comparison_stats"] = ""
                    stats["form_patterns"] = []
            except Exception:
                stats["comparison_stats"] = ""
                stats["form_patterns"] = []

            # --- 2. FORM DURUMU ve FİKSTÜR SIKIŞIKLIĞI (GÜNCELLENDİ) ---
            # Artık tarihleri de alıyoruz!
            md_divs = soup.find_all("div", class_="md")
            for md in md_divs:
                title_div = md.find("div", class_="detail-title")
                
                if title_div and "Form Durumu" in title_div.get_text():
                    team_name = title_div.get_text(strip=True).replace("- Form Durumu", "").strip()
                    table = md.find("table", class_="md-table3")
                    
                    if table:
                        rows = table.find_all("tr", class_=["alt1", "alt2"])
                        form_data = []
                        
                        # Son 5 maçı al
                        for row in rows[:5]: 
                            cols = row.find_all("td")
                            # HTML Yapısı: [0]Lig, [1]TARİH, [2]Takım, [3]SKOR
                            if len(cols) >= 4:
                                date_text = cols[1].get_text(strip=True) # Örn: 14.12
                                score_cell = row.find("b")
                                score = score_cell.get_text(strip=True) if score_cell else "?"
                                
                                form_data.append(f"{date_text} ({score})")
                        
                        if form_data:
                            # Veriyi şu formatta kaydediyoruz: "14.12 (3-3), 17.12 (0-1)..."
                            # AI bu tarihlere bakıp "Aaa, 3 gün arayla maç yapmışlar" diyecek.
                            stats["yellow_box"].append(f"🗓️ {team_name} Fikstürü (Tarih/Skor): {', '.join(form_data)}")

            # --- 3. KADRO VE OYUNCULAR ---
            for md in md_divs:
                title_div = md.find("div", class_="detail-title")
                if title_div and ("En Golcüler" in title_div.get_text() or "Son Maç Kadrosu" in title_div.get_text()):
                    header_text = title_div.get_text(strip=True)
                    table = md.find("table", class_="md-table")
                    if table:
                        rows = table.find_all("tr", class_=["alt1", "alt2"])
                        top_players = []
                        for row in rows[:5]: # İlk 5 oyuncu (Kadro derinliği için artırdım)
                            cols = row.find_all("td")
                            if cols:
                                player_name = cols[0].get_text(strip=True)
                                val = cols[-1].get_text(strip=True)
                                top_players.append(f"{player_name} ({val})")
                        
                        if top_players:
                            stats["player_stats"].append(f"{header_text}: {', '.join(top_players)}")

            return stats
        except Exception as e: 
            print(f"Scraper Hatası: {e}")
            return stats
        finally: browser.close()

def get_league_detailed_stats(league_value):
    """Lig genel istatistiklerini (Gol/Şut vb.) çeker."""
    team_stats_list = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        try:
            page.goto(BASE_URL, timeout=90000)
            handle_cookie_consent(page)
            if league_value != "1-1":
                page.select_option("#cboLeague", value=league_value)
                time.sleep(3)
                handle_cookie_consent(page)

            # İstatistik -> Takım İstatistikleri Navigasyonu
            page.evaluate("""() => {
                const tabs = document.querySelectorAll('#tab-list a');
                for (const tab of tabs) { if (tab.innerText.includes('İstatistik')) { tab.click(); break; } }
            }""")
            time.sleep(2)
            page.evaluate("""() => {
                const links = document.querySelectorAll('.sub-menu a');
                for (const link of links) { if (link.innerText.includes('Takım İstatistikleri')) { link.click(); break; } }
            }""")
            
            try: page.wait_for_selector("#tblTeamStats", state="visible", timeout=15000)
            except: pass

            soup = BeautifulSoup(page.content(), 'html.parser')
            table = soup.find("table", {"id": "tblTeamStats"})
            if table:
                rows = table.find_all("tr", {"class": ["alt1", "alt2"]})
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 10:
                        try:
                            line = (f"{cols[0].get_text(strip=True)} -> "
                                    f"Gol/M: {cols[2].get_text(strip=True)}, "
                                    f"Şut/M: {cols[3].get_text(strip=True)}, "
                                    f"TSO: %{cols[5].get_text(strip=True)}, "
                                    f"Korner: {cols[10].get_text(strip=True)}")
                            team_stats_list.append(line)
                        except: continue
            return {"team_stats": team_stats_list}
        except: return {"team_stats": []}
        finally: browser.close()

async def get_spor_toto_week_list():
    """
    iddaa.com üzerinden güncel Spor Toto listesini çeker.
    HTML yapısı 'data-comp-name' özniteliklerine göre hedeflenir.
    """
    url = "https://www.iddaa.com/spor-toto"
    matches = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            # Mobil görünüm değil desktop görünümü zorlayalım, yapı değişmesin
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            
            try:
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                
                # 1. Listenin yüklenmesini bekle (1. maçın sıra numarası kutusu gelene kadar)
                # HTML'de: <div ... data-comp-name="sporToto-1">1</div>
                await page.wait_for_selector('div[data-comp-name="sporToto-1"]', timeout=20000)
                
            except Exception as e:
                print(f"Sayfa yükleme zaman aşımı: {e}")
                await browser.close()
                return []

            # 2. 15 Maçlık Döngü
            for i in range(1, 16):
                try:
                    # Sıra numarasına sahip div'i bul (Örn: sporToto-1)
                    # first=True kullanıyoruz çünkü bazen shadow dom veya duplicate olabilir, ilki işimizi görür.
                    row_index_locator = page.locator(f'div[data-comp-name="sporToto-{i}"]').first
                    
                    # Eğer element yoksa döngüden çık
                    if await row_index_locator.count() == 0:
                        break
                        
                    # 3. Satırın Yapısını Çözümle
                    # İlgili numaranın bir üst ebeveyni (parent) tüm satırı kapsayan flex container'dır.
                    row_locator = row_index_locator.locator("..")
                    
                    # Tarih: data-comp-name="sporToto-dates"
                    date_text = await row_locator.locator('div[data-comp-name="sporToto-dates"]').inner_text()
                    
                    # Takımlar: class="flex-1" olan div genellikle takımları içerir
                    # Veya data-comp-name'i "sporToto-" ile başlayan ama tarih veya index olmayan div
                    teams_locator = row_locator.locator('div.flex-1')
                    teams_text = await teams_locator.inner_text()
                    
                    # Takım isimlerini ayrıştır (Format: Ev Sahibi-Deplasman)
                    # Bazen takım adlarında tire (-) olabilir, bu yüzden basit split yerine dikkatli ayıralım.
                    # iddaa.com genellikle "TakımA-TakımB" formatı kullanır (boşluksuz veya bitişik tire).
                    if "-" in teams_text:
                        # İlk tireden bölmek genelde güvenlidir ama takım adında tire varsa sorun olabilir.
                        # Genellikle iddaa.com görünümlerinde tirenin etrafında boşluk olmayabiliyor.
                        # En sağlam yöntem: ortadaki tireyi bulmak.
                        parts = teams_text.split("-")
                        if len(parts) >= 2:
                            # Son parça deplasman, geri kalan her şey ev sahibi (örn: Demir-Çelik Spor - Vefa)
                            # Ancak iddaa formatı genelde "X-Y" şeklindedir.
                            # Basitçe 2'ye bölelim, çoğu durumda çalışır.
                            # Alternatif: "Trabzonspor A.Ş.-Fenerbahçe A.Ş." gibi durumlarda
                            # parts = ['Trabzonspor A.Ş.', 'Fenerbahçe A.Ş.'] -> OK.
                            
                            # Eğer 2'den fazla parça varsa (Örn: Hatay-Spor - İst-Spor) manuel birleştirme gerekebilir.
                            # Şimdilik iddaa.com yapısına güvenip ilk parçayı Ev, diğerlerini Deplasman alalım.
                            # Veya daha güvenlisi: ortadaki ayırıcıyı bulmak zor. 
                            # Standart yaklaşım:
                            home = parts[0].strip()
                            away = "-".join(parts[1:]).strip()
                        else:
                            home = teams_text
                            away = "?"
                    else:
                        home = teams_text
                        away = "?"

                    matches.append({
                        "mac_no": i,
                        "home": home,
                        "away": away,
                        "date": date_text
                    })
                    
                except Exception as loop_e:
                    print(f"Satır {i} işlenirken hata: {loop_e}")
                    continue

            await browser.close()
            return matches

    except Exception as e:
        print(f"Genel Scraping Hatası: {e}")
        return []