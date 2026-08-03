"""
image_generator.py
يولّد تصاميم صور (1080x1350) بهوية بصرية سيبرانية (Modern Minimal) بدون أشخاص:
شبكات، خطوط رقمية، أقفال، دروع، خوادم - وفق نظام ألوان محدد.
يدعم النص العربي عبر إعادة التشكيل (reshaping) واتجاه RTL.
"""

import math
import os
import random
import re
import unicodedata
from datetime import datetime, timezone

import arabic_reshaper
from bidi.algorithm import get_display
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT = 1080, 1350
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
FONT_BOLD = os.path.join(FONT_DIR, "Cairo-Bold.ttf")
FONT_REGULAR = os.path.join(FONT_DIR, "Cairo-Regular.ttf")
FONT_SEMIBOLD = os.path.join(FONT_DIR, "Cairo-SemiBold.ttf")
# خط Cairo يغطي العربية واللاتينية أصلياً في ملف واحد، لكن نُبقي على منطق
# اختيار الخط المزدوج (أدناه) كحماية إضافية إن ظهر حرف نادر غير مدعوم مستقبلاً.
FONT_LATIN_BOLD = FONT_BOLD

# نقرأ خرائط الحروف (cmap) مرة واحدة فقط لمعرفة أي حرف مدعوم فعلياً في كل خط،
# بدلاً من الاعتماد على قائمة ثابتة قد تفوت علامات ترقيم مثل / ( ) %
_AR_CMAP = set(TTFont(FONT_BOLD).getBestCmap().keys())
_LATIN_CMAP = set(TTFont(FONT_LATIN_BOLD).getBestCmap().keys())

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


# محارف تحكم Unicode لعزل الاتجاه (LRE...PDF): تُستخدم لتغليف أي عبارة لاتينية
# مدمجة داخل نص عربي (مثل "Firewall Management Center (FMC)") كوحدة واحدة قوية
# الاتجاه (LTR)، لأن مكتبة bidi المستخدمة هنا (python-bidi 0.6.x) لا "تُرحّل"
# الأقواس بشكل صحيح عند اعتمادها فقط على القواعد الضمنية دون عزل صريح — وهذا
# يسبب خللاً ملحوظاً مثل ظهور "(FMC" بدل "(FMC)" منعكسة الموضع. عزل العبارة
# بالكامل (بما فيها الأقواس الداخلية) كوحدة LTR واحدة يحل المشكلة جذرياً.
_LRE, _PDF = "\u202A", "\u202C"
_LATIN_RUN = re.compile(r"\(?[A-Za-z][A-Za-z0-9 _\-/%.,:()]*[A-Za-z0-9)%]|[A-Za-z]")


def _isolate_latin_runs(text: str) -> str:
    return _LATIN_RUN.sub(lambda m: _LRE + m.group(0) + _PDF, text)


def _ar(text: str) -> str:
    """تجهيز نص عربي للعرض الصحيح (تشكيل + اتجاه) داخل Pillow، مع معالجتين احتياطيتين:
    1) عزل أي عبارة لاتينية مدمجة (بما فيها الأقواس) كوحدة LTR واحدة قبل تطبيق
       خوارزمية bidi، لتفادي خلل ترتيب الأقواس مع الاختصارات الإنجليزية.
    2) بعض الحروف العربية غير الواصلة (مثل ر، ة) قد لا يملك الخط شكلها المُقدَّم
       من reshaper تحديداً؛ في هذه الحالة نستبدلها بالحرف الأساسي غير المُشكَّل."""
    isolated = _isolate_latin_runs(text)
    reshaped = arabic_reshaper.reshape(isolated)
    displayed = get_display(reshaped, base_dir="R")
    result = []
    for ch in displayed:
        if ch.isspace() or ord(ch) in _AR_CMAP or ord(ch) in _LATIN_CMAP:
            result.append(ch)
            continue
        fallback = unicodedata.normalize("NFKC", ch)
        result.append(fallback if fallback else ch)
    return "".join(result)


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _is_arabic_char(ch: str) -> bool:
    """يحدد أي خط يجب استخدامه لهذا الحرف اعتماداً على تغطية الحروف الفعلية
    في ملفات الخطوط (cmap)، وليس على قائمة ثابتة قد تفوت رموزاً مثل / ( ) %."""
    if ch.isspace():
        return True
    code = ord(ch)
    if code in _AR_CMAP:
        return True
    if code in _LATIN_CMAP:
        return False
    return True  # افتراضياً: اعتمد الخط العربي إن لم يكن الحرف موجوداً في أي منهما


