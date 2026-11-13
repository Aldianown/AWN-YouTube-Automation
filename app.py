import streamlit as st
import asyncio
import json
import random
import tempfile
import os
import time
import requests
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import edge_tts
import imageio_ffmpeg
import yt_dlp
import google.generativeai as genai

# Setup FFmpeg
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

W, H = 1080, 1920
FPS = 30

# ==========================================
# KONFIGURASI HALAMAN & CSS MODERN
# ==========================================
st.set_page_config(page_title="AWN Studio", page_icon="🎬", layout="wide")

custom_css = """
<style>
    .stApp { background: #0b0c10; color: #c5c6c7; font-family: 'Inter', sans-serif; }
    .main-title { font-size: 2.5rem; font-weight: 900; letter-spacing: 2px; color: #ffffff; margin-bottom: 0px; }
    .main-title span { color: #66fcf1; }
    .mode-title { font-size: 1.5rem; font-weight: 600; color: #45a29e; margin-top: 0px; margin-bottom: 2rem; border-bottom: 1px solid #1f2833; padding-bottom: 10px;}
    
    div[data-testid="stForm"], .stContainer { background-color: rgba(31, 40, 51, 0.4); border: 1px solid rgba(102, 252, 241, 0.1); border-radius: 12px; padding: 2rem; }
    .stTextInput > div > div > input, .stTextArea > div > div > textarea, .stSelectbox > div > div { background-color: #0b0c10 !important; color: #66fcf1 !important; border: 1px solid #45a29e !important; border-radius: 6px !important; }
    
    .stButton > button { width: 100%; background: #66fcf1; color: #0b0c10 !important; font-weight: bold; border: none; border-radius: 6px; transition: 0.3s; }
    .stButton > button:hover { background: #45a29e; color: white !important; box-shadow: 0 0 10px #66fcf1; }
    
    .stVideo { border-radius: 10px; overflow: hidden; border: 2px solid #45a29e; }
    .stDownloadButton > button { background-color: transparent; color: #66fcf1 !important; border: 2px solid #66fcf1; border-radius: 6px; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ==========================================
# FUNGSI BANTUAN
# ==========================================
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists(): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def wrap_text(draw, text, fnt, max_width):
    words, lines, line = text.split(), [], ""
    for word in words:
        test = (line + " " + word).strip()
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width: line = test
        else:
            if line: lines.append(line)
            line = word
    if line: lines.append(line)
    return lines

def split_into_chunks(text: str, max_chars: int) -> list[str]:
    sentences, buf = [], ""
    for ch in text:
        buf += ch
        if ch in ".!?": sentences.append(buf.strip()); buf = ""
    if buf.strip(): sentences.append(buf.strip())
    chunks, current = [], ""
    for s in sentences:
        candidate = (current + " " + s).strip()
        if len(candidate) <= max_chars: current = candidate
        else:
            if current: chunks.append(current)
            current = s
    if current: chunks.append(current)
    final = []
    for c in chunks:
        while len(c) > max_chars:
            cut = c[:max_chars]; cut = cut[: cut.rfind(" ")]
            final.append(cut.strip()); c = c[len(cut):].strip()
        if c: final.append(c)
    return final

async def make_voice(text, path, voice_name):
    communicate = edge_tts.Communicate(text, voice=voice_name, rate="+2%")
    await communicate.save(str(path))

def fetch_pixabay_video(keyword, api_key):
    if not api_key: return None
    url = f"https://pixabay.com/api/videos/?key={api_key}&q={keyword}&video_type=film&orientation=vertical&per_page=5"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('hits'):
                video = data['hits'][0]
                if 'videos' in video and 'large' in video['videos']:
                    return video['videos']['large']['url']
    except: pass
    return None

def generate_ai_image(prompt):
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1920&nologo=true"
    try:
        response = requests.get(url, timeout=40)
        if response.status_code == 200: return response.content
    except: pass
    return None

# ==========================================
# SIDEBAR (MENU SETING & API KEYS)
# ==========================================
with st.sidebar:
    st.markdown('<h1 class="main-title">AWN<span>-STUDIO</span></h1>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### ⚙️ Pengaturan")
    
    app_mode = st.radio(
        "Pilih Studio Mode:",
        ("AI Director", "Smart Clipper", "URL Extractor", "Classic Shorts")
    )
    
    st.markdown("---")
    st.markdown("### 🔑 API Keys")
    st.caption("Masukkan API Key Anda di sini (Aman & tidak tersimpan di GitHub).")
    
    try:
        default_pixabay = st.secrets.get("PIXABAY_API_KEY", "")
        default_gemini = st.secrets.get("GEMINI_API_KEY", "")
    except:
        default_pixabay = ""
        default_gemini = ""
        
    user_pixabay_key = st.text_input("Pixabay API Key", type="password", value=default_pixabay)
    user_gemini_key = st.text_input("Gemini API Key", type="password", value=default_gemini)
    
    st.markdown("---")
    st.caption("AWN Studio v7.0 | Powered by Streamlit & AI")

# ==========================================
# AREA KONTEN UTAMA
# ==========================================

# --- MODE 1: AI DIRECTOR ---
if app_mode == "AI Director":
    st.markdown('<h2 class="mode-title">🎬 AI Director Studio</h2>', unsafe_allow_html=True)
    st.write("Ubah ide sederhana menjadi video sinematik dengan bantuan AI Sutradara (Gemini).")
    
    if "ai_generated_prompt" not in st.session_state:
        st.session_state.ai_generated_prompt = "A futuristic cyberpunk car restoration in a neon garage, 4k, highly detailed"

    col1, col2 = st.columns([1, 1])
    with col1:
        keyword_input = st.text_input("Masukkan Ide Sederhana", "Car restoration in a futuristic garage")
        if st.button("🪄 Buat Prompt Detail (AI)"):
            if user_gemini_key:
                with st.spinner("AI Sutradara sedang bekerja..."):
                    try:
                        genai.configure(api_key=user_gemini_key)
                        model = genai.GenerativeModel('gemini-3.8-flash')
                        sys_prompt = "You are an expert Hollywood Cinematographer. Expand this keyword into a highly detailed video prompt including camera, lighting, and style. Keep it under 3 sentences. ONLY the prompt."
                        response = model.generate_content(f"{sys_prompt}\nKeyword: {keyword_input}")
                        st.session_state.ai_generated_prompt = response.text.strip()
                        st.success("Prompt berhasil dibuat!")
                    except Exception as e:
                        st.error(f"Gagal: {e}")
            else:
                st.warning("Masukkan Gemini API Key di sidebar kiri.")
                
        ai_voice = st.selectbox("Pilih Suara Narasi", ["en-US-GuyNeural", "id-ID-ArdiNeural", "en-US-AriaNeural"], key="ai_voice")

    with col2:
        final_prompt = st.text_area("Prompt Video (Bisa diedit)", value=st.session_state.ai_generated_prompt, height=150)
        if st.button("🚀 Render AI Video", key="btn_ai"):
            with st.spinner("AI sedang menggambar dan merender video..."):
                temp_dir = tempfile.mkdtemp(); out_dir = Path(temp_dir)
                img_data = generate_ai_image(final_prompt)
                if img_data:
                    img_path = out_dir / "ai_image.jpg"
                    with open(img_path, "wb") as f: f.write(img_data)
                    voice_path = out_dir / "voice.mp3"
                    asyncio.run(make_voice(keyword_input, voice_path, ai_voice))
                    video_path = out_dir / "ai_output.mp4"
                    cmd = [ffmpeg_path, "-y", "-loop", "1", "-i", str(img_path), "-i", str(voice_path),
                           "-vf", f"scale={W*1.5}:{H*1.5},zoompan=z='min(zoom+0.0015,1.5)':d={FPS*10}:s={W}x{H},format=yuv420p",
                           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(video_path)]
                    subprocess.run(cmd, check=True, capture_output=True)
                    st.success("✅ Video Berhasil!")
                    st.video(str(video_path))
                    with open(video_path, "rb") as f: st.download_button("⬇️ Download MP4", f.read(), "AI_Shorts.mp4", "video/mp4")
                else:
                    st.error("Gagal membuat gambar AI.")

# --- MODE 2: SMART CLIPPER ---
elif app_mode == "Smart Clipper":
    st.markdown('<h2 class="mode-title">✂️ Smart Clipper Studio</h2>', unsafe_allow_html=True)
    st.write("Potong video lokal Anda menjadi format vertikal 9:16 secara instan.")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_file = st.file_uploader("Upload Video (MP4, MOV)", type=["mp4", "mov"])
        clip_start = st.number_input("Mulai dari detik ke-", min_value=0, value=0)
        clip_duration = st.number_input("Durasi klip (detik)", min_value=5, value=30)
        if st.button("✂️ Potong Video"):
            if uploaded_file:
                with st.spinner("Memproses klip..."):
                    temp_dir = tempfile.mkdtemp(); out_dir = Path(temp_dir)
                    input_path = out_dir / "input.mp4"
                    with open(input_path, "wb") as f: f.write(uploaded_file.read())
                    video_path = out_dir / "clipped.mp4"
                    cmd = [ffmpeg_path, "-y", "-ss", str(clip_start), "-t", str(clip_duration), "-i", str(input_path),
                           "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=yuv420p",
                           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25", "-c:a", "aac", "-b:a", "128k", str(video_path)]
                    subprocess.run(cmd, check=True, capture_output=True)
                    st.success("✅ Klip Dibuat!")
                    st.video(str(video_path))
                    with open(video_path, "rb") as f: st.download_button("⬇️ Download MP4", f.read(), "Clip_Shorts.mp4", "video/mp4")
            else:
                st.warning("Silakan upload video dulu.")
    with col2:
        st.info("💡 **Tips Clipper:**\n\n1. Video apapun (horizontal/vertikal) akan otomatis di-zoom ke tengah agar pas di layar HP.\n2. Gunakan durasi 15-60 detik untuk hasil Shorts yang optimal.")

# --- MODE 3: URL EXTRACTOR ---
elif app_mode == "URL Extractor":
    st.markdown('<h2 class="mode-title">🌐 URL Extractor Studio</h2>', unsafe_allow_html=True)
    st.write("Download dan potong klip dari link YouTube, TikTok, atau Instagram.")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        video_url = st.text_input("Link Video (URL)", "https://www.youtube.com/watch?v=...")
        url_start = st.number_input("Mulai dari detik ke-", min_value=0, value=0)
        url_duration = st.number_input("Durasi klip (detik)", min_value=5, value=30)
        if st.button("🌐 Download & Potong"):
            if video_url:
                with st.spinner("Mengunduh & memproses..."):
                    temp_dir = tempfile.mkdtemp(); out_dir = Path(temp_dir)
                    ydl_opts = {'format': 'best[ext=mp4]', 'outtmpl': str(out_dir / 'dl.mp4'), 'quiet': True}
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([video_url])
                        video_path = out_dir / "url_clip.mp4"
                        cmd = [ffmpeg_path, "-y", "-ss", str(url_start), "-t", str(url_duration), "-i", str(out_dir / 'dl.mp4'),
                               "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=yuv420p",
                               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25", "-c:a", "aac", "-b:a", "128k", str(video_path)]
                        subprocess.run(cmd, check=True, capture_output=True)
                        st.success("✅ Klip URL Dibuat!")
                        st.video(str(video_path))
                        with open(video_path, "rb") as f: st.download_button("⬇️ Download MP4", f.read(), "URL_Shorts.mp4", "video/mp4")
                    except Exception as e:
                        st.error(f"Gagal: {e}")
            else:
                st.warning("Masukkan link yang valid.")
    with col2:
        st.info("⚠️ **Peringatan:**\n\nDownload dari YouTube/TikTok kadang diblokir oleh server jika link bersifat privat atau memiliki proteksi ketat.")

# --- MODE 4: CLASSIC SHORTS ---
elif app_mode == "Classic Shorts":
    st.markdown('<h2 class="mode-title">💡 Classic Shorts Studio</h2>', unsafe_allow_html=True)
    st.write("Buat video Shorts standar dengan teks dan latar belakang video stock (Pixabay).")
    
    with st.form("classic_form"):
        col1, col2 = st.columns([1, 1])
        with col1:
            title = st.text_input("Video Title", "Why Warm-Ups Matter in Competitive Gaming")
            hook = st.text_area("Hook (Opening)", "Want more consistent aim?", height=80)
            body = st.text_area("Body (The Tips)", "A short warm-up helps you get comfortable.", height=100)
            takeaway = st.text_area("Takeaway (Closing)", "Build a small warm-up routine.", height=80)
        with col2:
            bg_keyword = st.text_input("Cari Background Video (Keywords)", "neon gaming")
            selected_voice = st.selectbox("Pilih Suara", ["en-US-GuyNeural", "id-ID-ArdiNeural", "id-ID-GadisNeural"], key="std_voice")
            st.write("Preview Background:")
            if bg_keyword:
                st.caption(f"Akan mencari video: *{bg_keyword}*")
        
        submitted = st.form_submit_button("🚀 Generate Classic Short")
        
    if submitted:
        if not user_pixabay_key:
            st.warning("Masukkan Pixabay API Key di sidebar untuk mencari video background.")
        else:
            with st.spinner("Merender video..."):
                temp_dir = tempfile.mkdtemp(); out_dir = Path(temp_dir)
                bg_video_path = None
                if bg_keyword.strip():
                    video_url = fetch_pixabay_video(bg_keyword, user_pixabay_key)
                    if video_url:
                        bg_video_path = out_dir / "background.mp4"
                        try:
                            with open(bg_video_path, 'wb') as f: f.write(requests.get(video_url, timeout=15).content)
                        except: bg_video_path = None
                
                narration = " ".join([hook, body, takeaway])
                voice_path = out_dir / "voice.mp3"
                asyncio.run(make_voice(narration, voice_path, selected_voice))
                duration = max(12.0, (len(narration) / 14.0) + 0.5)
                
                slide_specs = [("THE HOOK", hook)] + [("THE TIP", chunk) for chunk in split_into_chunks(body, 180)[:2]] + [("REMEMBER THIS", takeaway)]
                slide_paths = []
                bg_frame_path = out_dir / "bg_frame.jpg" if bg_video_path else None
                if bg_video_path:
                    subprocess.run([ffmpeg_path, "-y", "-i", str(bg_video_path), "-ss", "00:00:01", "-vframes", "1", str(bg_frame_path)], capture_output=True)

                for i, (label, text) in enumerate(slide_specs):
                    p = out_dir / f"slide_{i+1}.png"
                    if bg_frame_path and bg_frame_path.exists():
                        img = Image.open(bg_frame_path).convert("RGB").resize((W, H))
                        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 100))
                        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
                    else:
                        img = Image.new("RGB", (W, H), (10, 12, 35))
                    
                    d = ImageDraw.Draw(img, "RGBA")
                    d.rounded_rectangle((62, 120, W - 62, H - 120), radius=42, outline=(0, 220, 255, 150), width=4)
                    d.text((95, 185), "AWN STUDIO", font=font(48, True), fill=(255, 255, 255, 255))
                    d.text((95, 270), label.upper(), font=font(31, True), fill=(0, 220, 255, 255))
                    
                    body_size = 56
                    fnt = font(body_size, True)
                    lines = wrap_text(d, text, fnt, W - 190)
                    while (len(lines) > 8) and body_size > 36:
                        body_size -= 2; fnt = font(body_size, True); lines = wrap_text(d, text, fnt, W - 190)
                    
                    y = 610
                    for line in lines[:10]:
                        d.text((95, y), line, font=fnt, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 200))
                        y += int(body_size * 1.42)
                    d.rounded_rectangle((95, H - 310, W - 95, H - 220), radius=24, fill=(0, 220, 255, 38), outline=(0, 220, 255, 180), width=2)
                    d.text((125, H - 292), "FOLLOW FOR MORE TIPS", font=font(28, True), fill=(255, 255, 255, 255))
                    img.save(p, quality=95)
                    slide_paths.append(p)
                    
                per_slide = duration / len(slide_paths)
                concat_file = out_dir / "slides.txt"
                with open(concat_file, "w") as f:
                    for p in slide_paths:
                        f.write(f"file '{p.name}'\n"); f.write(f"duration {per_slide:.3f}\n")
                    f.write(f"file '{slide_paths[-1].name}'\n")
                    
                video_path = out_dir / "output.mp4"
                if bg_video_path:
                    cmd = [ffmpeg_path, "-y", "-stream_loop", "-1", "-i", str(bg_video_path), "-f", "concat", "-safe", "0", "-i", str(concat_file), "-i", str(voice_path),
                           "-filter_complex", f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}[bg];[bg][1:v]overlay=shortest=1,format=yuv420p[v]",
                           "-map", "[v]", "-map", "2:a", "-r", str(FPS), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(video_path)]
                else:
                    cmd = [ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-i", str(voice_path),
                           "-vf", f"scale={W}:{H},format=yuv420p", "-r", str(FPS), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(video_path)]
                subprocess.run(cmd, check=True, capture_output=True)
                
                st.success("✅ Video Berhasil Dibuat!")
                st.video(str(video_path))
                with open(video_path, "rb") as f: st.download_button("⬇️ Download MP4", f.read(), "AWN_Short.mp4", "video/mp4")
                st.markdown("### 📋 YouTube Metadata")
                st.code(f"Title: {title}\n\nDescription:\n{hook}\n\n{body}\n\n{takeaway}\n\n#Gaming #Shorts", language="text")
