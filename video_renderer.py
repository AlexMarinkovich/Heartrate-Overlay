import av
import os
import math
import numpy as np
import pandas as pd
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# CONFIG
# ============================================================
FPS = 30
WIDTH, HEIGHT = 260, 120

PIXEL_FORMAT = "yuva444p10le"
PRORES_PROFILE = "4444"
PRORES_QSCALE = "9"

BG_COLOR = (30, 30, 30)
BG_ALPHA = 200

FONT_SIZE = 70
TEXT_ANCHOR = "lm"
TEXT_X_OFFSET = 38

HEART_SIZE = 50
HEART_X_CENTER = 40

LINE_COLOR = (255, 255, 255)
LINE_WIDTH = 10
PADDING = 10
SLANT = 40

BEAT_SCALE = 0.28
HR_SMOOTHING = 0.15

LUB_RISE_END = 0.14
LUB_DECAY_END = 0.32
LUB_DECAY_STRENGTH = 9.0

DUB_START = 0.36
DUB_DURATION = 0.10

HR_RATE_MULTIPLIER = 1.5
MIN_HR = 40

FONT_PATH = "heartrate_overlay/assets/Fredoka-Bold.ttf"
HEART_IMAGE_PATH = "heartrate_overlay/assets/heart.png"


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================
def render_video(input_csv: str) -> str:
    input_csv = Path(input_csv)

    output_dir = Path("heartrate_overlay/videos")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{input_csv.stem}.mov"

    # ========================================================
    # LOAD DATA
    # ========================================================
    df = pd.read_csv(input_csv)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    duration_seconds = len(df)
    total_frames = int(duration_seconds * FPS)
    dt = 1.0 / FPS

    heart_img = Image.open(HEART_IMAGE_PATH).convert("RGBA")
    heart_img = heart_img.resize((HEART_SIZE, HEART_SIZE), Image.LANCZOS)

    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    # ========================================================
    # HELPERS
    # ========================================================
    def get_hr_at_time(t):
        index = min(int(t), len(df) - 1)
        return max(MIN_HR, int(df["heart_rate"].iloc[index]))

    def hr_to_color(hr):
        if hr <= 79:
            return (93, 251, 8)
        if hr <= 89:
            return (250, 186, 9)
        return (249, 35, 4)

    def draw_rounded_line(draw, p1, p2, width, color):
        draw.line([p1, p2], fill=color, width=width)
        radius = width // 2 - 1
        for x, y in (p1, p2):
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=color
            )

    # ========================================================
    # TRAPEZOID MASK
    # ========================================================
    def create_trapezoid_mask():
        mask = Image.new("L", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(mask)

        top = PADDING - (LINE_WIDTH // 2)
        bottom = HEIGHT - PADDING + (LINE_WIDTH // 2)
        right = WIDTH - PADDING

        polygon = [
            (0, top),
            (right, top),
            (right - SLANT, bottom),
            (0, bottom)
        ]

        draw.polygon(polygon, fill=255)
        return mask

    trapezoid_mask = create_trapezoid_mask()

    # ========================================================
    # HEARTBEAT ENGINE (STATEFUL)
    # ========================================================
    smoothed_hr = None
    beat_phase = 0.0

    def heartbeat_scale(dt, target_hr):
        nonlocal smoothed_hr, beat_phase

        if smoothed_hr is None:
            smoothed_hr = target_hr
        else:
            smoothed_hr += (target_hr - smoothed_hr) * HR_SMOOTHING

        seconds_per_beat = 60.0 / (smoothed_hr * HR_RATE_MULTIPLIER)
        beat_phase = (beat_phase + dt / seconds_per_beat) % 1.0

        pulse = 0.0

        if beat_phase < LUB_RISE_END:
            x = beat_phase / LUB_RISE_END
            pulse += math.sin(x * math.pi * 0.5)

        elif beat_phase < LUB_DECAY_END:
            x = (beat_phase - LUB_RISE_END) / (LUB_DECAY_END - LUB_RISE_END)
            pulse += math.exp(-LUB_DECAY_STRENGTH * x)

        if DUB_START <= beat_phase < DUB_START + DUB_DURATION:
            x = (beat_phase - DUB_START) / DUB_DURATION
            pulse += math.sin(x * math.pi)

        return 1.0 + BEAT_SCALE * pulse

    # ========================================================
    # FRAME RENDER
    # ========================================================
    def make_frame(t):
        hr = get_hr_at_time(t)
        text_color = hr_to_color(hr)

        base = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

        bg = Image.new("RGBA", (WIDTH, HEIGHT), BG_COLOR + (0,))
        alpha = trapezoid_mask.point(lambda a: a * BG_ALPHA // 255)
        bg.putalpha(alpha)

        img = Image.alpha_composite(base, bg)
        draw = ImageDraw.Draw(img)

        scale = heartbeat_scale(dt, hr)
        size = int(HEART_SIZE * scale)
        heart = heart_img.resize((size, size), Image.LANCZOS)

        hx = HEART_X_CENTER - size // 2
        hy = (HEIGHT - size) // 2
        img.paste(heart, (hx, hy), heart)

        draw.text(
            (HEART_SIZE + TEXT_X_OFFSET, HEIGHT // 2),
            str(hr),
            font=font,
            fill=text_color,
            anchor=TEXT_ANCHOR
        )

        top = PADDING - (LINE_WIDTH // 2)
        bottom = HEIGHT - PADDING + (LINE_WIDTH // 2)
        right = WIDTH - PADDING

        draw_rounded_line(draw, (0, top), (right, top), LINE_WIDTH, LINE_COLOR)
        draw_rounded_line(draw, (right, top), (right - SLANT, bottom), LINE_WIDTH, LINE_COLOR)
        draw_rounded_line(draw, (0, bottom), (right - SLANT, bottom), LINE_WIDTH, LINE_COLOR)

        return np.asarray(img, dtype=np.uint8)

    # ========================================================
    # ENCODE
    # ========================================================
    container = av.open(str(output_file), "w")

    stream = container.add_stream("prores_ks", rate=FPS)
    stream.width = WIDTH
    stream.height = HEIGHT
    stream.pix_fmt = PIXEL_FORMAT
    stream.options = {
        "profile": PRORES_PROFILE,
        "qscale": PRORES_QSCALE
    }

    for i in range(total_frames):
        frame = make_frame(i * dt)
        video_frame = av.VideoFrame.from_ndarray(frame, format="rgba")
        video_frame = video_frame.reformat(
            width=WIDTH,
            height=HEIGHT,
            format=PIXEL_FORMAT
        )

        for packet in stream.encode(video_frame):
            container.mux(packet)

    for packet in stream.encode():
        container.mux(packet)

    container.close()

    return str(output_file)
