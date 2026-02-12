import time
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# Başlangıç noktası
BASE_URL = "https://arsiv.mackolik.com/Puan-Durumu/s=70381/Turkiye-Super-Lig"

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
        browser = p.chromium.launch(headless=True)
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
        browser = p.chromium.launch(headless=True)
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
        browser = p.chromium.launch(headless=True)
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
        browser = p.chromium.launch(headless=True)
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