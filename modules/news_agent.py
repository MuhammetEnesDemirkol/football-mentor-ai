from duckduckgo_search import DDGS
import time

def get_current_status(team_name):
    """
    Sadece GÜNCEL KADRO ve FİKSTÜR durumunu araştırır.
    (Maç sonuçlarına bakmaz, onu veritabanı halleder).
    """
    print(f"🚑 Revir ve Fikstür Kontrolü: {team_name}...")
    intel_report = []
    
    # 1. Sakatlık ve Ceza Araması
    # 2. Fikstür/Yorgunluk Araması (Avrupa dönüşü mü?)
    queries = [
        f"{team_name} sakat cezalı futbolcular son dakika",
        f"{team_name} fikstür avrupa kupası yorgunluk",
        f"{team_name} teknik direktör açıklaması kadro"
    ]
    
    try:
        with DDGS() as ddgs:
            for q in queries:
                # Son 1 haftadaki (w) haberlere bak
                results = list(ddgs.text(q, region='tr-tr', safesearch='off', timelimit='w', max_results=2))
                
                for r in results:
                    source = r.get('title', 'Haber')
                    body = r.get('body', '')
                    # Kısa özet ekle
                    intel_report.append(f"- {body} (Kaynak: {source})")
                
                time.sleep(1) # Hız sınırı aşmamak için

        if not intel_report:
            return "İnternette güncel sakatlık/ceza haberi bulunamadı."
            
        return "\n".join(intel_report)
        
    except Exception as e:
        return f"Arama hatası: {e}"