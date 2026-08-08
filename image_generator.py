"""
image_generator.py
يولّد تصاميم صور (1080x1350) بهوية بصرية سيبرانية (Modern Minimal) بدون أشخاص:
شبكات، خطوط رقمية، أقفال، دروع، خوادم - وفق نظام ألوان محدد.
يدعم النص العربي عبر محرك RAQM المدمج في Pillow (HarfBuzz+FriBidi) للتشكيل
والاتجاه الصحيحين تلقائياً — بديل موثوق عن معالجة يدوية سابقة (reshape/bidi
يدوي) ثبت أنها تنتج نصاً مشوَّهاً بصرياً في حالات نصوص مختلطة (عربي+إنجليزي)
رغم اجتيازها فحوصاً برمجية على مستوى الرموز الفردية.
"""

import math
import os
import random
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

if not features.check("raqm"):
    raise RuntimeError(
        "محرك RAQM غير متوفر في نسخة Pillow المثبتة — هذا يعني أن النص العربي "
        "سيُعرض بشكل خاطئ (غير متصل الحروف). تأكد من تثبيت Pillow>=10.4.0 عبر "
        "pip (النسخ الحديثة تُضمِّن RAQM تلقائياً بدون أي إعداد إضافي على "
        "النظام)، ثم أعد المحاولة."
    )

WIDTH, HEIGHT = 1080, 1350
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
FONT_BOLD = os.path.join(FONT_DIR, "Cairo-Bold.ttf")
FONT_REGULAR = os.path.join(FONT_DIR, "Cairo-Regular.ttf")
FONT_SEMIBOLD = os.path.join(FONT_DIR, "Cairo-SemiBold.ttf")
# خط Cairo يغطي العربية واللاتينية أصلياً في ملف واحد.
FONT_LATIN_BOLD = FONT_BOLD

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


# محرك RAQM (HarfBuzz+FriBidi، مدمج في Pillow) يتولى تشكيل الحروف العربية
# واتجاه RTL تلقائياً وبشكل صحيح — بما في ذلك النصوص المختلطة (عربي+إنجليزي+
# أرقام) — دون أي حاجة لمعالجة يدوية (reshape/bidi/isolate) كانت هنا سابقاً.

def _ar(text: str) -> str:
    """تنظيف بسيط فقط؛ التشكيل والاتجاه يتوليّان تلقائياً عبر RAQM عند الرسم."""
    return text.strip()


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)


def _draw_mixed_line(draw, text: str, size: int, fill, x_left: float, y: float) -> float:
    """يرسم سطراً واحداً بمحاذاة يسارية عند x_left (عبر RAQM: anchor='la' مع
    direction='rtl' يضع الحافة اليسرى للنص المُشكَّل تلقائياً عند x_left، بينما
    محتوى RTL يُرسَم بصرياً بشكل صحيح داخلياً)، ويعيد العرض الكلي المرسوم."""
    font = _font(FONT_BOLD, size)
    draw.text((x_left, y), text, font=font, fill=fill, direction="rtl", anchor="la")
    bbox = draw.textbbox((0, 0), text, font=font, direction="rtl")
    return bbox[2] - bbox[0]


def _measure_mixed_line(draw, text: str, size: int) -> float:
    if not text:
        return 0.0
    font = _font(FONT_BOLD, size)
    bbox = draw.textbbox((0, 0), text, font=font, direction="rtl")
    return bbox[2] - bbox[0]


def _cap_lines(lines: list[str], max_lines: int) -> list[str]:
    """يحدّ عدد الأسطر بحد أقصى، ويضيف '…' لآخر سطر ظاهر إن جرى قصّ أسطر أخرى."""
    if len(lines) <= max_lines:
        return lines
    capped = lines[:max_lines]
    capped[-1] = capped[-1].rstrip() + " …"
    return capped


