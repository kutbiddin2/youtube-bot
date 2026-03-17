"""
🎬 ALTERNATİF TARİH VİDEO BOTU v2
====================================
Gereksinimler:
  pip install google-genai edge-tts "moviepy==1.0.3" pillow requests nest-asyncio
"""

import os
import asyncio
import nest_asyncio
import textwrap
import requests
import json
import re
import time
from PIL import Image, ImageDraw, ImageFont
from google import genai
import edge_tts
from moviepy.config import change_settings
from moviepy.editor import (
    AudioFileClip, CompositeAudioClip,
    concatenate_videoclips, CompositeVideoClip, TextClip
)
from moviepy.audio.fx.all import audio_loop
from moviepy.video.VideoClip import VideoClip
import numpy as np

# Spyder'da asyncio sorunu için zorunlu
nest_asyncio.apply()

# ImageMagick yolu
change_settings({"IMAGEMAGICK_BINARY": r"C:\\Program Files\\ImageMagick-7.1.2-Q16\\magick.exe"})

# ─────────────────────────────────────────
#  AYARLAR — sadece buraya API key gir
# ─────────────────────────────────────────
GEMINI_API_KEY  = "AIzaSyCKKiZjApQohvsItD5MipEchySn9lSg3Ns"
MUZIK_DOSYASI   = r"C:\Users\Talha\OneDrive\Desktop\youtube\youtube3\muzik.mp3"
CIKTI_KLASORU   = r"C:\Users\Talha\OneDrive\Desktop\youtube\youtube3\videolar"
TTS_SES         = "tr-TR-AhmetNeural"
TTS_PITCH       = "-5Hz"
VIDEO_GENISLIK  = 1920
VIDEO_YUKSEKLIK = 1080
ALTYAZI_FONT_BOY = 52

# ─────────────────────────────────────────
#  1. SCRİPT ÜRET (Gemini)
# ─────────────────────────────────────────
def script_uret(konu=None):
    client = genai.Client(api_key=GEMINI_API_KEY)

    if konu:
        konu_kismi = f"Konu: {konu}"
    else:
        konu_kismi = """Dünyanın herhangi bir medeniyetinden, herhangi bir dönemden özgün bir POV konusu seç.
        Antik Mısır, Roma, Yunan, Mezopotamya, Osmanlı, Viking, Aztek, Maya, Çin, Japon, İslam altın çağı, 
        Orta Çağ Avrupa, Moğol, Pers, İnka gibi medeniyetlerden birini seç.
        Her seferinde farklı bir medeniyet ve farklı bir meslek/karakter ol.
        Sıradan insanlar da olabilir: çiftçi, tüccar, köle, rahip, asker, zanaatkar, çocuk, kadın.
        Daha önce işlenmemiş, özgün bir konu seç."""

    format_aciklama = """
FORMAT KURALLARI:
- Anlatım 2. şahıs ile olmalı: "Sabah gözlerini açıyorsun...", "Kapıdan çıkıyorsun..."
- İzleyiciyi o döneme taşı, sanki kendisi oradaymış gibi hissettir
- Günlük detaylar ver: ne yiyor, ne giyiyor, ne görüyor, ne kokuyor
- Tarihi gerçeklerle süsle ama akıcı tut
- Başlık "POV:" ile başlamalı
"""

    prompt = f"""Sen bir POV (Point of View) tarih içerik üreticisisin. Türkçe YouTube videoları için içerik üretiyorsun.
İzleyiciyi tarihin içine çekecek, 2. şahıs anlatımıyla yazıyorsun.

{konu_kismi}
{format_aciklama}

Aşağıdaki JSON formatında çıktı ver (başka hiçbir şey yazma, sadece JSON):

{{
  "baslik": "POV ile başlayan YouTube başlığı — çarpıcı ve merak uyandırıcı",
  "konu_ozeti": "2-3 cümle özet",
  "script": "Tam video metni. En az 800 kelime. 2. şahıs anlatımı: sen, seni, sana gibi. Sabahtan akşama kadar o dönemin bir gününü anlat. Tarihi detaylar, kıyafetler, yemekler, sosyal hayat, tehlikeler, güzellikler.",
  "gorsel_sahneler": [
    {{"sahne": 1, "aciklama": "Görsel 1 açıklaması", "prompt": "Detailed English image description, historical daily life scene, cinematic, warm lighting, oil painting style, immersive POV perspective, no text, no watermark"}},
    {{"sahne": 2, "aciklama": "Görsel 2 açıklaması", "prompt": "..."}},
    {{"sahne": 3, "aciklama": "...", "prompt": "..."}},
    {{"sahne": 4, "aciklama": "...", "prompt": "..."}},
    {{"sahne": 5, "aciklama": "...", "prompt": "..."}},
    {{"sahne": 6, "aciklama": "...", "prompt": "..."}},
    {{"sahne": 7, "aciklama": "...", "prompt": "..."}}
  ]
}}"""

    print("📝 Gemini'den script üretiliyor...")
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt
    )
    text = response.text.strip()
    text = re.sub(r"```json\s*|\s*```", "", text).strip()
    data = json.loads(text)
    print(f"✅ Script hazır: {data['baslik']}")
    print(f"   Kelime sayısı: {len(data['script'].split())}")
    return data