def _font_for_size(base_path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(base_path, size)


def _draw_mixed_line(draw, text: str, size: int, fill, x_left: float, y: float) -> float:
    """يرسم سطراً واحداً (بعد reshape/bidi) مستخدماً الخط العربي للحروف العربية
    وخطاً لاتينياً احتياطياً لأي حروف إنجليزية مدمجة، بدءاً من x_left ويعيد العرض الكلي."""
    ar_font = _font_for_size(FONT_BOLD, size)
    lat_font = _font_for_size(FONT_LATIN_BOLD, size)

    runs: list[tuple[str, bool]] = []
    for ch in text:
        is_ar = _is_arabic_char(ch)
        if runs and runs[-1][1] == is_ar:
            runs[-1] = (runs[-1][0] + ch, is_ar)
        else:
            runs.append((ch, is_ar))

    cursor = x_left
    for chunk, is_ar in runs:
        font = ar_font if is_ar else lat_font
        draw.text((cursor, y), chunk, font=font, fill=fill)
        cursor += draw.textlength(chunk, font=font)
    return cursor - x_left


def _measure_mixed_line(draw, text: str, size: int) -> float:
    ar_font = _font_for_size(FONT_BOLD, size)
    lat_font = _font_for_size(FONT_LATIN_BOLD, size)
    total = 0.0
    current_ar, current_chunk = None, ""
    for ch in text:
        is_ar = _is_arabic_char(ch)
        if current_ar is None or is_ar == current_ar:
            current_chunk += ch
            current_ar = is_ar
        else:
            total += draw.textlength(current_chunk, font=(ar_font if current_ar else lat_font))
            current_chunk, current_ar = ch, is_ar
    if current_chunk:
        total += draw.textlength(current_chunk, font=(ar_font if current_ar else lat_font))
    return total


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
                    text_color=(225, 230, 236), max_lines: int = 2):
    """يرسم صندوق 'المختصر' (سطرين تفاصيل) بخلفية داكنة شفافة فوق أي خلفية،
    ويعيد (img, draw, box_bottom) الجديدين لمتابعة الرسم بعده."""
    draw = ImageDraw.Draw(img)
    lines = _cap_lines(_wrap_arabic(draw, details, 28, WIDTH - 160), max_lines)
    box_h = 30 + 36 * len(lines)
    panel = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle([60, box_top, WIDTH - 60, box_top + box_h], radius=16, fill=(8, 11, 18, 165))
    img = Image.alpha_composite(img.convert("RGBA"), panel).convert("RGB")
    draw = ImageDraw.Draw(img)
    _draw_multiline_centered(draw, lines, 28, text_color, WIDTH / 2, box_top + 16, 36)
    return img, draw, box_top + box_h


def _tag_badge_with_date(draw, tag: str, urgent: bool, center_y: float, date_str: str = ""):
    """يرسم وسم التصنيف (Tag) في منتصف عمودي محدد، مع تاريخ الخبر أسفله مباشرة."""
    tag_color = COLORS["red_alert"] if urgent else COLORS["cyan"]
    tag_font = _font(FONT_BOLD, 34)
    tag_text = _ar(tag)
    tw = draw.textlength(tag_text, font=tag_font)
    pad = 30
    badge_top = center_y - 32
    draw.rounded_rectangle(
        [WIDTH / 2 - tw / 2 - pad, badge_top, WIDTH / 2 + tw / 2 + pad, badge_top + 64],
        radius=32, fill=tag_color,
    )
    draw.text((WIDTH / 2 - tw / 2, badge_top + 16), tag_text, font=tag_font, fill=COLORS["black"])

    if date_str:
        date_font = _font(FONT_REGULAR, 26)
        date_text = _ar(date_str)
        dw = draw.textlength(date_text, font=date_font)
        dx = WIDTH / 2 - dw / 2
        dy = badge_top + 78
        draw.rounded_rectangle([dx - 14, dy - 6, dx + dw + 14, dy + 32], radius=10, fill=(6, 9, 14))
        draw.text((dx, dy), date_text, font=date_font, fill=(200, 208, 218))
    return badge_top + 64 + (44 if date_str else 0)


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
    x = WIDTH - w - 50
    y = HEIGHT - 60
    draw.rounded_rectangle([x - 16, y - 8, x + w + 16, y + 34], radius=10, fill=(6, 9, 14))
    draw.text((x, y), text, font=font, fill=COLORS["cyan"])


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


