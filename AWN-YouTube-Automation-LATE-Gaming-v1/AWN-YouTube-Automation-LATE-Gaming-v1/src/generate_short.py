import json
import math
import os
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import edge_tts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
TOPICS = ROOT / "content" / "topics.json"
W, H = 1080, 1920
FPS = 30

def font(size, bold=False):
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
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines

def draw_slide(index, label, text, out_path, seed):
    rng = random.Random(seed + index)
    palettes = [
        ((10, 12, 35), (35, 18, 75), (0, 220, 255)),
        ((8, 22, 38), (28, 15, 65), (255, 70, 180)),
        ((15, 12, 32), (12, 55, 72), (120, 255, 190)),
        ((25, 10, 40), (8, 20, 55), (255, 190, 70)),
    ]
    top, bottom, accent = palettes[index % len(palettes)]
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        c = tuple(int(top[k] * (1-t) + bottom[k] * t) for k in range(3))
        for x in range(W):
            px[x, y] = c
    d = ImageDraw.Draw(img, "RGBA")
    # Original abstract neon rings and bars; no third-party game assets.
    for _ in range(18):
        x, y = rng.randint(-200, W+200), rng.randint(-100, H+100)
        r = rng.randint(40, 260)
        d.ellipse((x-r, y-r, x+r, y+r), outline=(*accent, rng.randint(12, 42)), width=rng.randint(2, 8))
    for _ in range(22):
        y = rng.randint(0, H)
        d.line((0, y, W, y-rng.randint(-80, 80)), fill=(*accent, 18), width=2)
    d.rounded_rectangle((62, 120, W-62, H-120), radius=42, outline=(*accent, 150), width=4)
    d.text((95, 185), "LATE GAMING", font=font(48, True), fill=(245, 248, 255, 255))
    d.text((95, 270), label.upper(), font=font(31, True), fill=(*accent, 255))
    lines = wrap_text(d, text, font(66, True), W-190)
    y = 610
    line_h = 94
    for line in lines[:8]:
        d.text((95, y), line, font=font(66, True), fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0,0,0,90))
        y += line_h
    d.rounded_rectangle((95, H-310, W-95, H-220), radius=24, fill=(*accent, 38), outline=(*accent, 180), width=2)
    d.text((125, H-292), "FOLLOW FOR MORE GAMING TIPS", font=font(28, True), fill=(255,255,255,255))
    img.save(out_path, quality=95)

async def make_voice(text, path):
    communicate = edge_tts.Communicate(text, voice="en-US-GuyNeural", rate="+2%", volume="+0%")
    await communicate.save(str(path))

def run(cmd):
    print("RUN:", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)

def main():
    OUT.mkdir(exist_ok=True)
    with open(TOPICS, "r", encoding="utf-8") as f:
        topics = json.load(f)
    # Stable daily rotation based on UTC date.
    day = datetime.now(timezone.utc).date()
    topic = topics[day.toordinal() % len(topics)]
    narration = " ".join([topic["hook"], topic["body"], topic["takeaway"]])
    title = topic["title"][:95]
    description = (
        f"{topic['hook']}\n\n{topic['body']}\n\n{topic['takeaway']}\n\n"
        "#Gaming #GamingTips #Shorts #LateGaming"
    )
    (OUT / "metadata.json").write_text(json.dumps({
        "title": title, "description": description,
        "tags": ["Gaming", "GamingTips", "Shorts", "LateGaming"],
        "language": "en", "date": str(day)
    }, indent=2), encoding="utf-8")
    (OUT / "narration.txt").write_text(narration, encoding="utf-8")

    import asyncio
    voice = OUT / "voice.mp3"
    asyncio.run(make_voice(narration, voice))

    slides = [
        ("THE HOOK", topic["hook"]),
        ("THE TIP", topic["body"][:155]),
        ("REMEMBER THIS", topic["takeaway"]),
    ]
    slide_paths = []
    seed = day.toordinal()
    for i, (label, text) in enumerate(slides):
        p = OUT / f"slide_{i+1}.png"
        draw_slide(i, label, text, p, seed)
        slide_paths.append(p)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(voice)],
        check=True, capture_output=True, text=True
    )
    duration = max(12.0, float(probe.stdout.strip()) + 0.5)
    per_slide = duration / len(slide_paths)
    concat = OUT / "slides.txt"
    with open(concat, "w", encoding="utf-8") as f:
        for p in slide_paths:
            f.write(f"file '{p.name}'\n")
            f.write(f"duration {per_slide:.3f}\n")
        f.write(f"file '{slide_paths[-1].name}'\n")

    video = OUT / "LATE_Gaming_Short.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-i", str(voice), "-vf", f"scale={W}:{H},format=yuv420p",
        "-r", str(FPS), "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "25", "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart", str(video)
    ])
    print(f"SUCCESS: created {video}")
    print(f"Duration target: {duration:.1f}s")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