# ─────────────────────────────────────────
#  2. GÖRSEL ÜRET (ComfyUI - Yerel & Ücretsiz)
# ─────────────────────────────────────────
COMFYUI_URL = "http://127.0.0.1:8188"

def comfyui_model_adi() -> str:
    try:
        r = requests.get(f"{COMFYUI_URL}/object_info/CheckpointLoaderSimple", timeout=10)
        modeller = r.json()["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        print(f"   📦 Model: {modeller[0]}")
        return modeller[0]
    except:
        return "dreamshaper_8.safetensors"

def gorsel_uret(prompt: str, dosya_adi: str) -> str:
    try:
        model_adi = comfyui_model_adi()
        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7, "denoise": 1,
                    "latent_image": ["5", 0], "model": ["4", 0],
                    "negative": ["7", 0], "positive": ["6", 0],
                    "sampler_name": "euler", "scheduler": "normal",
                    "seed": int(time.time()) % 999999999, "steps": 20
                }
            },
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model_adi}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": 576, "width": 1024}},
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": prompt[:300] + ", cinematic, dramatic lighting, historical, detailed, masterpiece, 4k"}
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": "blurry, ugly, text, watermark, logo, bad anatomy, modern, cartoon"}
            },
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "tarih_bot", "images": ["8", 0]}}
        }

        print(f"      ComfyUI'de üretiliyor (~30 saniye)...")
        r = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow}, timeout=30)
        if r.status_code != 200:
            raise Exception(f"Prompt gönderilemedi: {r.status_code}")

        prompt_id = r.json()["prompt_id"]

        for _ in range(90):
            time.sleep(2)
            h = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10).json()
            if prompt_id in h and h[prompt_id].get("outputs"):
                break

        outputs = h[prompt_id]["outputs"]
        gorsel_bilgi = None
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                gorsel_bilgi = node_output["images"][0]
                break

        if not gorsel_bilgi:
            raise Exception("Görsel bulunamadı")

        img_r = requests.get(
            f"{COMFYUI_URL}/view",
            params={"filename": gorsel_bilgi["filename"], "subfolder": gorsel_bilgi.get("subfolder", ""), "type": "output"},
            timeout=30
        )
        with open(dosya_adi, "wb") as f:
            f.write(img_r.content)

        img = Image.open(dosya_adi).convert("RGB")
        img = img.resize((VIDEO_GENISLIK, VIDEO_YUKSEKLIK), Image.LANCZOS)
        img.save(dosya_adi)
        print(f"   ✅ Görsel hazır!")
        return dosya_adi

    except Exception as e:
        print(f"   ⚠️  Hata ({e}), yedek oluşturuluyor...")
        return gorsel_yedek_olustur(prompt, dosya_adi)

