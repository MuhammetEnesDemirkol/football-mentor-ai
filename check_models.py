import google.generativeai as genai

# API ANAHTARINI BURAYA YAPIŞTIR
API_KEY = "AIzaSyCCw37qFzOwielzD4t4P5ye87wG0uuBTS0"
genai.configure(api_key=API_KEY)

print("🔍 Erişilebilir Modeller Listeleniyor...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ Model Bulundu: {m.name}")
except Exception as e:
    print(f"❌ Hata: {e}")