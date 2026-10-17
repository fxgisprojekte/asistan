from google import genai
from google.genai import types
import requests
from datetime import datetime
import time
import threading

# =====================================================================
# 1. ŞİFRELERİMİZ (BURAYI KENDİ BİLGİLERİNLE DOLDUR)
# =====================================================================
import os

# Şifreleri artık buluttaki gizli kasadan alıyoruz:
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY)

# =====================================================================
# 2. YARDIMCI FONKSİYONLAR: Telegram Mesaj Gönderme ve Namaz Vakti
# =====================================================================

def telegrama_mesaj_gonder(mesaj: str):
    """Belirtilen metni doğrudan kullanıcının telefonundaki Telegram'a gönderir."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    veri = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj}
    try:
        requests.post(url, json=veri, timeout=10)
    except Exception as e:
        print(f"Telegram gönderim hatası: {e}")

def vakitleri_sozluk_olarak_al():
    # Bölgenin GPS koordinatları (Moers / Neukirchen-Vluyn: 51.45, 6.57)
    url = "http://api.aladhan.com/v1/timings?latitude=51.45&longitude=6.57&method=13"
    headers = {"User-Agent": "Mozilla/5.0"}
    cevap = requests.get(url, headers=headers, timeout=10).json()
    vakitler = cevap["data"]["timings"]
    
    return {
        "İmsak": vakitler["Fajr"][:5],
        "Güneş": vakitler["Sunrise"][:5],
        "Öğle": vakitler["Dhuhr"][:5],
        "İkindi": vakitler["Asr"][:5],
        "Akşam": vakitler["Maghrib"][:5],
        "Yatsı": vakitler["Isha"][:5]
    }

# =====================================================================
# 3. AJANIN ARAÇLARI (TOOLS / FONKSİYONLAR)
# =====================================================================

def gorev_ekle(gorev_metni: str) -> str:
    """Kullanıcı yeni bir görev, alışkanlık, kitap okuma veya spor (şınav, mekik, koşu) hedefi kaydetmek istediğinde çalıştır."""
    with open("gorevlerim.txt", "a", encoding="utf-8") as dosya:
        tarih = datetime.now().strftime("%d.%m.%Y %H:%M")
        dosya.write(f"- [{tarih}] {gorev_metni}\n")
    return f"BAŞARILI: '{gorev_metni}' görevi kaydedildi."

def gorevleri_listele() -> str:
    """Kullanıcı kayıtlı görevlerini veya hedeflerini görmek istediğinde çalıştır."""
    try:
        with open("gorevlerim.txt", "r", encoding="utf-8") as dosya:
            icerik = dosya.read()
        return f"Kayıtlı Görevler:\n{icerik}" if icerik else "Liste şu an boş."
    except FileNotFoundError:
        return "Henüz kayıtlı hiçbir görev yok."

def namaz_ve_kalan_sure_kontrol() -> str:
    """Kullanıcı namaz vakitlerini, sıradaki namazı veya vakte ne kadar kaldığını sorduğunda çalıştır."""
    try:
        vakitler = vakitleri_sozluk_olarak_al()
        simdi = datetime.now()
        simdi_dakika = simdi.hour * 60 + simdi.minute
        
        kalan_bilgisi = "Bugünkü tüm vakitler girdi (Yatsı okundu). Sıradaki vakit yarınki İmsak."
        for ad, saat_str in vakitler.items():
            saat, dakika = map(int, saat_str.split(":"))
            vakit_dakika = saat * 60 + dakika
            if vakit_dakika > simdi_dakika:
                fark = vakit_dakika - simdi_dakika
                saat_fark = fark // 60
                dk_fark = fark % 60
                kalan_bilgisi = f"Sıradaki vakit: {ad} ({saat_str}). Kalan süre: {saat_fark} saat {dk_fark} dakika (Toplam {fark} dk)!"
                break
                
        vakit_listesi = ", ".join([f"{k}: {v}" for k, v in vakitler.items()])
        return f"Şu anki saat: {simdi.strftime('%H:%M')} | Vakitler: [{vakit_listesi}] -> {kalan_bilgisi}"
    except Exception as hata:
        return f"Hata detayı: {hata}"

# =====================================================================
# 4. ARKA PLAN NÖBETÇİSİ (10 DAKİKA KALA TELEFONA BİLDİRİM ATAR)
# =====================================================================
def arka_plan_namaz_nobetcisi():
    """Arka planda sessizce çalışır ve vakte 10 dk kala Telegram'dan bildirim atar."""
    uyarilan_vakitler = set()
    while True:
        try:
            vakitler = vakitleri_sozluk_olarak_al()
            simdi = datetime.now()
            simdi_dakika = simdi.hour * 60 + simdi.minute
            
            for ad, saat_str in vakitler.items():
                saat, dakika = map(int, saat_str.split(":"))
                vakit_dakika = saat * 60 + dakika
                kalan = vakit_dakika - simdi_dakika
                
                # Vaktin girmesine (mevcut vaktin çıkmasına) 10 dakika kaldıysa:
                if kalan == 10 and ad not in uyarilan_vakitler:
                    uyari_mesaji = f"🔔 ACİL HATIRLATMA!\n\n{ad} vaktine (mevcut vaktin çıkmasına) 10 DAKİKA KALDI! (Saat: {saat_str})\nNamazını henüz kılmadıysan vakit çıkmadan yetişebilirsin! 🕌"
                    telegrama_mesaj_gonder(uyari_mesaji)
                    print(f"[BİLDİRİM GÖNDERİLDİ]: {ad} için 10 dk uyarısı telefona iletildi.")
                    uyarilan_vakitler.add(ad)
        except Exception:
            pass
        time.sleep(40) # Her 40 saniyede bir kontrol et

