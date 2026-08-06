"""
grc_image_generator.py
يولّد تصاميم صور بهوية بصرية رسمية/مؤسسية (أبيض/كريمي مع لمسات كحلي وذهبي)
لمحتوى الحوكمة وإدارة المخاطر والامتثال (GRC) — منفصلة عن الهوية السيبرانية
الداكنة في image_generator.py، لكنها تُعيد استخدام نفس محرك معالجة النصوص
العربية (RTL، إصلاح الأقواس، الخط Cairo) وأشكال الأيقونات الأساسية، لضمان
جودة وموثوقية متطابقتين دون تكرار الكود المُختبر أصلاً.
"""

import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

from image_generator import (
    FONT_BOLD, FONT_REGULAR, FONT_SEMIBOLD,
    _ar, _arabic_date, _cap_lines, _checklist_icon, _draw_mixed_line,
    _draw_multiline_centered, _fit_background_to_canvas, _font, _lock_icon,
    _measure_mixed_line, _news_icon, _radar_icon, _report_icon, _shield_icon,
    _wrap_arabic,
)

WIDTH, HEIGHT = 1080, 1350

GRC = {
    "white": (255, 255, 255),
    "cream": (250, 248, 243),
    "navy": (17, 35, 63),
    "navy_soft": (42, 62, 92),
    "gold": (185, 148, 74),
    "gray": (128, 136, 148),
    "light_gray": (235, 237, 240),
    "red_critical": (168, 40, 40),
}

# خرائط الأيقونات — نُعيد استخدام أشكالاً موجودة أصلاً في image_generator.py
# لأنها عامة الشكل (خطوط/دوائر) وتصلح بصرياً لسياق GRC أيضاً.
GRC_CLASSIFICATION_ICONS = {
    "تحديث تنظيمي": _report_icon,
    "إطار عمل جديد": _checklist_icon,
    "تقرير وأبحاث": _report_icon,
    "أفضل ممارسات حوكمة": _checklist_icon,
    "إدارة مخاطر": _radar_icon,
    "تدقيق وامتثال": _shield_icon,
    "فعالية وتدريب": _news_icon,
    "تحذير عاجل": _shield_icon,
}


def _grc_icon_for(tag: str):
    return GRC_CLASSIFICATION_ICONS.get(tag, _report_icon)


