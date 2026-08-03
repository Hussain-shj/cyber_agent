"""
image_generator.py
يولّد تصاميم صور (1080x1350) بهوية بصرية سيبرانية (Modern Minimal) بدون أشخاص:
شبكات، خطوط رقمية، أقفال، دروع، خوادم - وفق نظام ألوان محدد.
يدعم النص العربي عبر إعادة التشكيل (reshaping) واتجاه RTL.
"""

import math
import os
import random

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT = 1080, 1350
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
FONT_BOLD = os.path.join(FONT_DIR, "NotoSansArabic-Bold.ttf")
FONT_REGULAR = os.path.join(FONT_DIR, "NotoSansArabic-Regular.ttf")

# لوحة الألوان الرسمية للهوية البصرية
COLORS = {
    "black": (10, 12, 16),
    "dark_blue": (13, 27, 51),
    "cyber_blue": (16, 43, 89),
    "dark_gray": (30, 34, 40),
    "cyan": (56, 226, 235),        # Cyber Cyan
    "cyan_soft": (56, 226, 235, 60),
    "white": (240, 244, 248),
    "red_alert": (214, 40, 40),
}


def _ar(text: str) -> str:
    """تجهيز نص عربي للعرض الصحيح (تشكيل + اتجاه) داخل Pillow."""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _wrap_arabic(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """يقسّم النص العربي إلى أسطر تناسب العرض المتاح (يعمل على النص الأصلي قبل reshape)."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        w = draw.textlength(_ar(trial), font=font)
        if w <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_multiline_centered(draw, lines, font, fill, center_x, start_y, line_height):
    y = start_y
    for line in lines:
        rendered = _ar(line)
        w = draw.textlength(rendered, font=font)
        draw.text((center_x - w / 2, y), rendered, font=font, fill=fill)
        y += line_height
    return y


def _grid_background(draw, base_color, line_color, spacing=54, alpha=26):
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    col = line_color + (alpha,)
    for x in range(0, WIDTH, spacing):
        od.line([(x, 0), (x, HEIGHT)], fill=col, width=1)
    for y in range(0, HEIGHT, spacing):
        od.line([(0, y), (WIDTH, y)], fill=col, width=1)
    return overlay


def _digital_lines(draw_layer, color, count=10, seed=1):
    rnd = random.Random(seed)
    for _ in range(count):
        y = rnd.randint(0, HEIGHT)
        x1 = rnd.randint(-100, WIDTH // 2)
        length = rnd.randint(150, 500)
        width = rnd.choice([1, 1, 2, 3])
        alpha = rnd.randint(25, 90)
        draw_layer.line([(x1, y), (x1 + length, y)], fill=color + (alpha,), width=width)


def _shield_icon(draw, cx, cy, size, color, width=6):
    """درع مبسّط برسم خطي (outline) بدون أي عناصر بشرية."""
    pts = [
        (cx, cy - size),
        (cx + size * 0.8, cy - size * 0.55),
        (cx + size * 0.8, cy + size * 0.25),
        (cx, cy + size * 1.05),
        (cx - size * 0.8, cy + size * 0.25),
        (cx - size * 0.8, cy - size * 0.55),
    ]
    draw.line(pts + [pts[0]], fill=color, width=width, joint="curve")
    # علامة قفل داخل الدرع
    lock_w, lock_h = size * 0.5, size * 0.4
    draw.rounded_rectangle(
        [cx - lock_w / 2, cy - lock_h / 4, cx + lock_w / 2, cy + lock_h * 0.9],
        radius=8, outline=color, width=width - 2,
    )
    draw.arc(
        [cx - lock_w * 0.32, cy - lock_h * 0.85, cx + lock_w * 0.32, cy - lock_h * 0.05],
        start=180, end=360, fill=color, width=width - 2,
    )


def _lock_icon(draw, cx, cy, size, color, width=6):
    body_w, body_h = size, size * 0.75
    draw.rounded_rectangle(
        [cx - body_w / 2, cy - body_h / 4, cx + body_w / 2, cy + body_h * 0.9],
        radius=10, outline=color, width=width,
    )
    draw.arc(
        [cx - body_w * 0.32, cy - body_h * 1.05, cx + body_w * 0.32, cy - body_h * 0.05],
        start=180, end=360, fill=color, width=width,
    )
    draw.ellipse([cx - 6, cy + body_h * 0.15, cx + 6, cy + body_h * 0.35], fill=color)


def _network_nodes(draw, color, count=8, seed=2, region=None):
    rnd = random.Random(seed)
    if region is None:
        region = (60, HEIGHT - 260, WIDTH - 60, HEIGHT - 60)
    x0, y0, x1, y1 = region
    points = [(rnd.randint(x0, x1), rnd.randint(y0, y1)) for _ in range(count)]
    for i, p in enumerate(points):
        for q in points[i + 1:]:
            if math.dist(p, q) < 220:
                draw.line([p, q], fill=color + (70,), width=1)
    for p in points:
        r = rnd.randint(3, 6)
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)


def _base_canvas(bg_top, bg_bottom):
    img = Image.new("RGB", (WIDTH, HEIGHT), bg_top)
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(bg_top[0] * (1 - ratio) + bg_bottom[0] * ratio)
        g = int(bg_top[1] * (1 - ratio) + bg_bottom[1] * ratio)
        b = int(bg_top[2] * (1 - ratio) + bg_bottom[2] * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
    return img, draw


def _footer_brand(draw, brand_name="Cyber Watch | الإمارات"):
    font = _font(FONT_REGULAR, 26)
    text = _ar(brand_name)
    w = draw.textlength(text, font=font)
    draw.text((WIDTH - w - 50, HEIGHT - 60), text, font=font, fill=COLORS["cyan"])


def design_standard(title: str, tag: str, urgent: bool = False) -> Image.Image:
    """تصميم 1: خلفية متدرجة + شبكة رقمية + درع مركزي + عنوان علوي."""
    top = COLORS["black"]
    bottom = COLORS["dark_blue"]
    img, draw = _base_canvas(top, bottom)

    grid = _grid_background(draw, top, COLORS["cyber_blue"])
    img.paste(Image.alpha_composite(img.convert("RGBA"), grid).convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(img)

    lines_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines_layer)
    _digital_lines(ld, COLORS["cyan"], count=14, seed=7)
    img = Image.alpha_composite(img.convert("RGBA"), lines_layer).convert("RGB")
    draw = ImageDraw.Draw(img)

    # شريط الوسم العلوي (Tag)
    tag_color = COLORS["red_alert"] if urgent else COLORS["cyan"]
    tag_font = _font(FONT_BOLD, 34)
    tag_text = _ar(tag)
    tw = draw.textlength(tag_text, font=tag_font)
    pad = 30
    draw.rounded_rectangle(
        [WIDTH / 2 - tw / 2 - pad, 90, WIDTH / 2 + tw / 2 + pad, 90 + 64],
        radius=32, fill=tag_color,
    )
    draw.text((WIDTH / 2 - tw / 2, 106), tag_text, font=tag_font, fill=COLORS["black"])

    # الدرع المركزي
    _shield_icon(draw, WIDTH / 2, 480, 140, COLORS["cyan"], width=8)

    # العنوان
    title_font = _font(FONT_BOLD, 66)
    wrapped = _wrap_arabic(draw, title, title_font, WIDTH - 160)
    _draw_multiline_centered(draw, wrapped, title_font, COLORS["white"], WIDTH / 2, 720, 84)

    # خط فاصل فيروزي
    draw.rectangle([WIDTH / 2 - 90, 660, WIDTH / 2 + 90, 664], fill=COLORS["cyan"])

    _network_nodes(draw, COLORS["cyan"], count=10, seed=3)
    _footer_brand(draw)
    return img


def design_alert(title: str, tag: str) -> Image.Image:
    """تصميم 2: نمط تحذير عاجل (أحمر/أسود) لثغرات نشطة الاستغلال."""
    top = COLORS["black"]
    bottom = (30, 10, 10)
    img, draw = _base_canvas(top, bottom)

    lines_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines_layer)
    _digital_lines(ld, COLORS["red_alert"], count=16, seed=11)
    img = Image.alpha_composite(img.convert("RGBA"), lines_layer).convert("RGB")
    draw = ImageDraw.Draw(img)

    # شارة تحذير مثلثة مبسطة (بدون أي أشخاص)
    cx, cy, s = WIDTH / 2, 430, 130
    draw.polygon(
        [(cx, cy - s), (cx - s * 0.95, cy + s * 0.75), (cx + s * 0.95, cy + s * 0.75)],
        outline=COLORS["red_alert"], width=8,
    )
    excl_font = _font(FONT_BOLD, 130)
    draw.text((cx - 18, cy - 55), "!", font=excl_font, fill=COLORS["red_alert"])

    tag_font = _font(FONT_BOLD, 34)
    tag_text = _ar(tag)
    tw = draw.textlength(tag_text, font=tag_font)
    draw.rounded_rectangle(
        [WIDTH / 2 - tw / 2 - 30, 90, WIDTH / 2 + tw / 2 + 30, 154],
        radius=32, fill=COLORS["red_alert"],
    )
    draw.text((WIDTH / 2 - tw / 2, 106), tag_text, font=tag_font, fill=COLORS["white"])

    title_font = _font(FONT_BOLD, 68)
    wrapped = _wrap_arabic(draw, title, title_font, WIDTH - 140)
    _draw_multiline_centered(draw, wrapped, title_font, COLORS["white"], WIDTH / 2, 700, 86)

    draw.rectangle([WIDTH / 2 - 90, 660, WIDTH / 2 + 90, 664], fill=COLORS["red_alert"])

    _network_nodes(draw, COLORS["red_alert"], count=8, seed=4)
    _footer_brand(draw, "Cyber Watch | تحذير عاجل")
    return img


def design_minimal_dark(title: str, tag: str, urgent: bool = False) -> Image.Image:
    """تصميم 3: بساطة أكبر - خلفية رمادية داكنة + قفل جانبي + خط شبكي رفيع أسفل."""
    top = COLORS["dark_gray"]
    bottom = COLORS["black"]
    img, draw = _base_canvas(top, bottom)

    grid = _grid_background(draw, top, COLORS["cyan"], spacing=70, alpha=14)
    img = Image.alpha_composite(img.convert("RGBA"), grid).convert("RGB")
    draw = ImageDraw.Draw(img)

    accent = COLORS["red_alert"] if urgent else COLORS["cyan"]

    # شريط جانبي فيروزي
    draw.rectangle([0, 0, 14, HEIGHT], fill=accent)

    tag_font = _font(FONT_BOLD, 32)
    tag_text = _ar(tag)
    tw = draw.textlength(tag_text, font=tag_font)
    draw.text((WIDTH - tw - 60, 90), tag_text, font=tag_font, fill=accent)

    _lock_icon(draw, WIDTH - 140, 320, 120, accent, width=8)

    title_font = _font(FONT_BOLD, 70)
    wrapped = _wrap_arabic(draw, title, title_font, WIDTH - 200)
    _draw_multiline_centered(draw, wrapped, title_font, COLORS["white"], WIDTH / 2, 620, 88)

    draw.rectangle([WIDTH / 2 - 100, HEIGHT - 470, WIDTH / 2 + 100, HEIGHT - 466], fill=accent)

    _network_nodes(draw, accent, count=9, seed=6, region=(60, HEIGHT - 300, WIDTH - 60, HEIGHT - 100))
    _footer_brand(draw)
    return img


def generate_designs(content: dict, out_dir: str) -> list[str]:
    """يولّد 3 تصاميم بناءً على المحتوى ويحفظها كـ PNG، ويعيد قائمة المسارات."""
    os.makedirs(out_dir, exist_ok=True)
    title = content["image_title"]
    tag = content["classification"]
    urgent = content.get("urgency") == "عاجل"

    paths = []
    designs = [
        ("design_1_standard", design_standard(title, tag, urgent)),
        ("design_2_alert" if urgent else "design_2_minimal", (
            design_alert(title, tag) if urgent else design_minimal_dark(title, tag, urgent)
        )),
        ("design_3_minimal", design_minimal_dark(title, tag, urgent)),
    ]
    for name, img in designs:
        path = os.path.join(out_dir, f"{name}.png")
        img.save(path, "PNG", optimize=True)
        paths.append(path)
    return paths


if __name__ == "__main__":
    demo = {
        "image_title": "ثغرة خطيرة في Cisco SD-WAN",
        "classification": "تحذير عاجل",
        "urgency": "عاجل",
    }
    out = generate_designs(demo, "/tmp/cyber_demo")
    print(out)