def design_awareness(title: str, subtitle: str, items: list[dict], summary: str) -> Image.Image:
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

    return img


def _fit_background_to_canvas(bg: Image.Image) -> Image.Image:
    """يقصّ ويُحجّم أي صورة خلفية خارجية (مثل الناتجة عن OpenAI) لتطابق مقاس
    المنشور 1080x1350 (نسبة 4:5) دون تشويه، عبر قصّ مركزي ثم إعادة تحجيم."""
    target_ratio = WIDTH / HEIGHT
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
    return bg.resize((WIDTH, HEIGHT), Image.LANCZOS)


def _darken_overlay(img: Image.Image, top_alpha=140, bottom_alpha=195) -> Image.Image:
    """يضيف تدرجاً داكناً شفافاً أعلى وأسفل الصورة لضمان وضوح النص فوق أي خلفية،
    بغض النظر عن مدى فاتحة أو معقّدة الخلفية المولّدة بالذكاء الاصطناعي."""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    band_h = 280
    for y in range(band_h):
        a = int(top_alpha * (1 - y / band_h))
        od.line([(0, y), (WIDTH, y)], fill=(5, 8, 14, a))
    for y in range(HEIGHT - 480, HEIGHT):
        ratio = (y - (HEIGHT - 480)) / 480
        a = int(bottom_alpha * ratio)
        od.line([(0, y), (WIDTH, y)], fill=(5, 8, 14, a))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def design_ai_background(bg: Image.Image, title: str, tag: str, urgent: bool = False,
                          details: str = "", date_str: str = "") -> Image.Image:
    """يضع عناصر الهوية (وسم التصنيف في منتصف الخلفية + تاريخ الخبر + العنوان
    العربي + سطرا تفاصيل + التذييل) فوق خلفية فنية مولّدة بالذكاء الاصطناعي
    (بدون نص داخلها أصلاً)، بنفس محرك الخطوط الموثوق."""
    img = _fit_background_to_canvas(bg)
    img = _darken_overlay(img)
    draw = ImageDraw.Draw(img)

    tag_color = COLORS["red_alert"] if urgent else COLORS["cyan"]
    title_y = HEIGHT - 430

    # وسم التصنيف + التاريخ في منتصف مساحة الخلفية الفنية (الفراغ بين الأعلى والعنوان)
    center_y = title_y * 0.42
    _tag_badge_with_date(draw, tag, urgent, center_y, date_str)

    wrapped = _wrap_arabic(draw, title, 62, WIDTH - 140)
    y_after_title = _draw_multiline_centered(
        draw, wrapped, 62, COLORS["white"], WIDTH / 2, title_y, 80,
    )
    draw.rectangle(
        [WIDTH / 2 - 90, title_y - 30, WIDTH / 2 + 90, title_y - 26], fill=tag_color,
    )

    if details:
        img, draw, _ = _details_panel(img, details, y_after_title + 14)

    return img


def design_standard(title: str, tag: str, urgent: bool = False,
                     details: str = "", date_str: str = "") -> Image.Image:
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

    # شريط الوسم العلوي (Tag) + التاريخ
    _tag_badge_with_date(draw, tag, urgent, 122, date_str)

    # الدرع المركزي
    _shield_icon(draw, WIDTH / 2, 480, 140, COLORS["cyan"], width=8)

    # العنوان
    wrapped = _wrap_arabic(draw, title, 66, WIDTH - 160)
    y_after = _draw_multiline_centered(draw, wrapped, 66, COLORS["white"], WIDTH / 2, 720, 84)

    # خط فاصل فيروزي
    draw.rectangle([WIDTH / 2 - 90, 660, WIDTH / 2 + 90, 664], fill=COLORS["cyan"])

    if details:
        img, draw, y_after = _details_panel(img, details, y_after + 14)

    _network_nodes(draw, COLORS["cyan"], count=10, seed=3)
    return img


