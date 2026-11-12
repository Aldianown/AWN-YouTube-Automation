import asyncio
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import edge_tts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
TOPICS = ROOT / "content" / "topics.json"

W, H = 1080, 1920
FPS = 30
MAX_SLIDES = 5          # hook + up to 3 body chunks + takeaway
MAX_BODY_CHARS = 180    # per body slide, split at sentence boundary


# ---------- Fonts ----------
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ---------- Text helpers ----------
def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int) -> list[str]:
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


def truncate_words(text: str, max_len: int) -> str:
    """Truncate at a word boundary with an ellipsis, never mid-word."""
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    cut = cut[: cut.rfind(" ")].rstrip(" ,.;:")
    return cut + "…"


def split_into_chunks(text: str, max_chars: int) -> list[str]:
    """Split text into chunks at sentence boundaries, each <= max_chars."""
    sentences = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in ".!?":
            sentences.append(buf.strip())
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())

    chunks, current = [], ""
    for s in sentences:
        candidate = (current + " " + s).strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = s
    if current:
        chunks.append(current)

    # If a single sentence is too long, hard-split at word boundaries.
    final = []
    for c in chunks:
        while len(c) > max_chars:
            cut = c[:max_chars]
            cut = cut[: cut.rfind(" ")]
            final.append(cut.strip())
            c = c[len(cut):].strip()
        if c:
            final.append(c)
    return final


# ---------- Slide drawing ----------
def build_gradient(top: tuple, bottom: tuple) -> Image.Image:
    """Vectorised vertical gradient (fast)."""
    top_arr = np.array(top, dtype=np.float32)
    bottom_arr = np.array(bottom, dtype=np.float32)
    grad = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None, None]  # (H,1,1)
    arr = top_arr * (1 - grad) + bottom_arr * grad                    # (H,1,3)
    arr = np.repeat(arr, W, axis=1).astype(np.uint8)                  # (H,W,3)
    return Image.fromarray(arr, "RGB")


def draw_slide(index: int, label: str, text: str, out_path: Path, seed: int) -> None:
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

    # Original abstract neon rings and bars; no third-party game assets.
    for _ in range(18):
        x, y = rng.randint(-200, W + 200), rng.randint(-100, H + 100)
        r = rng.randint(40, 260)
        d.ellipse((x - r, y - r, x + r, y + r),
                  outline=(*accent, rng.randint(12, 42)),
                  width=rng.randint(2, 8))
    for _ in range(22):
        y = rng.randint(0, H)
        d.line((0, y, W, y - rng.randint(-80, 80)), fill=(*accent, 18), width=2)

    d.rounded_rectangle((62, 120, W - 62, H - 120), radius=42,
                        outline=(*accent, 150), width=4)

    d.text((95, 185), "LATE GAMING", font=font(48, True), fill=(245, 248, 255, 255))
    d.text((95, 270), label.upper(), font=font(31, True), fill=(*accent, 255))

    # Auto-fit body text: start big, shrink if it overflows.
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
        d.text((95, y), line, font=fnt, fill=(255, 255, 255, 255),
               stroke_width=1, stroke_fill=(0, 0, 0, 90))
        y += line_h

    d.rounded_rectangle((95, H - 310, W - 95, H - 220), radius=24,
                        fill=(*accent, 38), outline=(*accent, 180), width=2)
    d.text((125, H - 292), "FOLLOW FOR MORE GAMING TIPS",
           font=font(28, True), fill=(255, 255, 255, 255))

    img.save(out_path, quality=95)


# ---------- TTS ----------
async def make_voice(text: str, path: Path) -> None:
    communicate = edge_tts.Communicate(
        text, voice="en-US-GuyNeural", rate="+2%"
    )
    await communicate.save(str(path))


# ---------- FFmpeg helper ----------
def run(cmd: list) -> None:
    print("RUN:", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with open(TOPICS, "r", encoding="utf-8") as f:
        topics = json.load(f)
    if not topics:
        raise RuntimeError("content/topics.json is empty")

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
        "title": title,
        "description": description,
        "tags": ["Gaming", "GamingTips", "Shorts", "LateGaming"],
        "language": "en",
        "date": str(day),
    }, indent=2), encoding="utf-8")
    (OUT / "narration.txt").write_text(narration, encoding="utf-8")

    # --- Voice ---
    voice = OUT / "voice.mp3"
    asyncio.run(make_voice(narration, voice))
    if not voice.exists() or voice.stat().st_size < 1024:
        raise RuntimeError("TTS output missing or too small")

    # --- Probe duration ---
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(voice)],
        check=True, capture_output=True, text=True,
    )
    try:
        audio_duration = float(probe.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"Invalid audio duration: {probe.stdout!r}") from exc
    if audio_duration <= 0:
        raise RuntimeError("Audio duration is zero")
    duration = max(12.0, audio_duration + 0.5)

    # --- Build slides ---
    slide_specs: list[tuple[str, str]] = [("THE HOOK", topic["hook"])]
    body_chunks = split_into_chunks(topic["body"], MAX_BODY_CHARS)
    # Limit total slides so timing stays reasonable.
    available_for_body = max(1, MAX_SLIDES - 2)
    body_chunks = body_chunks[:available_for_body]
    for i, chunk in enumerate(body_chunks):
        label = "THE TIP" if i == 0 else "MORE TIPS"
        slide_specs.append((label, chunk))
    slide_specs.append(("REMEMBER THIS", topic["takeaway"]))

    slide_paths: list[Path] = []
    seed = day.toordinal()
    for i, (label, text) in enumerate(slide_specs):
        p = OUT / f"slide_{i + 1}.png"
        draw_slide(i, label, text, p, seed)
        slide_paths.append(p)

    # --- Concat file with per-slide durations ---
    per_slide = duration / len(slide_paths)
    concat = OUT / "slides.txt"
    with open(concat, "w", encoding="utf-8") as f:
        for p in slide_paths:
            f.write(f"file '{p.name}'\n")
            f.write(f"duration {per_slide:.3f}\n")
        f.write(f"file '{slide_paths[-1].name}'\n")

    # --- Render ---
    video = OUT / "LATE_Gaming_Short.mp4"
    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-i", str(voice),
        "-vf", f"scale={W}:{H},format=yuv420p",
        "-r", str(FPS),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart",
        str(video),
    ])

    if not video.exists() or video.stat().st_size < 10_000:
        raise RuntimeError("Rendered video is missing or too small")

    print(f"SUCCESS: created {video}")
    print(f"Slides: {len(slide_paths)}  Duration: {duration:.1f}s")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise