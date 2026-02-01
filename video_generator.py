import av
import math
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# FILES
# ============================================================
CSV_FILE = "logs/2026-01-30 13-27-11.csv"
OUTPUT_FILE = "heart_rate.mov"

FONT_PATH = "assets/Fredoka-Bold.ttf"
HEART_IMAGE_PATH = "assets/heart.png"

# ============================================================
# VIDEO
# ============================================================
FPS = 30
WIDTH, HEIGHT = 260, 120

PIXEL_FORMAT = "yuva444p10le"
PRORES_PROFILE = "4444"
PRORES_QSCALE = "9"

# ============================================================
# BACKGROUND
# ============================================================
BG_COLOR = (30, 30, 30)
BG_ALPHA = 200

# ============================================================
# TEXT
# ============================================================
FONT_SIZE = 70
TEXT_ANCHOR = "lm"
TEXT_X_OFFSET = 38

# ============================================================
# HEART ICON
# ============================================================
HEART_SIZE = 50
HEART_X_CENTER = 40

# ============================================================
# FRAME OUTLINE
# ============================================================
LINE_COLOR = (255, 255, 255)
LINE_WIDTH = 10
PADDING = 10
SLANT = 40

# ============================================================
# HEARTBEAT ANIMATION
# ============================================================
BEAT_SCALE = 0.28
HR_SMOOTHING = 0.15

# Beat shape
LUB_RISE_END = 0.14
LUB_DECAY_END = 0.32
LUB_DECAY_STRENGTH = 9.0

DUB_START = 0.36
DUB_DURATION = 0.10

HR_RATE_MULTIPLIER = 1.5
MIN_HR = 40

# ============================================================
# LOAD DATA
# ============================================================
df = pd.read_csv(CSV_FILE)
df["timestamp"] = pd.to_datetime(df["timestamp"])

DURATION_SECONDS = len(df)
TOTAL_FRAMES = int(DURATION_SECONDS * FPS)
DT = 1.0 / FPS

heart_img = Image.open(HEART_IMAGE_PATH).convert("RGBA")
heart_img = heart_img.resize((HEART_SIZE, HEART_SIZE), Image.LANCZOS)

font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

# ============================================================
# HELPERS
# ============================================================
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

# ============================================================
# TRAPEZOID MASK (STATIC)
# ============================================================
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


TRAPEZOID_MASK = create_trapezoid_mask()

# ============================================================
# HEARTBEAT ENGINE (STATEFUL)
# ============================================================
smoothed_hr = None
beat_phase = 0.0

def heartbeat_scale(dt, target_hr):
    global smoothed_hr, beat_phase

    if smoothed_hr is None:
        smoothed_hr = target_hr
    else:
        smoothed_hr += (target_hr - smoothed_hr) * HR_SMOOTHING

    seconds_per_beat = 60.0 / (smoothed_hr * HR_RATE_MULTIPLIER)
    beat_phase = (beat_phase + dt / seconds_per_beat) % 1.0

    pulse = 0.0

    # --- LUB ---
    if beat_phase < LUB_RISE_END:
        x = beat_phase / LUB_RISE_END
        pulse += math.sin(x * math.pi * 0.5)

    elif beat_phase < LUB_DECAY_END:
        x = (beat_phase - LUB_RISE_END) / (LUB_DECAY_END - LUB_RISE_END)
        pulse += math.exp(-LUB_DECAY_STRENGTH * x)

    # --- DUB ---
    if DUB_START <= beat_phase < DUB_START + DUB_DURATION:
        x = (beat_phase - DUB_START) / DUB_DURATION
        pulse += math.sin(x * math.pi)

    return 1.0 + BEAT_SCALE * pulse

# ============================================================
# FRAME RENDER
# ============================================================
def make_frame(t):
    hr = get_hr_at_time(t)
    text_color = hr_to_color(hr)

    base = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    bg = Image.new("RGBA", (WIDTH, HEIGHT), BG_COLOR + (0,))
    alpha = TRAPEZOID_MASK.point(lambda a: a * BG_ALPHA // 255)
    bg.putalpha(alpha)

    img = Image.alpha_composite(base, bg)
    draw = ImageDraw.Draw(img)

    # Heart
    scale = heartbeat_scale(DT, hr)
    size = int(HEART_SIZE * scale)
    heart = heart_img.resize((size, size), Image.LANCZOS)

    hx = HEART_X_CENTER - size // 2
    hy = (HEIGHT - size) // 2
    img.paste(heart, (hx, hy), heart)

    # Text
    draw.text(
        (HEART_SIZE + TEXT_X_OFFSET, HEIGHT // 2),
        str(hr),
        font=font,
        fill=text_color,
        anchor=TEXT_ANCHOR
    )

    # Frame outline
    top = PADDING - (LINE_WIDTH // 2)
    bottom = HEIGHT - PADDING + (LINE_WIDTH // 2)
    right = WIDTH - PADDING

    draw_rounded_line(draw, (0, top), (right, top), LINE_WIDTH, LINE_COLOR)
    draw_rounded_line(draw, (right, top), (right - SLANT, bottom), LINE_WIDTH, LINE_COLOR)
    draw_rounded_line(draw, (0, bottom), (right - SLANT, bottom), LINE_WIDTH, LINE_COLOR)

    return np.asarray(img, dtype=np.uint8)

# ============================================================
# ENCODE (PRORES 4444)
# ============================================================
container = av.open(OUTPUT_FILE, "w")

stream = container.add_stream("prores_ks", rate=FPS)
stream.width = WIDTH
stream.height = HEIGHT
stream.pix_fmt = PIXEL_FORMAT
stream.options = {
    "profile": PRORES_PROFILE,
    "qscale": PRORES_QSCALE
}

for i in range(TOTAL_FRAMES):
    frame = make_frame(i * DT)
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
print("Render complete:", OUTPUT_FILE)
