import json
import os
import datetime

# Veritabanı dosyası (Basit JSON)
DB_FILE = "user_history.json"

def load_history():
    """Geçmiş verileri JSON dosyasından okur."""
    if not os.path.exists(DB_FILE):
        return {"coupons": [], "analyses": []}
    
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"coupons": [], "analyses": []}

def save_history(data):
    """Verileri JSON dosyasına yazar."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def add_coupon(coupon_data, total_odd):
    """Yeni bir kuponu geçmişe ekler."""
    history = load_history()
    
    # Yeni kayıt
    new_entry = {
        "id": int(datetime.datetime.now().timestamp()), # Benzersiz ID
        "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "type": "coupon",
        "total_odd": total_odd,
        "items": coupon_data
    }
    
    # Listeye ekle (En başa)
    history["coupons"].insert(0, new_entry)
    
    # Son 50 kuponu tut (Dosya şişmesin)
    history["coupons"] = history["coupons"][:50]
    
    save_history(history)

def add_analysis(match_name, ai_response):
    """Yeni bir maç analizini geçmişe ekler."""
    history = load_history()
    
    new_entry = {
        "id": int(datetime.datetime.now().timestamp()),
        "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "type": "analysis",
        "match": match_name,
        "summary": ai_response
    }
    
    history["analyses"].insert(0, new_entry)
    history["analyses"] = history["analyses"][:50]
    
    save_history(history)

def get_user_coupons():
    """Kayıtlı kuponları döndürür."""
    data = load_history()
    return data.get("coupons", [])

def get_user_analyses():
    """Kayıtlı analizleri döndürür."""
    data = load_history()
    return data.get("analyses", [])