def design_alert(title: str, tag: str, details: str = "", date_str: str = "") -> Image.Image:
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

    _tag_badge_with_date(draw, tag, True, 122, date_str)

    wrapped = _wrap_arabic(draw, title, 68, WIDTH - 140)
    y_after = _draw_multiline_centered(draw, wrapped, 68, COLORS["white"], WIDTH / 2, 700, 86)

    draw.rectangle([WIDTH / 2 - 90, 660, WIDTH / 2 + 90, 664], fill=COLORS["red_alert"])

    if details:
        img, draw, y_after = _details_panel(img, details, y_after + 14)

    _network_nodes(draw, COLORS["red_alert"], count=8, seed=4)
    return img


def design_minimal_dark(title: str, tag: str, urgent: bool = False,
                         details: str = "", date_str: str = "") -> Image.Image:
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

    if date_str:
        date_font = _font(FONT_REGULAR, 24)
        date_text = _ar(date_str)
        dw = draw.textlength(date_text, font=date_font)
        draw.text((WIDTH - dw - 60, 138), date_text, font=date_font, fill=(190, 196, 204))

    _lock_icon(draw, WIDTH - 140, 320, 120, accent, width=8)

    wrapped = _wrap_arabic(draw, title, 70, WIDTH - 200)
    y_after = _draw_multiline_centered(draw, wrapped, 70, COLORS["white"], WIDTH / 2, 620, 88)

    draw.rectangle([WIDTH / 2 - 100, HEIGHT - 470, WIDTH / 2 + 100, HEIGHT - 466], fill=accent)

    if details:
        img, draw, y_after = _details_panel(img, details, y_after + 14)

    _network_nodes(draw, accent, count=9, seed=6, region=(60, HEIGHT - 300, WIDTH - 60, HEIGHT - 100))
    return img


def generate_designs(content: dict, out_dir: str, ai_background=None) -> list[str]:
    """يولّد 3 تصاميم بناءً على المحتوى ويحفظها كـ PNG، ويعيد قائمة المسارات.

    ai_background: صورة PIL اختيارية (خلفية فنية بدون نص، من OpenAI مثلاً) —
    إن مُررت، يُستخدم التصميم الأول (design_1) بهذه الخلفية بدل الرسم المجرّد.
    إن لم تُمرَّر (None)، يعمل كل شيء بالكامل بـ Pillow المحلي كما كان.

    إن كان الخبر تصنيفه 'نصائح توعوية' أو 'أفضل الممارسات' وتوفرت عناصر
    awareness_items (3 علامات) في المحتوى، يُستخدم قالب التوعية (أيقونات +
    ملخص المشكلة + هاتف متصدّع) كأحد التصاميم الثلاثة بدلاً من التصميم المجرّد.
    """
    os.makedirs(out_dir, exist_ok=True)
    title = content["image_title"]
    tag = content["classification"]
    urgent = content.get("urgency") == "عاجل"
    details_text = content.get("summary", "")
    date_str = _arabic_date()

    paths = []
    if ai_background is not None:
        design_1 = ("design_1_ai", design_ai_background(
            ai_background, title, tag, urgent, details=details_text, date_str=date_str,
        ))
    else:
        design_1 = ("design_1_standard", design_standard(
            title, tag, urgent, details=details_text, date_str=date_str,
        ))

    designs = [
        design_1,
        ("design_2_alert" if urgent else "design_2_minimal", (
            design_alert(title, tag, details=details_text, date_str=date_str) if urgent
            else design_minimal_dark(title, tag, urgent, details=details_text, date_str=date_str)
        )),
    ]

    items = content.get("awareness_items")
    summary = content.get("problem_summary")
    is_awareness_type = tag in ("نصائح توعوية", "أفضل الممارسات")
    if is_awareness_type and items and len(items) >= 3 and summary:
        subtitle = content.get("hook_title", "")
        designs.append((
            "design_3_awareness",
            design_awareness(title, subtitle, items, summary),
        ))
    else:
        designs.append(("design_3_minimal", design_minimal_dark(
            title, tag, urgent, details=details_text, date_str=date_str,
        )))

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
