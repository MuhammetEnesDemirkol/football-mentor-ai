import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'futbol.db')

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Tablo: Takımlar (Puan Durumu)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            played INTEGER,
            wins INTEGER,
            draws INTEGER,
            losses INTEGER,
            goals_for INTEGER,
            goals_against INTEGER,
            points INTEGER
        )
    """)
    
    # 2. YENİ TABLO: Fikstür ve Maç Sonuçları
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week INTEGER,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            is_played BOOLEAN DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# --- VERİ KAYDETME FONKSİYONLARI ---

def update_team_stats(team_data):
    """Puan durumunu günceller"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO teams (name, played, wins, draws, losses, goals_for, goals_against, points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                played=excluded.played, wins=excluded.wins, draws=excluded.draws,
                losses=excluded.losses, goals_for=excluded.goals_for,
                goals_against=excluded.goals_against, points=excluded.points
        """, (team_data['name'], team_data['played'], team_data['wins'], team_data['draws'], 
              team_data['losses'], team_data['goals_for'], team_data['goals_against'], team_data['points']))
        conn.commit()
    except Exception as e:
        print(f"DB Team Error: {e}")
    conn.close()

def save_match_result(week, home, away, h_score, a_score, played):
    """Maç sonucunu kaydeder"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Aynı maçı tekrar kaydetmemek için kontrol (Takımlar ve Hafta aynıysa güncelle)
        cursor.execute("""
            SELECT id FROM matches WHERE home_team=? AND away_team=? AND week=?
        """, (home, away, week))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("""
                UPDATE matches SET home_score=?, away_score=?, is_played=? 
                WHERE id=?
            """, (h_score, a_score, played, existing[0]))
        else:
            cursor.execute("""
                INSERT INTO matches (week, home_team, away_team, home_score, away_score, is_played)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (week, home, away, h_score, a_score, played))
        conn.commit()
    except Exception as e:
        print(f"DB Match Error: {e}")
    conn.close()

def calculate_team_performance(team_name):
    """
    Maç tablosunu okuyarak İç Saha, Dış Saha ve Genel performansı HESAPLAR.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Takımın oynadığı TÜM maçları çek (Tarih sırasına göre)
    cursor.execute("""
        SELECT week, home_team, away_team, home_score, away_score 
        FROM matches 
        WHERE (home_team=? OR away_team=?) AND is_played=1 
        ORDER BY week ASC
    """, (team_name, team_name))
    
    matches = cursor.fetchall()
    conn.close()

    # İstatistik Sepetleri
    stats = {
        "general": {"p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0},
        "home":    {"p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0},
        "away":    {"p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0},
        "form":    [] # Son 5 maç (G-B-M)
    }

    for m in matches:
        week, h_team, a_team, h_score, a_score = m
        
        # Maçın skoru ve sonucu
        is_home = (h_team == team_name)
        my_score = h_score if is_home else a_score
        opp_score = a_score if is_home else h_score
        
        # Sonuç Belirleme (3 Puan, 1 Puan, 0 Puan)
        if my_score > opp_score:
            res = "W" # Win
            points = 3
        elif my_score == opp_score:
            res = "D" # Draw
            points = 1
        else:
            res = "L" # Loss
            points = 0
            
        # Form Listesine Ekle (En sona ekle)
        stats["form"].append(res)
        
        # Genel İstatistikleri Güncelle
        stats["general"]["p"] += points
        stats["general"]["w"] += 1 if res == "W" else 0
        stats["general"]["d"] += 1 if res == "D" else 0
        stats["general"]["l"] += 1 if res == "L" else 0
        stats["general"]["gf"] += my_score
        stats["general"]["ga"] += opp_score

        # İç Saha / Dış Saha Ayrımı
        cat = "home" if is_home else "away"
        stats[cat]["p"] += points
        stats[cat]["w"] += 1 if res == "W" else 0
        stats[cat]["d"] += 1 if res == "D" else 0
        stats[cat]["l"] += 1 if res == "L" else 0
        stats[cat]["gf"] += my_score
        stats[cat]["ga"] += opp_score

    # Formun sadece son 5 maçını al ve ters çevir (Yeni -> Eski)
    stats["form"] = stats["form"][-5:][::-1]
    
    return stats

def get_current_week():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Skoru girilmemiş en küçük hafta
        cursor.execute("SELECT MIN(week) FROM matches WHERE is_played = 0")
        res = cursor.fetchone()
        return res[0] if res and res[0] else 38
    except:
        return 1
    finally:
        conn.close()

def get_matches_by_week(week):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT home_team, away_team FROM matches WHERE week=?", (week,))
    res = cursor.fetchall()
    conn.close()
    return [f"{r[0]} - {r[1]}" for r in res]

# --- ANALİZ İÇİN VERİ ÇEKME FONKSİYONLARI ---

def get_team_stats(team_name):
    """Puan tablosu verisi"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teams WHERE name LIKE ?", (f"%{team_name}%",))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "name": row[1], "played": row[2], "wins": row[3], "draws": row[4],
            "losses": row[5], "goals_for": row[6], "goals_against": row[7], "points": row[8]
        }
    return None

def get_team_rank(team_name):
    """Sıralama hesapla"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM teams ORDER BY points DESC, (goals_for - goals_against) DESC")
    all_teams = [row[0] for row in cursor.fetchall()]
    conn.close()
    try:
        return all_teams.index(team_name) + 1
    except:
        return 0

def get_form_analysis(team_name, role):
    """
    MATEMATİKSEL FORM ANALİZİ:
    - Son 5 maçı bulur.
    - İç saha / Dış saha ayrımına göre özel istatistik çıkarır.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. SON 5 MAÇ (Genel Form)
    cursor.execute("""
        SELECT home_team, away_team, home_score, away_score 
        FROM matches 
        WHERE (home_team=? OR away_team=?) AND is_played=1 
        ORDER BY week DESC LIMIT 5
    """, (team_name, team_name))
    last_5_matches = cursor.fetchall()
    
    # Formu hesapla (G-B-M)
    form_str = []
    for m in last_5_matches:
        h_team, a_team, h_s, a_s = m
        if h_team == team_name:
            res = "G" if h_s > a_s else "M" if h_s < a_s else "B"
        else:
            res = "G" if a_s > h_s else "M" if a_s < h_s else "B"
        form_str.append(res)
    
    # 2. İÇ/DIŞ SAHA KARNESİ
    if role == "home":
        # Sadece evindeki maçlar
        cursor.execute("SELECT home_score, away_score FROM matches WHERE home_team=? AND is_played=1", (team_name,))
        matches = cursor.fetchall()
        # Evindeki gol ortalaması
        goals_scored = sum([m[0] for m in matches])
        goals_conceded = sum([m[1] for m in matches])
        count = len(matches)
        loc_stat = f"Evinde {count} maçta {goals_scored} gol attı, {goals_conceded} yedi."
    else:
        # Sadece deplasmandaki maçlar
        cursor.execute("SELECT home_score, away_score FROM matches WHERE away_team=? AND is_played=1", (team_name,))
        matches = cursor.fetchall()
        goals_scored = sum([m[1] for m in matches]) # Deplasman golü 2. indekstir
        goals_conceded = sum([m[0] for m in matches])
        count = len(matches)
        loc_stat = f"Deplasmanda {count} maçta {goals_scored} gol attı, {goals_conceded} yedi."
        
    conn.close()
    
    return {
        "last_5": "-".join(form_str[::-1]), # Eskiden yeniye sırala
        "location_stat": loc_stat if count > 0 else "Veri yok"
    }

def get_all_teams():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM teams ORDER BY points DESC")
    return [row[0] for row in cursor.fetchall()]