def gorsel_yedek_olustur(prompt: str, dosya_adi: str) -> str:
    img = Image.new("RGB", (VIDEO_GENISLIK, VIDEO_YUKSEKLIK), color=(20, 20, 35))
    draw = ImageDraw.Draw(img)
    for i in range(VIDEO_YUKSEKLIK):
        r = int(20 + (i / VIDEO_YUKSEKLIK) * 15)
        g = int(20 + (i / VIDEO_YUKSEKLIK) * 10)
        b = int(35 + (i / VIDEO_YUKSEKLIK) * 20)
        draw.line([(0, i), (VIDEO_GENISLIK, i)], fill=(r, g, b))
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 40)
    except:
        font = ImageFont.load_default()
    draw.rectangle([80, 80, VIDEO_GENISLIK-80, 90], fill=(180, 140, 60))
    draw.rectangle([80, VIDEO_YUKSEKLIK-90, VIDEO_GENISLIK-80, VIDEO_YUKSEKLIK-80], fill=(180, 140, 60))
    satirlar = textwrap.wrap(prompt[:120], width=50)
    y = VIDEO_YUKSEKLIK // 2 - (len(satirlar) * 50) // 2
    for satir in satirlar:
        bbox = draw.textbbox((0, 0), satir, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((VIDEO_GENISLIK - w) // 2, y), satir, font=font, fill=(220, 200, 140))
        y += 55
    img.save(dosya_adi)
    return dosya_adi

def gorselleri_uret(sahneler: list, klasor: str) -> list:
    print("\n🎨 Görseller üretiliyor (Pollinations AI - ücretsiz)...")
    gorsel_dosyalari = []
    for i, sahne in enumerate(sahneler):
        dosya = os.path.join(klasor, f"gorsel_{i+1:02d}.png")
        print(f"   [{i+1}/{len(sahneler)}] {sahne['aciklama'][:55]}...")
        gorsel_uret(sahne["prompt"], dosya)
        gorsel_dosyalari.append(dosya)
        time.sleep(3)
    return gorsel_dosyalari

# ─────────────────────────────────────────
#  3. SESLENDİRME (edge-tts)
# ─────────────────────────────────────────
async def seslendir_async(metin: str, dosya: str):
    communicate = edge_tts.Communicate(metin, TTS_SES, rate="+0%", pitch="-5Hz")
    await communicate.save(dosya)

def seslendir(metin: str, dosya: str):
    print("\n🎙️  Seslendirme yapılıyor...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(seslendir_async(metin, dosya))
    print(f"✅ Ses hazır: {dosya}")

# ─────────────────────────────────────────
#  4. ALTYAZI
# ─────────────────────────────────────────
def altyazi_parcalari_hesapla(script: str, toplam_sure: float) -> list:
    cumleler = re.split(r'(?<=[.!?])\s+', script.strip())
    cumleler = [c.strip() for c in cumleler if c.strip()]
    kelime_sayisi = sum(len(c.split()) for c in cumleler)
    kelime_basi_sure = toplam_sure / kelime_sayisi if kelime_sayisi > 0 else 0.3
    parcalar = []
    t = 0.0
    for cumle in cumleler:
        sure = len(cumle.split()) * kelime_basi_sure
        parcalar.append({"metin": cumle, "baslangic": t, "bitis": t + sure})
        t += sure
    return parcalar

# ─────────────────────────────────────────
#  5. VİDEO OLUŞTUR
# ─────────────────────────────────────────
def ken_burns_efekti(gorsel_dosyasi: str, sure: float, zoom_yon: str = "in"):
    img = Image.open(gorsel_dosyasi).convert("RGB")
    img_array = np.array(img)
    h, w = img_array.shape[:2]
    zoom_miktari = 0.00

    def make_frame(t):
        progress = t / sure
        if zoom_yon == "in":
            zoom = 1.0 + zoom_miktari * progress
        else:
            zoom = (1.0 + zoom_miktari) - zoom_miktari * progress
        new_w = int(w / zoom)
        new_h = int(h / zoom)
        x1 = (w - new_w) // 2
        y1 = (h - new_h) // 2
        crop = img_array[y1:y1+new_h, x1:x1+new_w]
        return np.array(Image.fromarray(crop).resize((VIDEO_GENISLIK, VIDEO_YUKSEKLIK), Image.LANCZOS))

    return VideoClip(make_frame, duration=sure)

def video_olustur(gorsel_dosyalari, ses_dosyasi, muzik_dosyasi, script, cikti_dosyasi, baslik):
    print("\n🎬 Video oluşturuluyor...")
    ana_ses = AudioFileClip(ses_dosyasi)
    toplam_sure = ana_ses.duration
    print(f"   Toplam süre: {toplam_sure:.1f}s ({toplam_sure/60:.1f} dk)")

    gorsel_sure = toplam_sure / len(gorsel_dosyalari)
    zoom_yonleri = ["in", "out", "in", "out", "in", "out", "in"]
    gorsel_klipleri = []

    for i, dosya in enumerate(gorsel_dosyalari):
        print(f"   [{i+1}/{len(gorsel_dosyalari)}] Görsel işleniyor...")
        klip = ken_burns_efekti(dosya, gorsel_sure, zoom_yonleri[i % len(zoom_yonleri)])
        klip = klip.fadein(0.8).fadeout(0.8)
        gorsel_klipleri.append(klip)

    video = concatenate_videoclips(gorsel_klipleri, method="compose")

    # Altyazılar
    print("   Altyazılar ekleniyor...")
    parcalar = altyazi_parcalari_hesapla(script, toplam_sure)
    altyazi_klipleri = []
    for parca in parcalar:
        metin = parca["metin"]
        if len(metin) > 60:
            ortasi = len(metin) // 2
            bosluk = metin.rfind(" ", 0, ortasi)
            if bosluk > 0:
                metin = metin[:bosluk] + "\n" + metin[bosluk+1:]
        try:
            txt = (TextClip(metin, fontsize=ALTYAZI_FONT_BOY, color="white",
                            font="Arial-Bold", stroke_color="black", stroke_width=2,
                            method="caption", size=(VIDEO_GENISLIK-200, None), align="center")
                   .set_start(parca["baslangic"])
                   .set_duration(parca["bitis"] - parca["baslangic"])
                   .set_position(("center", VIDEO_YUKSEKLIK - 180)))
            altyazi_klipleri.append(txt)
        except:
            pass

    # Başlık
    try:
        baslik_klip = (TextClip(baslik, fontsize=58, color="gold", font="Arial-Bold",
                                stroke_color="black", stroke_width=3,
                                method="caption", size=(VIDEO_GENISLIK-160, None), align="center")
                       .set_start(0).set_duration(4)
                       .set_position(("center", 60)).crossfadeout(1))
        altyazi_klipleri.append(baslik_klip)
    except:
        pass

    final_video = CompositeVideoClip([video] + altyazi_klipleri)

    # Müzik
    ses_listesi = [ana_ses]
    if os.path.exists(muzik_dosyasi):
        print("   🎵 Müzik ekleniyor...")
        muzik = AudioFileClip(muzik_dosyasi)
        muzik = audio_loop(muzik, duration=toplam_sure) if muzik.duration < toplam_sure else muzik.subclip(0, toplam_sure)
        ses_listesi.append(muzik.volumex(0.12))
    else:
        print(f"   ⚠️  '{muzik_dosyasi}' bulunamadı.")

    final_video = final_video.set_audio(CompositeAudioClip(ses_listesi))

    print("   💾 Kaydediliyor (bu birkaç dakika sürebilir)...")
    final_video.write_videofile(cikti_dosyasi, fps=24, codec="libx264",
                                 audio_codec="aac", bitrate="5000k", threads=4, logger=None)
    print(f"\n✅ Video hazır: {cikti_dosyasi}")

# ─────────────────────────────────────────
#  ÇALIŞTIR
# ─────────────────────────────────────────
def main(konu=None):
    os.makedirs(CIKTI_KLASORU, exist_ok=True)
    veri     = script_uret(konu)
    baslik   = veri["baslik"]
    script   = veri["script"]
    sahneler = veri["gorsel_sahneler"]

    guvenli  = re.sub(r'[^\w\s-]', '', baslik)[:60].strip().replace(" ", "_")
    klasor   = os.path.join(CIKTI_KLASORU, guvenli)
    os.makedirs(klasor, exist_ok=True)

    print(f"\n{'='*60}\n📹 {baslik}\n{'='*60}")

    ses_dosyasi   = os.path.join(klasor, "anlatim.mp3")
    cikti_dosyasi = os.path.join(CIKTI_KLASORU, f"{guvenli}.mp4")

    gorsel_dosyalari = gorselleri_uret(sahneler, klasor)
    seslendir(script, ses_dosyasi)
    video_olustur(gorsel_dosyalari, ses_dosyasi, MUZIK_DOSYASI, script, cikti_dosyasi, baslik)

    print(f"""
╔══════════════════════════════════════════╗
║  🎉 VİDEO TAMAMLANDI!
║  📁 {cikti_dosyasi}
╚══════════════════════════════════════════╝""")
    return cikti_dosyasi


if __name__ == "__main__":
    video_sayisi = 8  # Kaç video üretsin, istediğin kadar artır

    basarili = 0
    for i in range(video_sayisi):
        print(f"\n{'='*60}")
        print(f"🎬 VIDEO {i+1}/{video_sayisi} başlıyor...")
        print(f"{'='*60}")
        try:
            main()
            basarili += 1
            print(f"✅ {basarili} video tamamlandı! 30 saniye bekleniyor...")
            time.sleep(30)
        except Exception as e:
            print(f"⚠️  Hata: {e}")
            print("⏳ 60 saniye beklenip tekrar denenecek...")
            time.sleep(60)

    print(f"\n🎉 Bitti! {basarili}/{video_sayisi} video üretildi.")