nobetci = threading.Thread(target=arka_plan_namaz_nobetcisi, daemon=True)
nobetci.start()

# =====================================================================
# 5. ASİSTANIN KARAKTERİ VE TELEGRAM DİNLEME DÖNGÜSÜ
# =====================================================================

sistem_talimati = """
Sen kullanıcının Telegram üzerinden çalışan kişisel yaşam, gelişim ve takip asistanısın (AI Agent).
Görevlerin:
1. Kullanıcının eklediği görevleri (kitap okuma, şınav, mekik, koşu vb.) `gorev_ekle` aracıyla kaydetmek ve sorduğunda `gorevleri_listele` ile göstermek.
2. Namaz vakitleri sorulduğunda `namaz_ve_kalan_sure_kontrol` aracını kullanmak.
3. Kullanıcı 'günlük paket', 'dil pratiği' veya 'borsa/teknoloji' istediğinde:
   - İngilizce (A2/B1 seviyesinde, Raymond Murphy 'Essential Grammar in Use' tarzı net örneklerle) veya Almanca (B2 seviyesinde) kullanışlı kelimeler ve kısa bir gramer ipucu ver.
   - Borsa ve finans dünyasından (ETF, F/K oranı, bileşik getiri, destek/direnç vb.) 1 kavramı çok basitçe açıkla.
   - Günü güzelleştirecek, tebessüm ettirecek kısa bir hikmetli söz veya espri ekle.
Samimi, motive edici ve telefonda okunması kolay (emojili, maddeli) bir dil kullan.
"""

sohbet = client.chats.create(
    model="gemini-3.8-flash",
    config=types.GenerateContentConfig(
        system_instruction=sistem_talimati,
        tools=[gorev_ekle, gorevleri_listele, namaz_ve_kalan_sure_kontrol],
        temperature=0.4
    )
)

print("=======================================================")
print("📱 TELEGRAM AI AGENT AKTİF! Telefonuna ilk mesaj gönderiliyor...")
print("Artık telefonundaki Telegram'dan botuna mesaj yazabilirsin!")
print("Programı kapatmak için bu ekranda Ctrl + C yapabilirsin.")
print("=======================================================\n")

# Program başlar başlamaz telefona "Ben hazırım!" mesajı atıyoruz:
telegrama_mesaj_gonder("🤖 Selam! Kişisel AI Agent'ın artık cebinde!\n\nBana buradan görev ekleyebilir, namaz vaktini sorabilir veya 'Günlük paketimi getir' diyebilirsin. Ayrıca vakit çıkmadan 10 dk önce seni buradan uyaracağım! 🚀")

# Telefondan gelen mesajları sürekli dinleyen döngü:
son_mesaj_id = 0

while True:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={son_mesaj_id + 1}&timeout=10"
        cevap = requests.get(url, timeout=15).json()
        
        if cevap.get("ok") and cevap.get("result"):
            for guncelleme in cevap["result"]:
                son_mesaj_id = guncelleme["update_id"]
                
                if "message" in guncelleme and "text" in guncelleme["message"]:
                    gelen_metin = guncelleme["message"]["text"]
                    gonderen_id = str(guncelleme["message"]["chat"]["id"])
                    
                    # Sadece senin telefonundan gelen mesajlara cevap ver (Güvenlik!):
                    if gonderen_id == str(TELEGRAM_CHAT_ID):
                        print(f"📱 Telefondan Gelen Mesaj: {gelen_metin}")
                        
                        # Gemini'ye sor ve cevabı al
                        ai_cevap = sohbet.send_message(gelen_metin)
                        
                        # Cevabı tekrar telefona (Telegram'a) gönder
                        telegrama_mesaj_gonder(ai_cevap.text)
                        print("✅ Cevap telefona gönderildi!\n")
    except Exception as e:
        time.sleep(3)