import streamlit as st
import asyncio
import json
import random
import tempfile
import os
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import edge_tts
import imageio_ffmpeg
import time

# Setup FFmpeg
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

W, H = 1080, 1920
FPS = 30

# ==========================================
# 1. CUSTOM CSS UNTUK TAMPILAN MODERN
# ==========================================
st.set_page_config(page_title="LATE Gaming Studio", page_icon="🎮", layout="wide")

custom_css = """
<style>
    .stApp {
        background: linear-gradient(135deg, #0b0c10 0%, #1f2833 100%);
        color: #c5c6c7;
        font-family: 'Inter', sans-serif;
    }
    .title-text {
        font-size: 3rem;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #66fcf1, #45a29e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
        text-align: center;
    }
    .subtitle-text {
        text-align: center;
        color: #45a29e;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    div[data-testid="stForm"] {
        background-color: rgba(31, 40, 51, 0.6);
        border: 1px solid rgba(102, 252, 241, 0.2);
        border-radius: 15px;
        padding: 2rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(10px);
    }
    .stTextInput > div > div > input, .stTextArea > div > div > textarea, .stSelectbox > div > div {
        background-color: #0b0c10 !important;
        color: #66fcf1 !important;
        border: 1px solid #45a29e !important;
        border-radius: 8px !important;
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #45a29e 0%, #66fcf1 100%);
        color: #0b0c10 !important;
        font-weight: bold;
        font-size: 1.2rem;
        padding: 10px 20px;
        border: none;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 15px rgba(102, 252, 241, 0.5);
    }
    .stVideo {
        border-radius: 15px;
        overflow: hidden;
        border: 2px solid #45a29e;
    }
    .stDownloadButton > button {
        background-color: transparent;
        color: #66fcf1 !important;
        border: 2px solid #66fcf1;
        border-radius: 8px;
        font-weight: bold;
    }
    .stDownloadButton > button:hover {
        background-color: rgba(102, 252, 241, 0.1);
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ==========================================
# 2. FUNGSI-FUNGSI PEMBUAT VIDEO
# ==========================================
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def wrap_text(draw, text, fnt, max_width):
    words, lines, line = text.split(), [], ""
    for word in words:
        test = (line + " " + word).strip()
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width:
            line = test
        else:
            if line: lines.append(line)
            line = word
    if line: lines.append(line)
    return lines

def split_into_chunks(text: str, max_chars: int) -> list[str]:
    sentences, buf = [], ""
    for ch in text:
        buf += ch
        if ch in ".!?":
            sentences.append(buf.strip())
            buf = ""
    if buf.strip(): sentences.append(buf.strip())

    chunks, current = [], ""
    for s in sentences:
        candidate = (current + " " + s).strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current: chunks.append(current)
            current = s
    if current: chunks.append(current)

    final = []
    for c in chunks:
        while len(c) > max_chars:
            cut = c[:max_chars]
            cut = cut[: cut.rfind(" ")]
            final.append(cut.strip())
            c = c[len(cut):].strip()
        if c: final.append(c)
    return final

def build_gradient(top, bottom):
    top_arr = np.array(top, dtype=np.float32)
    bottom_arr = np.array(bottom, dtype=np.float32)
    grad = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None, None]
    arr = top_arr * (1 - grad) + bottom_arr * grad
    arr = np.repeat(arr, W, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB")

def draw_slide(index, label, text, out_path, seed):
    rng = random.Random(seed + index)
    palettes = [
        ((10, 12, 35), (35, 18, 75), (0, 220, 255)),
        ((8, 22, 38), (28, 15, 65), (255, 70, 180)),
        ((15, 12, 32), (12, 55, 72), (120, 255, 190)),
        ((25, 10, 40), (8, 20, 55), (255, 190, 70)),
    ]
    top, bottom, accent = palettes[index % len(palettes)]
    img = build_gradient(top, bottom)
    d = ImageDraw.Draw(img, "RGBA")

    for _ in range(18):
        x, y = rng.randint(-200, W + 200), rng.randint(-100, H + 100)
        r = rng.randint(40, 260)
        d.ellipse((x - r, y - r, x + r, y + r), outline=(*accent, rng.randint(12, 42)), width=rng.randint(2, 8))
    for _ in range(22):
        y = rng.randint(0, H)
        d.line((0, y, W, y - rng.randint(-80, 80)), fill=(*accent, 18), width=2)

    d.rounded_rectangle((62, 120, W - 62, H - 120), radius=42, outline=(*accent, 150), width=4)
    d.text((95, 185), "LATE GAMING", font=font(48, True), fill=(245, 248, 255, 255))
    d.text((95, 270), label.upper(), font=font(31, True), fill=(*accent, 255))

    body_size = 66
    fnt = font(body_size, True)
    lines = wrap_text(d, text, fnt, W - 190)
    while (len(lines) > 8 or len(lines) * int(body_size * 1.35) > (H - 610 - 340)) and body_size > 40:
        body_size -= 4
        fnt = font(body_size, True)
        lines = wrap_text(d, text, fnt, W - 190)

    y = 610
    line_h = int(body_size * 1.42)
    for line in lines[:10]:
        d.text((95, y), line, font=fnt, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 90))
        y += line_h

    d.rounded_rectangle((95, H - 310, W - 95, H - 220), radius=24, fill=(*accent, 38), outline=(*accent, 180), width=2)
    d.text((125, H - 292), "FOLLOW FOR MORE GAMING TIPS", font=font(28, True), fill=(255, 255, 255, 255))
    img.save(out_path, quality=95)

# Fungsi TTS sekarang menerima parameter 'voice'
async def make_voice(text, path, voice_name):
    communicate = edge_tts.Communicate(text, voice=voice_name, rate="+2%")
    await communicate.save(str(path))


# ==========================================
# 3. ANTARMUKA WEB (UI)
# ==========================================
st.markdown('<h1 class="title-text">LATE GAMING STUDIO</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle-text">Professional Shorts Generator v2.0</p>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    with st.form("input_form"):
        st.markdown("### 📝 Content Details")
        title = st.text_input("Video Title", "Why Warm-Ups Matter in Competitive Gaming")
        hook = st.text_area("Hook (Opening)", "Want more consistent aim? Stop jumping straight into ranked matches.", height=80)
        body = st.text_area("Body (The Tips)", "A short warm-up helps you get comfortable with your sensitivity, movement, and timing. Spend a few minutes in a practice range or a low-pressure mode before competitive games. Focus on smooth control instead of chasing a perfect score. The goal is to start focused, not exhausted.", height=150)
        takeaway = st.text_area("Takeaway (Closing)", "Build a small warm-up routine, then stay consistent. Follow LATE Gaming for more practical gaming tips.", height=80)
        
        st.markdown("### 🗣️ Voice Settings")
        # PILIHAN BAHASA
        voice_options = {
            "English (US) - Male": "en-US-GuyNeural",
            "English (US) - Female": "en-US-AriaNeural",
            "English (UK) - Male": "en-GB-RyanNeural",
            "Indonesian - Male": "id-ID-ArdiNeural",
            "Indonesian - Female": "id-ID-GadisNeural",
            "Japanese - Female": "ja-JP-NanamiNeural",
            "Spanish - Male": "es-ES-AlvaroNeural"
        }
        selected_voice = st.selectbox("Pilih Bahasa & Suara", list(voice_options.keys()))
        
        submitted = st.form_submit_button("🚀 GENERATE VIDEO")

with col2:
    if submitted:
        progress_text = "Memproses video... Mohon tunggu."
        my_bar = st.progress(0, text=progress_text)
        
        time.sleep(0.5)
        my_bar.progress(20, text="1/4 Menghasilkan Suara (TTS)...")
        
        temp_dir = tempfile.mkdtemp()
        out_dir = Path(temp_dir)
        narration = " ".join([hook, body, takeaway])
        
        voice_path = out_dir / "voice.mp3"
        # Menggunakan voice yang dipilih
        voice_id = voice_options[selected_voice]
        asyncio.run(make_voice(narration, voice_path, voice_id))
        
        my_bar.progress(40, text="2/4 Menghitung Durasi Audio...")
        
        probe = subprocess.run(
            [ffmpeg_path.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(voice_path)],
            check=True, capture_output=True, text=True
        )
        try:
            duration = max(12.0, float(probe.stdout.strip()) + 0.5)
        except ValueError:
            duration = 15.0
            
        my_bar.progress(60, text="3/4 Menggambar Slide Grafis...")
        
        slide_specs = [("THE HOOK", hook)]
        body_chunks = split_into_chunks(body, 180)[:3]
        for i, chunk in enumerate(body_chunks):
            slide_specs.append(("THE TIP" if i == 0 else "MORE TIPS", chunk))
        slide_specs.append(("REMEMBER THIS", takeaway))
        
        slide_paths = []
        seed = random.randint(1, 10000)
        for i, (label, text) in enumerate(slide_specs):
            p = out_dir / f"slide_{i+1}.png"
            draw_slide(i, label, text, p, seed)
            slide_paths.append(p)
            
        my_bar.progress(80, text="4/4 Merender Video Final (FFmpeg)...")
        
        per_slide = duration / len(slide_paths)
        concat_file = out_dir / "slides.txt"
        with open(concat_file, "w") as f:
            for p in slide_paths:
                f.write(f"file '{p.name}'\n")
                f.write(f"duration {per_slide:.3f}\n")
            f.write(f"file '{slide_paths[-1].name}'\n")
            
        video_path = out_dir / "output.mp4"
        
        cmd = [
            ffmpeg_path, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-i", str(voice_path),
            "-vf", f"scale={W}:{H},format=yuv420p",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25",
            "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
            str(video_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        
        my_bar.progress(100, text="✅ Video Berhasil Dibuat!")
        time.sleep(0.5)
        my_bar.empty()
        
        st.success("Video siap diunduh dan diunggah ke YouTube!")
        st.video(str(video_path))
        
        with open(video_path, "rb") as f:
            video_bytes = f.read()
            
        st.download_button(
            label="⬇️ DOWNLOAD MP4",
            data=video_bytes,
            file_name="LATE_Gaming_Short.mp4",
            mime="video/mp4",
            use_container_width=True
        )
        
        st.markdown("### 📋 YouTube Metadata")
        metadata_text = f"Title: {title}\n\nDescription:\n{hook}\n\n{body}\n\n{takeaway}\n\n#Gaming #Shorts #LateGaming"
        st.code(metadata_text, language="text")
    else:
        st.info("👈 Isi form di sebelah kiri dan klik **Generate Video** untuk melihat hasilnya di sini.")