def _grc_lighten_overlay(img: Image.Image, top_alpha=150, bottom_alpha=200) -> Image.Image:
    """يضيف تدرجاً أبيض/فاتح شفافاً أعلى وأسفل الصورة لضمان وضوح النص الكحلي
    الداكن فوق أي خلفية فنية (حتى لو كانت معقدة أو ملونة)، عكس _darken_overlay
    السيبراني — هنا نُفتّح بدل نُعتّم لأن نص GRC داكن على خلفية فاتحة."""
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    band_h = round(h * 0.22)
    for y in range(band_h):
        a = int(top_alpha * (1 - y / band_h))
        od.line([(0, y), (w, y)], fill=(255, 255, 253, a))
    bottom_band_h = round(h * 0.4)
    for y in range(h - bottom_band_h, h):
        ratio = (y - (h - bottom_band_h)) / bottom_band_h
        a = int(bottom_alpha * ratio)
        od.line([(0, y), (w, y)], fill=(255, 255, 253, a))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _grc_base_canvas(canvas=None):
    """خلفية متدرجة بيضاء/كريمية فاتحة نظيفة، بدل التدرج الداكن السيبراني."""
    w, h = canvas or (WIDTH, HEIGHT)
    img = Image.new("RGB", (w, h), GRC["white"])
    draw = ImageDraw.Draw(img)
    top, bottom = GRC["white"], GRC["cream"]
    for y in range(h):
        ratio = y / h
        r = int(top[0] * (1 - ratio) + bottom[0] * ratio)
        g = int(top[1] * (1 - ratio) + bottom[1] * ratio)
        b = int(top[2] * (1 - ratio) + bottom[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img, draw


def _grc_frame(draw, accent, canvas=None):
    """إطار زوايا رفيع بدل الشبكة الرقمية الداكنة — أسلوب مؤسسي أنظف."""
    w, h = canvas or (WIDTH, HEIGHT)
    margin = round(w * 0.045)
    corner = round(w * 0.09)
    width = max(3, round(w * 0.0037))
    for cx, cy, dx, dy in (
        (margin, margin, 1, 1), (w - margin, margin, -1, 1),
        (margin, h - margin, 1, -1), (w - margin, h - margin, -1, -1),
    ):
        draw.line([(cx, cy), (cx + dx * corner, cy)], fill=accent, width=width)
        draw.line([(cx, cy), (cx, cy + dy * corner)], fill=accent, width=width)


def _grc_tag_badge_with_date(draw, tag, urgent, center_y, date_str="", canvas=None):
    w, _ = canvas or (WIDTH, HEIGHT)
    accent = GRC["red_critical"] if urgent else GRC["navy"]
    tag_size = max(24, round(w * 0.0296))
    tag_font = _font(FONT_SEMIBOLD, tag_size)
    tag_text = _ar(tag)
    tw = draw.textlength(tag_text, font=tag_font)
    pad = round(w * 0.026)
    badge_h = round(tag_size * 1.8)
    badge_top = center_y - badge_h / 2
    draw.rounded_rectangle(
        [w / 2 - tw / 2 - pad, badge_top, w / 2 + tw / 2 + pad, badge_top + badge_h],
        radius=6, fill=accent,
    )
    draw.text((w / 2 - tw / 2, badge_top + badge_h * 0.22), tag_text, font=tag_font, fill=GRC["white"])

    extra = 0
    if date_str:
        date_size = max(18, round(w * 0.0215))
        date_font = _font(FONT_REGULAR, date_size)
        date_text = _ar(date_str)
        dw = draw.textlength(date_text, font=date_font)
        dy = badge_top + badge_h + round(w * 0.014)
        draw.text((w / 2 - dw / 2, dy), date_text, font=date_font, fill=GRC["gray"])
        extra = round(date_size * 1.5) + round(w * 0.014)
    return badge_top + badge_h + extra


def _grc_details_panel(img, details, box_top, canvas=None, max_lines=4):
    w, h = canvas or (WIDTH, HEIGHT)
    text_size = max(24, round(w * 0.030))
    line_h = round(text_size * 1.4)
    draw = ImageDraw.Draw(img)
    lines = _cap_lines(_wrap_arabic(draw, details, text_size, w - round(w * 0.148)), max_lines)
    box_h = round(w * 0.036) + line_h * len(lines)
    margin = round(w * 0.056)
    draw.rounded_rectangle(
        [margin, box_top, w - margin, box_top + box_h], radius=round(w * 0.012),
        fill=GRC["light_gray"], outline=GRC["navy_soft"], width=1,
    )
    _draw_multiline_centered(draw, lines, text_size, GRC["navy"], w / 2, box_top + round(w * 0.017), line_h)
    return img, draw, box_top + box_h


def _grc_source_line(draw, source, canvas=None):
    if not source:
        return
    w, h = canvas or (WIDTH, HEIGHT)
    text = _ar(f"المصدر: {source}")
    text_size = max(18, round(w * 0.0222))
    tw = _measure_mixed_line(draw, text, text_size)
    x = w - tw - round(w * 0.046)
    y = h - round(h * 0.044)
    _draw_mixed_line(draw, text, text_size, GRC["gold"], x, y)


def _grc_network_dots(draw, color, count=8, seed=2, region=None, canvas=None):
    """نسخة هادئة (بلا خطوط اتصال كثيفة) من عنصر الزخرفة السيبراني، تناسب
    الطابع المؤسسي الأنظف — نقاط متناثرة خفيفة فقط."""
    w, h = canvas or (WIDTH, HEIGHT)
    rnd = random.Random(seed)
    if region is None:
        region = (round(w * 0.056), h - round(h * 0.193), w - round(w * 0.056), h - round(h * 0.06))
    x0, y0, x1, y1 = region
    points = [(rnd.randint(x0, x1), rnd.randint(y0, y1)) for _ in range(count)]
    for p in points:
        r = rnd.randint(2, 4)
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)


def grc_design_standard(title, tag, urgent=False, details="", date_str="", source="",
                         canvas: tuple[int, int] = (WIDTH, HEIGHT), bg_image=None) -> Image.Image:
    """تصميم GRC 1: خلفية بيضاء/كريمية (أو فنية عبر bg_image) + إطار زوايا +
    أيقونة مركزية + عنوان."""
    w, h = canvas
    accent = GRC["red_critical"] if urgent else GRC["navy"]

    if bg_image is not None:
        img = _fit_background_to_canvas(bg_image, canvas=canvas)
        img = _grc_lighten_overlay(img)
        draw = ImageDraw.Draw(img)
    else:
        img, draw = _grc_base_canvas(canvas)
        _grc_frame(draw, GRC["gold"], canvas)

    _grc_tag_badge_with_date(draw, tag, urgent, h * 0.09, date_str, canvas=canvas)

    icon_cy = h * 0.356
    icon_size = min(w, h) * 0.125
    icon_fn = _grc_icon_for(tag)
    icon_fn(draw, w / 2, icon_cy, icon_size, GRC["navy"], width=max(4, round(w * 0.0056)))

    title_size = max(30, round(w * 0.058))
    title_y = h * 0.533
    wrapped = _wrap_arabic(draw, title, title_size, w - round(w * 0.148))
    y_after = _draw_multiline_centered(draw, wrapped, title_size, GRC["navy"], w / 2, title_y, round(title_size * 1.27))

    sep_y = title_y - h * 0.044
    draw.rectangle([w / 2 - w * 0.06, sep_y, w / 2 + w * 0.06, sep_y + max(2, round(h * 0.0022))], fill=GRC["gold"])

    if details:
        img, draw, y_after = _grc_details_panel(img, details, y_after + h * 0.01, canvas=canvas)

    _grc_network_dots(draw, GRC["gold"], count=7, seed=3, canvas=canvas)
    _grc_source_line(draw, source, canvas=canvas)
    return img


def grc_design_highlight(title, tag, urgent, details="", date_str="", source="",
                          canvas: tuple[int, int] = (WIDTH, HEIGHT), bg_image=None) -> Image.Image:
    """تصميم GRC 2: بطاقة 'إشعار رسمي' — شريط علوي كحلي/ذهبي + عنوان بارز،
    بديل مؤسسي لنمط 'التحذير العاجل' السيبراني."""
    w, h = canvas
    accent = GRC["red_critical"] if urgent else GRC["gold"]

    if bg_image is not None:
        img = _fit_background_to_canvas(bg_image, canvas=canvas)
        img = _grc_lighten_overlay(img)
        draw = ImageDraw.Draw(img)
    else:
        img, draw = _grc_base_canvas(canvas)

    band_h = round(h * 0.1)
    draw.rectangle([0, 0, w, band_h], fill=GRC["navy"])
    label = _ar("إشعار رسمي" if not urgent else "إشعار عاجل")
    label_font = _font(FONT_SEMIBOLD, max(24, round(w * 0.03)))
    lw = draw.textlength(label, font=label_font)
    draw.text((w / 2 - lw / 2, band_h * 0.3), label, font=label_font, fill=GRC["white"])

    icon_cy = band_h + h * 0.2
    icon_size = min(w, h) * 0.13
    icon_fn = _grc_icon_for(tag)
    icon_fn(draw, w / 2, icon_cy, icon_size, accent, width=max(4, round(w * 0.0056)))

    tag_size = max(22, round(w * 0.027))
    tag_font = _font(FONT_SEMIBOLD, tag_size)
    tag_text = _ar(tag)
    tw = draw.textlength(tag_text, font=tag_font)
    tag_y = icon_cy + icon_size * 0.9
    draw.text((w / 2 - tw / 2, tag_y), tag_text, font=tag_font, fill=accent)

    title_size = max(30, round(w * 0.057))
    title_y = tag_y + tag_size * 2
    wrapped = _wrap_arabic(draw, title, title_size, w - round(w * 0.148))
    y_after = _draw_multiline_centered(draw, wrapped, title_size, GRC["navy"], w / 2, title_y, round(title_size * 1.27))

    if details:
        img, draw, y_after = _grc_details_panel(img, details, y_after + h * 0.014, canvas=canvas)

    if date_str:
        d_text = _ar(f"{date_str}")
        d_font = _font(FONT_REGULAR, max(18, round(w * 0.0215)))
        dw = draw.textlength(d_text, font=d_font)
        draw.text((w / 2 - dw / 2, h - h * 0.09), d_text, font=d_font, fill=GRC["gray"])

    _grc_source_line(draw, source, canvas=canvas)
    return img


def _grc_draw_multiline_right(draw, lines, size, fill, right_x, start_y, line_height):
    y = start_y
    for line in lines:
        rendered = _ar(line)
        w = _measure_mixed_line(draw, rendered, size)
        _draw_mixed_line(draw, rendered, size, fill, right_x - w, y)
        y += line_height
    return y


def grc_design_detailed(title, tag, urgent, body_text, date_str="", source="",
                         section_header="التفاصيل", canvas: tuple[int, int] = (WIDTH, HEIGHT),
                         bg_image=None) -> Image.Image:
    """تصميم GRC 3: عنوان + رأس قسم + فقرة كاملة محاذاة يمين + أيقونة + تذييل،
    نظير design_detailed السيبراني لكن بالهوية البيضاء الرسمية."""
    w, h = canvas
    accent = GRC["red_critical"] if urgent else GRC["gold"]

    if bg_image is not None:
        img = _fit_background_to_canvas(bg_image, canvas=canvas)
        img = _grc_lighten_overlay(img)
        draw = ImageDraw.Draw(img)
    else:
        img, draw = _grc_base_canvas(canvas)
        _grc_frame(draw, GRC["gold"], canvas)

    right_margin = w * 0.072
    right_x = w - right_margin

    tag_size = max(20, round(w * 0.024))
    tag_font = _font(FONT_SEMIBOLD, tag_size)
    tag_text = _ar(tag)
    tw = draw.textlength(tag_text, font=tag_font)
    pad = round(w * 0.02)
    badge_h = round(tag_size * 1.7)
    badge_top = h * 0.04
    draw.rounded_rectangle([right_x - tw - pad, badge_top, right_x + pad, badge_top + badge_h],
                            radius=6, fill=GRC["navy"])
    draw.text((right_x - tw, badge_top + badge_h * 0.2), tag_text, font=tag_font, fill=GRC["white"])

    title_size = max(34, round(w * 0.05))
    title_y = badge_top + badge_h + h * 0.03
    wrapped_title = _cap_lines(_wrap_arabic(draw, title, title_size, w - right_margin * 2), 2)
    y_after = _grc_draw_multiline_right(draw, wrapped_title, title_size, GRC["navy"], right_x, title_y, round(title_size * 1.3))

    section_y = y_after + h * 0.03
    section_size = max(22, round(w * 0.028))
    section_font = _font(FONT_SEMIBOLD, section_size)
    section_text = _ar(section_header)
    sw = _measure_mixed_line(draw, section_text, section_size)
    dot_r = section_size * 0.24
    draw.text((right_x - sw, section_y), section_text, font=section_font, fill=GRC["navy"])
    draw.rectangle([right_x - sw - dot_r * 3.4, section_y + section_size * 0.15,
                     right_x - sw - dot_r * 1.4, section_y + section_size * 0.15 + dot_r * 2], fill=GRC["gold"])

    body_size = max(24, round(w * 0.0285))
    body_y = section_y + h * 0.052
    wrapped_body = _cap_lines(_wrap_arabic(draw, body_text, body_size, w - right_margin * 2), 8)
    body_line_h = round(body_size * 1.55)
    y_after_body = _grc_draw_multiline_right(draw, wrapped_body, body_size, GRC["navy_soft"], right_x, body_y, body_line_h)

    footer_zone_top = h - h * 0.135
    icon_size = min(w, h) * 0.14
    icon_cy = max((y_after_body + footer_zone_top) / 2, y_after_body + icon_size * 0.7)
    icon_cy = min(icon_cy, footer_zone_top - icon_size * 0.7)
    icon_fn = _grc_icon_for(tag)
    icon_fn(draw, w / 2, icon_cy, icon_size, accent, width=max(4, round(w * 0.0056)))

    if date_str:
        d_text = _ar(f"تاريخ الإصدار: {date_str}")
        d_font = _font(FONT_SEMIBOLD, max(18, round(w * 0.0215)))
        dw = draw.textlength(d_text, font=d_font)
        pad2 = round(w * 0.022)
        footer_y = h - h * 0.075
        draw.rounded_rectangle([right_x - dw - pad2 * 2, footer_y, right_x, footer_y + round(w * 0.046)],
                                radius=round(w * 0.023), fill=GRC["navy"])
        draw.text((right_x - dw - pad2, footer_y + round(w * 0.009)), d_text, font=d_font, fill=GRC["white"])

    _grc_source_line(draw, source, canvas=canvas)
    return img


def generate_grc_designs(content: dict, out_dir: str, ai_backgrounds: list | None = None) -> list[str]:
    """يولّد 3 تصاميم GRC (إنستغرام 1080×1350) ويحفظها كـ PNG.

    ai_backgrounds: قائمة اختيارية من حتى 3 صور PIL (خلفيات فنية بدون نص، من
    Nano Banana/Gemini مثلاً) — كل عنصر يقابل أحد التصاميم الثلاثة بالترتيب.
    أي عنصر مفقود أو None يُستخدم له الرسم المحلي الأبيض كبديل تلقائي."""
    os.makedirs(out_dir, exist_ok=True)
    title = content["image_title"]
    tag = content["classification"]
    urgent = content.get("urgency") == "عاجل"
    details_text = content.get("image_summary") or content.get("summary", "")
    date_str = _arabic_date()
    source = content.get("source", "")
    full_body = content.get("summary") or details_text

    bgs = list(ai_backgrounds or [])
    bg1 = bgs[0] if len(bgs) > 0 else None
    bg2 = bgs[1] if len(bgs) > 1 else None
    bg3 = bgs[2] if len(bgs) > 2 else None

    designs = [
        ("grc_1_standard" if bg1 is None else "grc_1_ai",
         grc_design_standard(title, tag, urgent, details_text, date_str, source, bg_image=bg1)),
        ("grc_2_highlight" if bg2 is None else "grc_2_ai",
         grc_design_highlight(title, tag, urgent, details_text, date_str, source, bg_image=bg2)),
        ("grc_3_detailed" if bg3 is None else "grc_3_detailed_ai",
         grc_design_detailed(title, tag, urgent, full_body, date_str, source, bg_image=bg3)),
    ]
    paths = []
    for name, img in designs:
        path = os.path.join(out_dir, f"{name}.png")
        img.save(path, "PNG", optimize=True)
        paths.append(path)
    return paths


def generate_grc_platform_designs(content: dict, out_dir: str, platform: str = "linkedin",
                                   ai_backgrounds: list | None = None) -> list[str]:
    """نسخة بمقاس منصة مخصص (مثل LinkedIn المربع 1080×1080) من نفس تصاميم GRC.
    يعيد استخدام نفس ai_backgrounds المُولَّدة أصلاً لإنستغرام (إن وُجدت) بقصّ
    مختلف يناسب مقاس المنصة الجديدة — دون أي استدعاء إضافي للنموذج."""
    from image_generator import PLATFORM_SIZES
    if platform not in PLATFORM_SIZES:
        raise ValueError(f"منصة غير معروفة: {platform}")
    canvas = PLATFORM_SIZES[platform]

    os.makedirs(out_dir, exist_ok=True)
    title = content["image_title"]
    tag = content["classification"]
    urgent = content.get("urgency") == "عاجل"
    details_text = content.get("image_summary") or content.get("summary", "")
    date_str = _arabic_date()
    source = content.get("source", "")
    full_body = content.get("summary") or details_text

    bgs = list(ai_backgrounds or [])
    bg1 = bgs[0] if len(bgs) > 0 else None
    bg2 = bgs[1] if len(bgs) > 1 else None
    bg3 = bgs[2] if len(bgs) > 2 else None

    designs = [
        (f"{platform}_grc_1", grc_design_standard(title, tag, urgent, details_text, date_str, source, canvas=canvas, bg_image=bg1)),
        (f"{platform}_grc_2", grc_design_highlight(title, tag, urgent, details_text, date_str, source, canvas=canvas, bg_image=bg2)),
        (f"{platform}_grc_3", grc_design_detailed(title, tag, urgent, full_body, date_str, source, canvas=canvas, bg_image=bg3)),
    ]
    paths = []
    for name, img in designs:
        path = os.path.join(out_dir, f"{name}.png")
        img.save(path, "PNG", optimize=True)
        paths.append(path)
    return paths


if __name__ == "__main__":
    demo = {
        "image_title": "معيار ISO 27001:2026 يضيف متطلبات ذكاء اصطناعي",
        "classification": "إطار عمل جديد",
        "urgency": "مرتفع",
        "image_summary": "نسخة محدّثة من المعيار تُلزم المؤسسات بضوابط حوكمة جديدة للذكاء الاصطناعي.",
        "summary": "أصدرت المنظمة الدولية للمعايير تحديثاً على ISO 27001 يضيف متطلبات صريحة لحوكمة أنظمة الذكاء الاصطناعي داخل أطر إدارة أمن المعلومات، ما يتطلب من المؤسسات المعتمدة مراجعة سياساتها خلال 12 شهراً.",
        "source": "ISO",
    }
    out = generate_grc_designs(demo, "/tmp/grc_demo")
    print(out)