def _wrap_arabic(draw: ImageDraw.ImageDraw, text: str, size: int, max_width: int) -> list[str]:
    """يقسّم النص إلى أسطر تناسب العرض المتاح، بالاعتماد على قياس مختلط الخطوط
    (عربي + لاتيني احتياطي) لأن العناوين قد تتضمن أسماء منتجات إنجليزية."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        w = _measure_mixed_line(draw, _ar(trial), size)
        if w <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_multiline_centered(draw, lines, size, fill, center_x, start_y, line_height):
    y = start_y
    for line in lines:
        rendered = _ar(line)
        w = _measure_mixed_line(draw, rendered, size)
        _draw_mixed_line(draw, rendered, size, fill, center_x - w / 2, y)
        y += line_height
    return y


_ARABIC_MONTHS = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]


def _arabic_date(dt: datetime | None = None) -> str:
    """ينسّق التاريخ بالعربية بأرقام غربية (مدعومة بالكامل في الخط)، مثل: 3 أغسطس 2026."""
    dt = dt or datetime.now(timezone.utc)
    return f"{dt.day} {_ARABIC_MONTHS[dt.month - 1]} {dt.year}"


def _details_panel(img: Image.Image, details: str, box_top: float,
                    text_color=(225, 230, 236), max_lines: int = 4, canvas=None):
    """يرسم صندوق 'المختصر' (تفاصيل الصورة) بخلفية داكنة شفافة فوق أي خلفية،
    ويعيد (img, draw, box_bottom) الجديدين لمتابعة الرسم بعده. الخط أكبر
    والحد الأقصى للأسطر أعلى من السابق لتفادي قصّ الجملة في منتصف معناها —
    النص المصدر (image_summary) مصمَّم أصلاً ليكون جملة واحدة قصيرة كاملة
    المعنى، فزيادة الأسطر المسموحة هنا تحمي من القص دون تضخيم الصندوق فعلياً."""
    w, h = canvas or (WIDTH, HEIGHT)
    text_size = max(24, round(w * 0.032))
    line_h = round(text_size * 1.32)
    draw = ImageDraw.Draw(img)
    lines = _cap_lines(_wrap_arabic(draw, details, text_size, w - round(w * 0.148)), max_lines)
    box_h = round(w * 0.032) + line_h * len(lines)
    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    margin = round(w * 0.056)
    pd.rounded_rectangle([margin, box_top, w - margin, box_top + box_h], radius=round(w * 0.015), fill=(8, 11, 18, 175))
    img = Image.alpha_composite(img.convert("RGBA"), panel).convert("RGB")
    draw = ImageDraw.Draw(img)
    _draw_multiline_centered(draw, lines, text_size, text_color, w / 2, box_top + round(w * 0.016), line_h)
    return img, draw, box_top + box_h


def _tag_badge_with_date(draw, tag: str, urgent: bool, center_y: float, date_str: str = "", canvas=None):
    """يرسم وسم التصنيف (Tag) في منتصف عمودي محدد، مع تاريخ الخبر أسفله مباشرة."""
    w, _ = canvas or (WIDTH, HEIGHT)
    tag_color = COLORS["red_alert"] if urgent else COLORS["cyan"]
    tag_size = max(24, round(w * 0.0315))
    tag_font = _font(FONT_BOLD, tag_size)
    tag_text = _ar(tag)
    tw = draw.textlength(tag_text, font=tag_font)
    pad = round(w * 0.028)
    badge_h = round(tag_size * 1.85)
    badge_top = center_y - badge_h / 2
    draw.rounded_rectangle(
        [w / 2 - tw / 2 - pad, badge_top, w / 2 + tw / 2 + pad, badge_top + badge_h],
        radius=badge_h / 2, fill=tag_color,
    )
    draw.text((w / 2 - tw / 2, badge_top + badge_h * 0.24), tag_text, font=tag_font, fill=COLORS["black"])

    extra = 0
    if date_str:
        date_size = max(18, round(w * 0.0235))
        date_font = _font(FONT_REGULAR, date_size)
        date_text = _ar(date_str)
        dw = draw.textlength(date_text, font=date_font)
        dx = w / 2 - dw / 2
        dy = badge_top + badge_h + round(w * 0.012)
        chip_h = round(date_size * 1.5)
        draw.rounded_rectangle([dx - 12, dy - 5, dx + dw + 12, dy + chip_h], radius=9, fill=(6, 9, 14))
        draw.text((dx, dy), date_text, font=date_font, fill=(200, 208, 218))
        extra = chip_h + round(w * 0.012)
    return badge_top + badge_h + extra


def _grid_background(draw, base_color, line_color, spacing=54, alpha=26, canvas=None):
    w, h = canvas or (WIDTH, HEIGHT)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    col = line_color + (alpha,)
    for x in range(0, w, spacing):
        od.line([(x, 0), (x, h)], fill=col, width=1)
    for y in range(0, h, spacing):
        od.line([(0, y), (w, y)], fill=col, width=1)
    return overlay


def _digital_lines(draw_layer, color, count=10, seed=1, canvas=None):
    w, h = canvas or (WIDTH, HEIGHT)
    rnd = random.Random(seed)
    for _ in range(count):
        y = rnd.randint(0, h)
        x1 = rnd.randint(-100, w // 2)
        length = rnd.randint(round(w * 0.14), round(w * 0.46))
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


def _bug_icon(draw, cx, cy, size, color, width=6):
    """أيقونة حشرة (برمجية خبيثة / Malware): جسم بيضاوي + قرون استشعار + أرجل."""
    body_w, body_h = size * 0.62, size * 0.95
    draw.ellipse([cx - body_w / 2, cy - body_h / 2, cx + body_w / 2, cy + body_h / 2],
                 outline=color, width=width)
    draw.line([(cx, cy - body_h / 2), (cx, cy + body_h / 2)], fill=color, width=max(2, width - 3))
    # قرنا الاستشعار
    for side in (-1, 1):
        draw.line([(cx, cy - body_h * 0.42), (cx + side * size * 0.35, cy - body_h * 0.75)],
                   fill=color, width=max(2, width - 3))
    # الأرجل (3 على كل جانب)
    for i, ratio in enumerate((-0.28, 0, 0.32)):
        y = cy + body_h * ratio
        for side in (-1, 1):
            draw.line([(cx + side * body_w * 0.5, y), (cx + side * size * 0.58, y + size * 0.08 * (i - 1))],
                       fill=color, width=max(2, width - 3))


def _ransom_icon(draw, cx, cy, size, color, width=6):
    """أيقونة Ransomware: مستندات مكدّسة مقفلة (بيانات محتجزة مقابل فدية)."""
    doc_w, doc_h = size * 0.62, size * 0.8
    for dx, dy in ((-10, 10), (10, -6), (0, -18)):
        left = cx - doc_w / 2 + dx
        top = cy - doc_h / 2 + dy
        draw.rounded_rectangle([left, top, left + doc_w, top + doc_h], radius=6,
                                outline=color, width=max(2, width - 3))
    lock_size = size * 0.5
    _lock_icon(draw, cx, cy + size * 0.18, lock_size, color, width=width)


def _phishing_icon(draw, cx, cy, size, color, width=6):
    """أيقونة تصيّد احتيالي: مغلّف بريد إلكتروني + صنّارة صيد."""
    env_w, env_h = size * 1.1, size * 0.72
    left, top = cx - env_w / 2, cy - env_h / 2
    draw.rounded_rectangle([left, top, left + env_w, top + env_h], radius=8, outline=color, width=width)
    draw.line([(left, top), (cx, cy + env_h * 0.12), (left + env_w, top)], fill=color, width=max(2, width - 3), joint="curve")
    # صنارة الصيد داخلة من الأعلى
    hook_x = cx + env_w * 0.22
    draw.line([(hook_x, top - size * 0.4), (hook_x, cy - size * 0.02)], fill=color, width=max(2, width - 3))
    draw.arc([hook_x - 12, cy - size * 0.14, hook_x + 12, cy + size * 0.1], start=0, end=200,
              fill=color, width=max(2, width - 3))


def _leak_icon(draw, cx, cy, size, color, width=6):
    """أيقونة تسريب بيانات: أسطوانة قاعدة بيانات مع قطرة تسريب."""
    db_w, db_h = size * 0.85, size * 0.32
    top_y = cy - size * 0.5
    draw.ellipse([cx - db_w / 2, top_y, cx + db_w / 2, top_y + db_h], outline=color, width=width)
    draw.line([(cx - db_w / 2, top_y + db_h / 2), (cx - db_w / 2, top_y + size * 0.55)], fill=color, width=width)
    draw.line([(cx + db_w / 2, top_y + db_h / 2), (cx + db_w / 2, top_y + size * 0.55)], fill=color, width=width)
    draw.arc([cx - db_w / 2, top_y + size * 0.55 - db_h / 2, cx + db_w / 2, top_y + size * 0.55 + db_h / 2],
              start=0, end=180, fill=color, width=width)
    # قطرة تسريب أسفل القاعدة
    drop_cx, drop_top = cx, top_y + size * 0.62
    draw.polygon([
        (drop_cx, drop_top),
        (drop_cx - size * 0.13, drop_top + size * 0.28),
        (drop_cx + size * 0.13, drop_top + size * 0.28),
    ], outline=color, width=max(2, width - 3))
    draw.ellipse([drop_cx - size * 0.13, drop_top + size * 0.14, drop_cx + size * 0.13, drop_top + size * 0.4],
                 outline=color, width=max(2, width - 3))


def _update_icon(draw, cx, cy, size, color, width=6):
    """أيقونة تحديث أمني: درع مع سهم دائري (تحديث/ترقيع)."""
    _shield_icon(draw, cx, cy, size * 0.72, color, width=width)
    r = size * 0.42
    draw.arc([cx - r, cy - r - size * 0.1, cx + r, cy + r - size * 0.1], start=25, end=310,
              fill=color, width=max(3, width - 2))
    ax, ay = cx + r * 0.94, cy - r * 0.42
    draw.polygon([(ax - 12, ay - 4), (ax + 10, ay + 6), (ax - 6, ay + 16)], fill=color)


def _checklist_icon(draw, cx, cy, size, color, width=6):
    """أيقونة أفضل الممارسات: لوحة حافظة (Clipboard) مع علامات صح."""
    board_w, board_h = size * 0.78, size * 1.05
    left, top = cx - board_w / 2, cy - board_h / 2
    draw.rounded_rectangle([left, top, left + board_w, top + board_h], radius=10, outline=color, width=width)
    clip_w = board_w * 0.4
    draw.rounded_rectangle([cx - clip_w / 2, top - size * 0.08, cx + clip_w / 2, top + size * 0.1],
                            radius=6, outline=color, width=max(2, width - 3))
    for i, ratio in enumerate((0.28, 0.52, 0.76)):
        y = top + board_h * ratio
        x0 = left + board_w * 0.16
        draw.line([(x0, y), (x0 + board_w * 0.12, y + board_h * 0.06), (x0 + board_w * 0.32, y - board_h * 0.08)],
                  fill=color, width=max(2, width - 3), joint="curve")
        draw.line([(x0 + board_w * 0.42, y - board_h * 0.02), (left + board_w * 0.84, y - board_h * 0.02)],
                   fill=color, width=max(2, width - 4))


def _radar_icon(draw, cx, cy, size, color, width=6):
    """أيقونة تحليل هجوم: شاشة رادار/مسح دائري مع نقطة مرصودة."""
    r = size * 0.55
    for ratio in (1.0, 0.66, 0.33):
        rr = r * ratio
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=color, width=max(2, width - 3))
    draw.line([(cx, cy), (cx + r * 0.9, cy - r * 0.55)], fill=color, width=max(2, width - 2))
    # نقطة مرصودة
    px, py = cx - r * 0.4, cy + r * 0.3
    draw.ellipse([px - 7, py - 7, px + 7, py + 7], fill=color)


def _tool_icon(draw, cx, cy, size, color, width=6):
    """أيقونة أدوات جديدة: مفتاح ربط + ترس متقاطعان."""
    # الترس (دائرة مسننة مبسطة)
    r = size * 0.36
    gx, gy = cx - size * 0.12, cy - size * 0.12
    draw.ellipse([gx - r, gy - r, gx + r, gy + r], outline=color, width=width)
    draw.ellipse([gx - r * 0.35, gy - r * 0.35, gx + r * 0.35, gy + r * 0.35], outline=color, width=max(2, width - 3))
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1, y1 = gx + math.cos(rad) * r, gy + math.sin(rad) * r
        x2, y2 = gx + math.cos(rad) * (r + size * 0.13), gy + math.sin(rad) * (r + size * 0.13)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=max(3, width - 1))
    # مفتاح الربط
    wx1, wy1 = cx + size * 0.32, cy + size * 0.32
    wx2, wy2 = cx - size * 0.05, cy - size * 0.05
    draw.line([(wx1, wy1), (wx2, wy2)], fill=color, width=max(4, width))
    draw.arc([wx1 - 14, wy1 - 14, wx1 + 14, wy1 + 14], start=30, end=300, fill=color, width=max(3, width - 1))


def _report_icon(draw, cx, cy, size, color, width=6):
    """أيقونة تقرير استخباراتي: مستند مع خطوط نص وعدسة تكبير فوقه (تحليل/رصد)."""
    doc_w, doc_h = size * 0.68, size * 0.92
    left, top = cx - doc_w / 2 - size * 0.08, cy - doc_h / 2
    draw.rounded_rectangle([left, top, left + doc_w, top + doc_h], radius=8, outline=color, width=width)
    for ratio in (0.28, 0.46, 0.64):
        y = top + doc_h * ratio
        draw.line([(left + doc_w * 0.16, y), (left + doc_w * 0.84, y)], fill=color, width=max(2, width - 4))
    # عدسة تكبير
    lens_cx, lens_cy = cx + size * 0.28, cy + size * 0.22
    lens_r = size * 0.24
    draw.ellipse([lens_cx - lens_r, lens_cy - lens_r, lens_cx + lens_r, lens_cy + lens_r],
                 outline=color, width=max(3, width - 1))
    handle_dx = lens_r * 0.75
    draw.line([(lens_cx + handle_dx, lens_cy + handle_dx), (lens_cx + handle_dx + size * 0.18, lens_cy + handle_dx + size * 0.18)],
               fill=color, width=max(3, width - 1))


def _news_icon(draw, cx, cy, size, color, width=6):
    """أيقونة خبر سيبراني عام: جرس تنبيه مع موجات بث."""
    bell_w, bell_h = size * 0.62, size * 0.7
    top = cy - bell_h / 2
    draw.arc([cx - bell_w / 2, top, cx + bell_w / 2, top + bell_h], start=180, end=360,
              fill=color, width=width)
    draw.line([(cx - bell_w / 2, top + bell_h / 2), (cx - bell_w * 0.62, cy + bell_h * 0.42)], fill=color, width=width)
    draw.line([(cx + bell_w / 2, top + bell_h / 2), (cx + bell_w * 0.62, cy + bell_h * 0.42)], fill=color, width=width)
    draw.line([(cx - bell_w * 0.62, cy + bell_h * 0.42), (cx + bell_w * 0.62, cy + bell_h * 0.42)], fill=color, width=width)
    draw.ellipse([cx - 9, cy + bell_h * 0.42 + 6, cx + 9, cy + bell_h * 0.42 + 24], fill=color)
    # موجات بث
    for i, r in enumerate((0.75, 1.0)):
        rr = bell_w * r
        draw.arc([cx - rr, top - size * 0.25, cx + rr, top + size * 0.3], start=200, end=340,
                  fill=color, width=max(2, width - 3))


# خريطة ربط كل تصنيف بالأيقونة المناسبة له — هذا هو المكان الوحيد الذي يحتاج
# تعديلاً لإضافة "مهارة" (أيقونة) جديدة لتصنيف جديد مستقبلاً. راجع التعليمة
# التفصيلية أسفل الملف (CLASSIFICATION_ICONS) لمعرفة كيفية الإضافة.
CLASSIFICATION_ICONS = {
    "خبر سيبراني": _news_icon,
    "ثغرة أمنية": _shield_icon,
    "برمجية خبيثة": _bug_icon,
    "Ransomware": _ransom_icon,
    "حملة تصيد": _phishing_icon,
    "تسريب بيانات": _leak_icon,
    "تحديث أمني": _update_icon,
    "نصائح توعوية": _checklist_icon,
    "أفضل الممارسات": _checklist_icon,
    "تحليل هجوم": _radar_icon,
    "أدوات جديدة": _tool_icon,
    "تقرير استخباراتي": _report_icon,
    "تحذير عاجل": _shield_icon,
}


def _icon_for_classification(tag: str):
    """يعيد دالة الأيقونة المناسبة للتصنيف، أو الدرع كافتراضي إن كان التصنيف
    غير معروف (حماية من أي تصنيف جديد لم تُضَف له أيقونة بعد)."""
    return CLASSIFICATION_ICONS.get(tag, _shield_icon)


def _network_nodes(draw, color, count=8, seed=2, region=None, canvas=None):
    w, h = canvas or (WIDTH, HEIGHT)
    rnd = random.Random(seed)
    if region is None:
        region = (round(w * 0.056), h - round(h * 0.193), w - round(w * 0.056), h - round(h * 0.044))
    x0, y0, x1, y1 = region
    points = [(rnd.randint(x0, x1), rnd.randint(y0, y1)) for _ in range(count)]
    for i, p in enumerate(points):
        for q in points[i + 1:]:
            if math.dist(p, q) < w * 0.204:
                draw.line([p, q], fill=color + (70,), width=1)
    for p in points:
        r = rnd.randint(3, 6)
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)


def _base_canvas(bg_top, bg_bottom, canvas=None):
    w, h = canvas or (WIDTH, HEIGHT)
    img = Image.new("RGB", (w, h), bg_top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        ratio = y / h
        r = int(bg_top[0] * (1 - ratio) + bg_bottom[0] * ratio)
        g = int(bg_top[1] * (1 - ratio) + bg_bottom[1] * ratio)
        b = int(bg_top[2] * (1 - ratio) + bg_bottom[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img, draw


def _source_line(draw, source: str, canvas=None):
    """يعرض اسم المصدر فقط (بدون رابط) في أسفل الصورة، بخلفية داكنة صغيرة
    خلفه لضمان وضوحه فوق أي خلفية."""
    if not source:
        return
    cw, ch = canvas or (WIDTH, HEIGHT)
    text = _ar(f"المصدر: {source}")
    text_size = max(18, round(cw * 0.024))
    w = _measure_mixed_line(draw, text, text_size)
    x = cw - w - round(cw * 0.046)
    y = ch - round(ch * 0.044)
    draw.rounded_rectangle([x - 16, y - 8, x + w + 16, y + 34], radius=10, fill=(6, 9, 14))
    _draw_mixed_line(draw, text, text_size, COLORS["cyan"], x, y)


def _battery_icon(draw, cx, cy, size, color, width=6):
    """أيقونة بطارية تستنزف بسرعة: جسم البطارية + برق + سهم هابط."""
    body_w, body_h = size * 0.9, size * 1.5
    left, top = cx - body_w / 2, cy - body_h / 2
    right, bottom = cx + body_w / 2, cy + body_h / 2
    draw.rounded_rectangle([left, top, right, bottom], radius=10, outline=color, width=width)
    # طرف البطارية العلوي
    nub_w = body_w * 0.35
    draw.rectangle([cx - nub_w / 2, top - size * 0.16, cx + nub_w / 2, top], outline=color, width=width)
    # برق داخل البطارية
    bolt = [
        (cx + body_w * 0.12, top + body_h * 0.18),
        (cx - body_w * 0.10, cy + body_h * 0.02),
        (cx + body_w * 0.02, cy + body_h * 0.02),
        (cx - body_w * 0.12, bottom - body_h * 0.15),
        (cx + body_w * 0.14, cy - body_h * 0.05),
        (cx + body_w * 0.00, cy - body_h * 0.05),
    ]
    draw.polygon(bolt, fill=color)
    # سهم هابط بجانب البطارية (استنزاف سريع)
    ax = right + size * 0.55
    draw.line([(ax, top + size * 0.1), (ax, bottom - size * 0.35)], fill=color, width=width - 1)
    draw.polygon(
        [(ax - 14, bottom - size * 0.35), (ax + 14, bottom - size * 0.35), (ax, bottom - size * 0.1)],
        fill=color,
    )


def _heat_icon(draw, cx, cy, size, color, width=6):
    """أيقونة ميزان حرارة مع خطوط تعبّر عن الحرارة المرتفعة."""
    stem_w = size * 0.34
    top = cy - size * 1.1
    bottom = cy + size * 0.85
    draw.rounded_rectangle(
        [cx - stem_w / 2, top, cx + stem_w / 2, bottom - size * 0.2],
        radius=stem_w / 2, outline=color, width=width,
    )
    bulb_r = size * 0.42
    draw.ellipse([cx - bulb_r, bottom - bulb_r, cx + bulb_r, bottom + bulb_r], outline=color, width=width)
    draw.ellipse([cx - bulb_r * 0.45, bottom - bulb_r * 0.45, cx + bulb_r * 0.45, bottom + bulb_r * 0.45], fill=color)
    # خطوط حرارة متعرجة حول الميزان
    for dx, h in ((-size * 0.7, 0.55), (size * 0.7, 0.75)):
        x0 = cx + dx
        y0 = top + size * 0.1
        draw.line(
            [(x0, y0), (x0 + 10, y0 - 14), (x0 - 6, y0 - 28), (x0 + 12, y0 - 42)],
            fill=color, width=width - 3, joint="curve",
        )


def _eye_data_icon(draw, cx, cy, size, color, width=6):
    """أيقونة عين مع مؤشر بيانات صاعد (استهلاك بيانات/مراقبة غير معروفة)."""
    eye_w, eye_h = size * 1.5, size * 0.85
    draw.arc([cx - eye_w / 2, cy - eye_h / 2 - eye_h * 0.15, cx + eye_w / 2, cy + eye_h * 0.55],
              start=200, end=340, fill=color, width=width)
    draw.arc([cx - eye_w / 2, cy - eye_h * 0.55, cx + eye_w / 2, cy + eye_h / 2 + eye_h * 0.15],
              start=20, end=160, fill=color, width=width)
    pupil_r = size * 0.22
    draw.ellipse([cx - pupil_r, cy - pupil_r, cx + pupil_r, cy + pupil_r], outline=color, width=width - 2)
    draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=color)
    # مخطط بيانات صاعد أسفل العين
    base_y = cy + size * 0.95
    pts = [(-size * 0.7, 0.15), (-size * 0.35, 0.4), (0, 0.25), (size * 0.35, 0.7), (size * 0.7, 0.55)]
    line_pts = [(cx + dx, base_y - size * ratio) for dx, ratio in pts]
    draw.line(line_pts, fill=color, width=width - 2, joint="curve")
    # سهم صغير في نهاية المخطط
    lx, ly = line_pts[-1]
    draw.polygon([(lx - 12, ly + 10), (lx + 4, ly - 10), (lx + 14, ly + 4)], fill=color)


def _cracked_phone_icon(draw, cx, cy, w, h, color_left, color_right, seed=5):
    """رسم خطي لهاتف بشاشة متصدعة، بلونين متدرجين يميناً/يساراً لإيحاء بصري
    بانقسام الحالة (طبيعي مقابل مخترَق) - بدون أي عناصر بشرية أو صور فوتوغرافية."""
    left, top = cx - w / 2, cy - h / 2
    right, bottom = cx + w / 2, cy + h / 2

    # جسم الهاتف: نصفان بلونين مختلفين
    draw.rounded_rectangle([left, top, cx, bottom], radius=36, outline=color_left, width=7)
    draw.rounded_rectangle([cx, top, right, bottom], radius=36, outline=color_right, width=7)
    # تصحيح الحد المزدوج في المنتصف (نرسم خطاً عمودياً موحداً بدل الفاصل المزدوج)
    draw.line([(cx, top + 10), (cx, bottom - 10)], fill=color_right, width=1)

    # كاميرا أمامية بسيطة
    draw.ellipse([cx - 8, top + 24, cx + 8, top + 40], outline=(150, 160, 170), width=3)

    # خطوط تصدّع تنطلق من نقطة مركزية
    rnd = random.Random(seed)
    center = (cx, cy + h * 0.05)
    draw.ellipse([center[0] - 8, center[1] - 8, center[0] + 8, center[1] + 8], fill=(230, 235, 240))
    for _ in range(14):
        angle = rnd.uniform(0, 2 * math.pi)
        length = rnd.uniform(w * 0.15, w * 0.48)
        x2 = center[0] + math.cos(angle) * length
        y2 = center[1] + math.sin(angle) * length * 0.9
        col = color_left if x2 < cx else color_right
        draw.line([center, (x2, y2)], fill=col, width=2)
        # تفرعات صغيرة
        branch_angle = angle + rnd.uniform(-0.6, 0.6)
        bx = x2 + math.cos(branch_angle) * length * 0.35
        by = y2 + math.sin(branch_angle) * length * 0.35
        draw.line([(x2, y2), (bx, by)], fill=col, width=1)


def _glow_layer(base_size, draw_fn, color, blur=22):
    """يرسم شكلاً على طبقة منفصلة ثم يموّهه (Gaussian Blur) لإنتاج تأثير توهج خلف العنصر."""
    layer = Image.new("RGBA", base_size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    draw_fn(d)
    return layer.filter(ImageFilter.GaussianBlur(blur))


def design_awareness(title: str, subtitle: str, items: list[dict], summary: str, source: str = "") -> Image.Image:
    """تصميم توعوي: عنوان + عنوان فرعي + 3 أيقونات وعلامات تحذيرية + ملخص مختصر
    للمشكلة + رسم هاتف متصدّع بتأثير توهج. مناسب لمحتوى 'نصائح توعوية' و'أفضل الممارسات'."""
    top_c = COLORS["black"]
    bottom_c = COLORS["dark_blue"]
    img, draw = _base_canvas(top_c, bottom_c)

    grid = _grid_background(draw, top_c, COLORS["cyber_blue"], spacing=60, alpha=18)
    img = Image.alpha_composite(img.convert("RGBA"), grid).convert("RGB")
    draw = ImageDraw.Draw(img)

    # العنوان الرئيسي
    wrapped_title = _wrap_arabic(draw, title, 62, WIDTH - 120)
    y = _draw_multiline_centered(draw, wrapped_title, 62, COLORS["white"], WIDTH / 2, 70, 78)

    # العنوان الفرعي
    wrapped_sub = _wrap_arabic(draw, subtitle, 34, WIDTH - 140)
    y = _draw_multiline_centered(draw, wrapped_sub, 34, COLORS["cyan"], WIDTH / 2, y + 10, 46)

    # 3 أيقونات تحذيرية بعناوينها القصيرة — نرتّبها من اليمين لليسار (RTL):
    # أول عنصر منطقي في القائمة يظهر في أقصى اليمين، كما يقرأ القارئ العربي.
    icon_fns = {
        "battery": _battery_icon,
        "heat": _heat_icon,
        "eye": _eye_data_icon,
    }
    col_centers_rtl = [WIDTH * 0.80, WIDTH * 0.5, WIDTH * 0.20]
    icon_y = y + 90
    label_font_size = 28
    for (item, col_x) in zip(items[:3], col_centers_rtl):
        icon_color = COLORS["red_alert"] if item.get("severity", "high") == "high" else COLORS["cyan"]
        fn = icon_fns.get(item.get("icon", "eye"), _eye_data_icon)
        fn(draw, col_x, icon_y, 42, icon_color, width=6)

        wrapped_label = _wrap_arabic(draw, item["label"], label_font_size, WIDTH * 0.30)
        _draw_multiline_centered(
            draw, wrapped_label, label_font_size, COLORS["white"],
            col_x, icon_y + 70, label_font_size + 10,
        )

    # ملخص مختصر للمشكلة (الإضافة المطلوبة)
    summary_y = icon_y + 230
    wrapped_summary = _wrap_arabic(draw, summary, 30, WIDTH - 160)
    draw.rounded_rectangle(
        [70, summary_y - 22, WIDTH - 70, summary_y + 26 + 40 * len(wrapped_summary)],
        radius=18, outline=COLORS["cyan"], width=2,
    )
    _draw_multiline_centered(draw, wrapped_summary, 30, COLORS["white"], WIDTH / 2, summary_y, 40)

    # رسم الهاتف المتصدّع بتأثير توهج (نصف أحمر / نصف فيروزي)
    phone_cy = HEIGHT - 300
    phone_w, phone_h = 260, 470
    glow = _glow_layer(
        (WIDTH, HEIGHT),
        lambda d: _cracked_phone_icon(d, WIDTH / 2, phone_cy, phone_w + 20, phone_h + 20,
                                        COLORS["red_alert"], COLORS["cyan"]),
        COLORS["cyan"], blur=18,
    )
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)
    _cracked_phone_icon(draw, WIDTH / 2, phone_cy, phone_w, phone_h, COLORS["red_alert"], COLORS["cyan"])

    _source_line(draw, source)
    return img


def _fit_background_to_canvas(bg: Image.Image, canvas=None) -> Image.Image:
    """يقصّ ويُحجّم أي صورة خلفية خارجية (مثل الناتجة عن OpenAI) لتطابق أي
    مقاس هدف دون تشويه، عبر قصّ مركزي ثم إعادة تحجيم. يدعم أي نسبة عرض
    لارتفاع (يُستخدم لإعادة توظيف نفس الصورة الفنية لإنستغرام و LinkedIn معاً)."""
    target_w, target_h = canvas or (WIDTH, HEIGHT)
    target_ratio = target_w / target_h
    w, h = bg.size
    current_ratio = w / h
    if current_ratio > target_ratio:
        new_w = int(h * target_ratio)
        x0 = (w - new_w) // 2
        bg = bg.crop((x0, 0, x0 + new_w, h))
    else:
        new_h = int(w / target_ratio)
        y0 = (h - new_h) // 2
        bg = bg.crop((0, y0, w, y0 + new_h))
    return bg.resize((target_w, target_h), Image.LANCZOS)


def _darken_overlay(img: Image.Image, top_alpha=140, bottom_alpha=195) -> Image.Image:
    """يضيف تدرجاً داكناً شفافاً أعلى وأسفل الصورة لضمان وضوح النص فوق أي خلفية،
    بغض النظر عن مدى فاتحة أو معقّدة الخلفية المولّدة بالذكاء الاصطناعي.
    يعتمد على مقاس img نفسه (أياً كان)، وليس على WIDTH/HEIGHT الثابتين."""
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    band_h = round(h * 0.207)
    for y in range(band_h):
        a = int(top_alpha * (1 - y / band_h))
        od.line([(0, y), (w, y)], fill=(5, 8, 14, a))
    bottom_band_h = round(h * 0.356)
    for y in range(h - bottom_band_h, h):
        ratio = (y - (h - bottom_band_h)) / bottom_band_h
        a = int(bottom_alpha * ratio)
        od.line([(0, y), (w, y)], fill=(5, 8, 14, a))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def design_ai_background(bg: Image.Image, title: str, tag: str, urgent: bool = False,
                          details: str = "", date_str: str = "", source: str = "",
                          canvas: tuple[int, int] = (WIDTH, HEIGHT)) -> Image.Image:
    """يضع عناصر الهوية (وسم التصنيف في منتصف الخلفية + تاريخ الخبر + العنوان
    العربي + سطرا تفاصيل + اسم المصدر) فوق خلفية فنية مولّدة بالذكاء الاصطناعي
    (بدون نص داخلها أصلاً)، بنفس محرك الخطوط الموثوق. يدعم أي مقاس قماشة."""
    w, h = canvas
    img = _fit_background_to_canvas(bg, canvas=canvas)
    img = _darken_overlay(img)
    draw = ImageDraw.Draw(img)

    tag_color = COLORS["red_alert"] if urgent else COLORS["cyan"]
    title_y = h - h * 0.319

    # وسم التصنيف + التاريخ في منتصف مساحة الخلفية الفنية (الفراغ بين الأعلى والعنوان)
    center_y = title_y * 0.42
    _tag_badge_with_date(draw, tag, urgent, center_y, date_str, canvas=canvas)

    title_size = max(30, round(w * 0.0574))
    wrapped = _wrap_arabic(draw, title, title_size, w - round(w * 0.13))
    y_after_title = _draw_multiline_centered(
        draw, wrapped, title_size, COLORS["white"], w / 2, title_y, round(title_size * 1.29),
    )
    draw.rectangle(
        [w / 2 - w * 0.083, title_y - h * 0.022, w / 2 + w * 0.083, title_y - h * 0.019], fill=tag_color,
    )

    if details:
        img, draw, _ = _details_panel(img, details, y_after_title + h * 0.01, canvas=canvas)

    _source_line(draw, source, canvas=canvas)
    return img


def _draw_multiline_right(draw, lines, size, fill, right_x, start_y, line_height):
    """يرسم أسطراً متعددة محاذاة لليمين (المحاذاة الطبيعية لفقرة عربية طويلة،
    بخلاف التوسيط المستخدم في العناوين القصيرة)."""
    y = start_y
    for line in lines:
        rendered = _ar(line)
        w = _measure_mixed_line(draw, rendered, size)
        _draw_mixed_line(draw, rendered, size, fill, right_x - w, y)
        y += line_height
    return y


def design_detailed(title: str, tag: str, urgent: bool, body_text: str,
                     date_str: str = "", source: str = "", section_header: str = "ما الذي يحدث؟",
                     canvas: tuple[int, int] = (WIDTH, HEIGHT), bg_image: Image.Image | None = None) -> Image.Image:
    """تصميم 'تفصيلي': عنوان أعلى + رأس قسم (ما الذي يحدث؟) + فقرة كاملة
    محاذاة لليمين + أيقونة التصنيف + شارتا تاريخ ومصدر بيضاويتان أسفل الصورة.
    مستوحى من تخطيط نصي مرجعي زوّدنا به المستخدم. إن مُرِّر bg_image (خلفية
    فنية من OpenAI مثلاً)، تُستخدم بدل الرسم المجرّد المحلي، مع تعتيم تلقائي
    لضمان وضوح النص فوقها."""
    w, h = canvas
    accent = COLORS["red_alert"] if urgent else COLORS["cyan"]

    if bg_image is not None:
        img = _fit_background_to_canvas(bg_image, canvas=canvas)
        img = _darken_overlay(img, top_alpha=110, bottom_alpha=170)
        draw = ImageDraw.Draw(img)
    else:
        top_bg = COLORS["black"]
        bottom_bg = (28, 10, 10) if urgent else COLORS["dark_blue"]
        img, draw = _base_canvas(top_bg, bottom_bg, canvas=canvas)

        grid = _grid_background(draw, top_bg, COLORS["cyber_blue"], canvas=canvas)
        img = Image.alpha_composite(img.convert("RGBA"), grid).convert("RGB")
        draw = ImageDraw.Draw(img)

        lines_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lines_layer)
        _digital_lines(ld, accent, count=14, seed=9, canvas=canvas)
        img = Image.alpha_composite(img.convert("RGBA"), lines_layer).convert("RGB")
        draw = ImageDraw.Draw(img)

    right_margin = w * 0.072
    right_x = w - right_margin

    # وسم مضغوط أعلى يميناً
    tag_size = max(20, round(w * 0.026))
    tag_font = _font(FONT_BOLD, tag_size)
    tag_text = _ar(tag)
    tw = draw.textlength(tag_text, font=tag_font)
    pad = round(w * 0.02)
    badge_h = round(tag_size * 1.7)
    badge_top = h * 0.04
    draw.rounded_rectangle([right_x - tw - pad, badge_top, right_x + pad, badge_top + badge_h],
                            radius=badge_h / 2, fill=accent)
    draw.text((right_x - tw, badge_top + badge_h * 0.2), tag_text, font=tag_font, fill=COLORS["black"])

    # العنوان (محاذى لليمين، سطران كحد أقصى)
    title_size = max(34, round(w * 0.052))
    title_y = badge_top + badge_h + h * 0.03
    wrapped_title = _cap_lines(_wrap_arabic(draw, title, title_size, w - right_margin * 2), 2)
    y_after = _draw_multiline_right(draw, wrapped_title, title_size, COLORS["white"],
                                     right_x, title_y, round(title_size * 1.3))

    # رأس القسم: دائرة حمراء + عنوان القسم
    section_y = y_after + h * 0.03
    section_size = max(24, round(w * 0.03))
    section_font = _font(FONT_BOLD, section_size)
    section_text = _ar(section_header)
    sw = _measure_mixed_line(draw, section_text, section_size)
    dot_r = section_size * 0.28
    draw.text((right_x - sw, section_y), section_text, font=section_font, fill=COLORS["white"])
    draw.ellipse([right_x - sw - dot_r * 3, section_y + section_size * 0.22 - dot_r,
                  right_x - sw - dot_r, section_y + section_size * 0.22 + dot_r], fill=accent)

    # الفقرة الكاملة (محاذاة يمين، حتى 8 أسطر بدون أي قص لمعنى الجملة)
    body_size = max(26, round(w * 0.0305))
    body_y = section_y + h * 0.052
    wrapped_body = _cap_lines(_wrap_arabic(draw, body_text, body_size, w - right_margin * 2), 8)
    body_line_h = round(body_size * 1.55)
    y_after_body = _draw_multiline_right(draw, wrapped_body, body_size, (225, 230, 236),
                                          right_x, body_y, body_line_h)

    # أيقونة التصنيف (بديل الرسم التوضيحي، مرسومة محلياً) — تُوسَّط في
    # المساحة المتبقية بين نهاية الفقرة وشارتي التذييل، بدل موضع ثابت قد
    # يترك فراغاً كبيراً مع الفقرات القصيرة أو يتداخل مع الفقرات الطويلة.
    footer_zone_top = h - h * 0.135
    icon_size = min(w, h) * 0.15
    available_mid = (y_after_body + footer_zone_top) / 2
    icon_cy = max(available_mid, y_after_body + icon_size * 0.7)
    icon_cy = min(icon_cy, footer_zone_top - icon_size * 0.7)
    icon_fn = _icon_for_classification(tag)
    icon_fn(draw, w / 2, icon_cy, icon_size, accent, width=max(5, round(w * 0.0074)))

    # شارتا التاريخ والمصدر (خلفية فاتحة، نص داكن) أسفل الصورة
    footer_y = h - h * 0.075
    if date_str:
        d_text = _ar(f"تاريخ الإصدار: {date_str}")
        d_font = _font(FONT_BOLD, max(20, round(w * 0.024)))
        dw = draw.textlength(d_text, font=d_font)
        pad2 = round(w * 0.024)
        draw.rounded_rectangle([right_x - dw - pad2 * 2, footer_y, right_x, footer_y + round(w * 0.05)],
                                radius=round(w * 0.025), fill=(240, 244, 248))
        draw.text((right_x - dw - pad2, footer_y + round(w * 0.01)), d_text, font=d_font, fill=(10, 12, 16))

    if source:
        s_text = _ar(f"📌 المصدر: {source}")
        s_font = _font(FONT_BOLD, max(20, round(w * 0.024)))
        sw2 = draw.textlength(s_text, font=s_font)
        draw.text((w / 2 - sw2 / 2, h - h * 0.026), s_text, font=s_font, fill=(235, 190, 60))

    return img


def design_standard(title: str, tag: str, urgent: bool = False,
                     details: str = "", date_str: str = "", source: str = "",
                     canvas: tuple[int, int] = (WIDTH, HEIGHT)) -> Image.Image:
    """تصميم 1: خلفية متدرجة + شبكة رقمية + درع مركزي + عنوان علوي. يدعم أي
    مقاس قماشة (canvas=(width,height)) عبر رسم نسبي متكيّف."""
    w, h = canvas
    top = COLORS["black"]
    bottom = COLORS["dark_blue"]
    img, draw = _base_canvas(top, bottom, canvas=canvas)

    grid = _grid_background(draw, top, COLORS["cyber_blue"], canvas=canvas)
    img.paste(Image.alpha_composite(img.convert("RGBA"), grid).convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(img)

    lines_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines_layer)
    _digital_lines(ld, COLORS["cyan"], count=14, seed=7, canvas=canvas)
    img = Image.alpha_composite(img.convert("RGBA"), lines_layer).convert("RGB")
    draw = ImageDraw.Draw(img)

    # شريط الوسم العلوي (Tag) + التاريخ
    tag_bottom = _tag_badge_with_date(draw, tag, urgent, h * 0.09, date_str, canvas=canvas)

    # الدرع المركزي
    shield_cy = h * 0.356
    shield_size = min(w, h) * 0.13
    icon_fn = _icon_for_classification(tag)
    icon_fn(draw, w / 2, shield_cy, shield_size, COLORS["cyan"], width=max(5, round(w * 0.0074)))

    # العنوان
    title_size = max(30, round(w * 0.061))
    title_y = h * 0.533
    wrapped = _wrap_arabic(draw, title, title_size, w - round(w * 0.148))
    y_after = _draw_multiline_centered(draw, wrapped, title_size, COLORS["white"], w / 2, title_y, round(title_size * 1.27))

    # خط فاصل فيروزي
    sep_y = title_y - h * 0.044
    draw.rectangle([w / 2 - w * 0.083, sep_y, w / 2 + w * 0.083, sep_y + max(3, round(h * 0.003))], fill=COLORS["cyan"])

    if details:
        img, draw, y_after = _details_panel(img, details, y_after + h * 0.01, canvas=canvas)

    _network_nodes(draw, COLORS["cyan"], count=10, seed=3, canvas=canvas)
    _source_line(draw, source, canvas=canvas)
    return img


def design_alert(title: str, tag: str, details: str = "", date_str: str = "", source: str = "",
                  canvas: tuple[int, int] = (WIDTH, HEIGHT)) -> Image.Image:
    """تصميم 2: نمط تحذير عاجل (أحمر/أسود) لثغرات نشطة الاستغلال. يدعم أي مقاس قماشة."""
    w, h = canvas
    top = COLORS["black"]
    bottom = (30, 10, 10)
    img, draw = _base_canvas(top, bottom, canvas=canvas)

    lines_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines_layer)
    _digital_lines(ld, COLORS["red_alert"], count=16, seed=11, canvas=canvas)
    img = Image.alpha_composite(img.convert("RGBA"), lines_layer).convert("RGB")
    draw = ImageDraw.Draw(img)

    # شارة تحذير مثلثة مبسطة (بدون أي أشخاص)
    cx, cy, s = w / 2, h * 0.319, min(w, h) * 0.12
    draw.polygon(
        [(cx, cy - s), (cx - s * 0.95, cy + s * 0.75), (cx + s * 0.95, cy + s * 0.75)],
        outline=COLORS["red_alert"], width=max(5, round(w * 0.0074)),
    )
    excl_size = round(s * 1.0)
    excl_font = _font(FONT_BOLD, excl_size)
    draw.text((cx - excl_size * 0.14, cy - excl_size * 0.42), "!", font=excl_font, fill=COLORS["red_alert"])

    tag_bottom = _tag_badge_with_date(draw, tag, True, h * 0.09, date_str, canvas=canvas)

    title_size = max(30, round(w * 0.063))
    title_y = h * 0.519
    wrapped = _wrap_arabic(draw, title, title_size, w - round(w * 0.13))
    y_after = _draw_multiline_centered(draw, wrapped, title_size, COLORS["white"], w / 2, title_y, round(title_size * 1.26))

    sep_y = title_y - h * 0.03
    draw.rectangle([w / 2 - w * 0.083, sep_y, w / 2 + w * 0.083, sep_y + max(3, round(h * 0.003))], fill=COLORS["red_alert"])

    if details:
        img, draw, y_after = _details_panel(img, details, y_after + h * 0.01, canvas=canvas)

    _network_nodes(draw, COLORS["red_alert"], count=8, seed=4, canvas=canvas)
    _source_line(draw, source, canvas=canvas)
    return img


def design_minimal_dark(title: str, tag: str, urgent: bool = False,
                         details: str = "", date_str: str = "", source: str = "",
                         canvas: tuple[int, int] = (WIDTH, HEIGHT)) -> Image.Image:
    """تصميم 3: بساطة أكبر - خلفية رمادية داكنة + قفل جانبي + خط شبكي رفيع أسفل.
    يدعم أي مقاس قماشة."""
    w, h = canvas
    top = COLORS["dark_gray"]
    bottom = COLORS["black"]
    img, draw = _base_canvas(top, bottom, canvas=canvas)

    grid = _grid_background(draw, top, COLORS["cyan"], spacing=70, alpha=14, canvas=canvas)
    img = Image.alpha_composite(img.convert("RGBA"), grid).convert("RGB")
    draw = ImageDraw.Draw(img)

    accent = COLORS["red_alert"] if urgent else COLORS["cyan"]

    # شريط جانبي فيروزي
    draw.rectangle([0, 0, max(8, round(w * 0.013)), h], fill=accent)

    tag_size = max(22, round(w * 0.0296))
    tag_font = _font(FONT_BOLD, tag_size)
    tag_text = _ar(tag)
    tw = draw.textlength(tag_text, font=tag_font)
    tag_y = h * 0.067
    draw.text((w - tw - w * 0.056, tag_y), tag_text, font=tag_font, fill=accent)

    if date_str:
        date_size = max(16, round(w * 0.0222))
        date_font = _font(FONT_REGULAR, date_size)
        date_text = _ar(date_str)
        dw = draw.textlength(date_text, font=date_font)
        draw.text((w - dw - w * 0.056, tag_y + tag_size * 1.5), date_text, font=date_font, fill=(190, 196, 204))

    lock_size = min(w, h) * 0.111
    icon_fn = _icon_for_classification(tag)
    icon_fn(draw, w - w * 0.13, h * 0.237, lock_size, accent, width=max(5, round(w * 0.0074)))

    title_size = max(30, round(w * 0.065))
    title_y = h * 0.459
    wrapped = _wrap_arabic(draw, title, title_size, w - round(w * 0.185))
    y_after = _draw_multiline_centered(draw, wrapped, title_size, COLORS["white"], w / 2, title_y, round(title_size * 1.26))

    sep_y = title_y - h * 0.022
    draw.rectangle([w / 2 - w * 0.093, sep_y, w / 2 + w * 0.093, sep_y + max(3, round(h * 0.003))], fill=accent)

    if details:
        img, draw, y_after = _details_panel(img, details, y_after + h * 0.01, canvas=canvas)

    _network_nodes(draw, accent, count=9, seed=6,
                    region=(round(w * 0.056), h - round(h * 0.222), w - round(w * 0.056), h - round(h * 0.074)),
                    canvas=canvas)
    _source_line(draw, source, canvas=canvas)
    return img


# مقاسات جاهزة لمنصات التواصل الشائعة (يمكن إضافة المزيد بسهولة). المقاسات
# المربعة/الرأسية (نسبة ارتفاع لعرض ≥ 0.8) مضبوطة ومُختبرة بعناية. المقاسات
# الأفقية (landscape) تعمل تقنياً عبر نفس النظام النسبي لكنها لم تُختبر بصرياً
# بنفس الدقة بعد — قد تحتاج ضبطاً إضافياً لاحقاً إن استُخدمت كثيراً.
PLATFORM_SIZES = {
    "instagram": (1080, 1350),         # 4:5 رأسي — الافتراضي الحالي لإنستغرام
    "instagram_square": (1080, 1080),
    "linkedin": (1080, 1080),          # مربع — الأنسب والأكثر توافقاً على LinkedIn حالياً
    "stories": (1080, 1920),           # قصص إنستغرام/فيسبوك
    "facebook": (1200, 630),           # أفقي — تجريبي
    "twitter": (1200, 675),            # أفقي — تجريبي
}


def generate_platform_designs(content: dict, out_dir: str, platform: str = "linkedin",
                               ai_backgrounds: list | None = None) -> list[str]:
    """يولّد 3 تصاميم إضافية بمقاس مخصص لمنصة معينة (مثل LinkedIn المربع)
    باستخدام نفس محتوى الخبر وهويته البصرية. يعيد استخدام نفس صور
    ai_backgrounds المُولَّدة أصلاً لإنستغرام (إن وُجدت) بقصّ مختلف يناسب
    مقاس المنصة الجديدة — دون أي استدعاء إضافي لـ OpenAI، فتكلفة الصور
    الفنية تبقى ثابتة بغض النظر عن عدد المنصات."""
    if platform not in PLATFORM_SIZES:
        raise ValueError(f"منصة غير معروفة: {platform}. الخيارات المتاحة: {list(PLATFORM_SIZES)}")
    canvas = PLATFORM_SIZES[platform]

    os.makedirs(out_dir, exist_ok=True)
    title = content["image_title"]
    tag = content["classification"]
    urgent = content.get("urgency") == "عاجل"
    details_text = content.get("image_summary") or content.get("summary", "")
    date_str = _arabic_date()
    source = content.get("source", "")

    bgs = list(ai_backgrounds or [])
    bg1 = bgs[0] if len(bgs) > 0 else None
    bg2 = bgs[1] if len(bgs) > 1 else None
    bg3 = bgs[2] if len(bgs) > 2 else None

    design_1 = (f"{platform}_1_ai", design_ai_background(
        bg1, title, tag, urgent, details=details_text, date_str=date_str, source=source, canvas=canvas,
    )) if bg1 is not None else (f"{platform}_1_standard", design_standard(
        title, tag, urgent, details=details_text, date_str=date_str, source=source, canvas=canvas,
    ))

    design_2 = (f"{platform}_2_ai", design_ai_background(
        bg2, title, tag, urgent, details=details_text, date_str=date_str, source=source, canvas=canvas,
    )) if bg2 is not None else (f"{platform}_2_{'alert' if urgent else 'minimal'}", (
        design_alert(title, tag, details=details_text, date_str=date_str, source=source, canvas=canvas) if urgent
        else design_minimal_dark(title, tag, urgent, details=details_text, date_str=date_str, source=source, canvas=canvas)
    ))

    full_body = content.get("summary") or details_text
    design_3 = (f"{platform}_3_detailed", design_detailed(
        title, tag, urgent, full_body, date_str=date_str, source=source, canvas=canvas, bg_image=bg3,
    ))

    designs = [design_1, design_2, design_3]

    paths = []
    for name, img in designs:
        path = os.path.join(out_dir, f"{name}.png")
        img.save(path, "PNG", optimize=True)
        paths.append(path)
    return paths


def generate_designs(content: dict, out_dir: str, ai_backgrounds: list | None = None) -> list[str]:
    """يولّد 3 تصاميم بناءً على المحتوى ويحفظها كـ PNG، ويعيد قائمة المسارات.

    ai_backgrounds: قائمة اختيارية من حتى 3 صور PIL (خلفيات فنية بدون نص، من
    OpenAI مثلاً) — كل عنصر يقابل أحد التصاميم الثلاثة بالترتيب (design_1,
    design_2, design_3). أي عنصر مفقود أو None يُستخدم له الرسم المحلي
    بـ Pillow كبديل تلقائي. مرّر [] أو None لتجاهل الخلفيات الفنية بالكامل.

    إن كان الخبر تصنيفه 'نصائح توعوية' أو 'أفضل الممارسات' وتوفرت عناصر
    awareness_items (3 علامات) في المحتوى، يُستخدم قالب التوعية (أيقونات +
    ملخص المشكلة + هاتف متصدّع) كأحد التصاميم الثلاثة بدلاً من التصميم المجرّد
    (هذا القالب لا يدعم الخلفية الفنية حالياً بسبب تخطيطه المتخصص).
    """
    os.makedirs(out_dir, exist_ok=True)
    title = content["image_title"]
    tag = content["classification"]
    urgent = content.get("urgency") == "عاجل"
    details_text = content.get("image_summary") or content.get("summary", "")
    date_str = _arabic_date()
    source = content.get("source", "")

    bgs = list(ai_backgrounds or [])
    bg1 = bgs[0] if len(bgs) > 0 else None
    bg2 = bgs[1] if len(bgs) > 1 else None
    bg3 = bgs[2] if len(bgs) > 2 else None

    paths = []
    if bg1 is not None:
        design_1 = ("design_1_ai", design_ai_background(
            bg1, title, tag, urgent, details=details_text, date_str=date_str, source=source,
        ))
    else:
        design_1 = ("design_1_standard", design_standard(
            title, tag, urgent, details=details_text, date_str=date_str, source=source,
        ))

    if bg2 is not None:
        design_2 = ("design_2_ai", design_ai_background(
            bg2, title, tag, urgent, details=details_text, date_str=date_str, source=source,
        ))
    else:
        design_2 = ("design_2_alert" if urgent else "design_2_minimal", (
            design_alert(title, tag, details=details_text, date_str=date_str, source=source) if urgent
            else design_minimal_dark(title, tag, urgent, details=details_text, date_str=date_str, source=source)
        ))

    designs = [design_1, design_2]

    items = content.get("awareness_items")
    awareness_summary = content.get("problem_summary")
    is_awareness_type = tag in ("نصائح توعوية", "أفضل الممارسات")
    if is_awareness_type and items and len(items) >= 3 and awareness_summary:
        subtitle = content.get("hook_title", "")
        designs.append((
            "design_3_awareness",
            design_awareness(title, subtitle, items, awareness_summary, source=source),
        ))
    else:
        # التصميم التفصيلي: فقرة كاملة (وليست جملة مختصرة) + رأس قسم + أيقونة
        # التصنيف — يستخدم حقل summary الأطول بدل image_summary القصير، لأن
        # الغرض هنا عرض شرح كامل داخل الصورة نفسه بدل عبارة بصرية موجزة.
        # يستخدم bg3 كخلفية فنية إن توفرت.
        full_body = content.get("summary") or details_text
        designs.append((
            "design_3_detailed" if bg3 is None else "design_3_detailed_ai",
            design_detailed(title, tag, urgent, full_body, date_str=date_str, source=source, bg_image=bg3),
        ))

    for name, img in designs:
        path = os.path.join(out_dir, f"{name}.png")
        img.save(path, "PNG", optimize=True)
        paths.append(path)
    return paths


if __name__ == "__main__":
    demo = {
        "image_title": "هل هاتفك مراقب؟",
        "hook_title": "3 علامات تحذيرية تدل على الاختراق",
        "classification": "نصائح توعوية",
        "urgency": "عادي",
        "problem_summary": "بعض التطبيقات الخبيثة تعمل بصمت في الخلفية، تستهلك موارد جهازك وتُسرّب بياناتك دون علمك.",
        "awareness_items": [
            {"icon": "battery", "label": "استنزاف البطارية بسرعة", "severity": "high"},
            {"icon": "heat", "label": "ارتفاع حرارة الجهاز", "severity": "high"},
            {"icon": "eye", "label": "استهلاك بيانات مجهول", "severity": "normal"},
        ],
    }
    out = generate_designs(demo, "/tmp/cyber_demo_awareness")
    print(out)
