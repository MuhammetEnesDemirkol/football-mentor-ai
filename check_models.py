import google.generativeai as genai

# API ANAHTARINI BURAYA YAPIŞTIR
API_KEY = "AAAAA"
genai.configure(api_key=API_KEY)

print("🔍 Erişilebilir Modeller Listeleniyor...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ Model Bulundu: {m.name}")
except Exception as e:
    print(f"❌ Hata: {e}")