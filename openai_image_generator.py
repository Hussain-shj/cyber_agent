"""
openai_image_generator.py
يولّد خلفية فنية (بدون أي نص مكتوب داخلها) عبر OpenAI Images API، لاستخدامها
كخلفية يوضع فوقها لاحقاً نص عربي دقيق عبر Pillow (image_generator.py).

السبب في فصل الخلفية عن النص: نماذج توليد الصور الحالية لا تزال ترتكب أخطاء
إملائية متكررة عند كتابة نصوص عربية داخل الصورة، بينما النص المرسوم عبر Pillow
هنا مضمون الصحة 100% (تم التحقق من تغطية الحروف برمجياً).
"""

import base64
import os
from io import BytesIO

from openai import OpenAI
from PIL import Image

from design_brief import BRAND_GUIDANCE, DESIGNER_BRIEF_PREFIX, NO_TEXT_WARNING

# أقرب مقاس مدعوم من OpenAI لنسبة 1080x1350 (4:5) هو الوضع الرأسي 1024x1536
GEN_SIZE = "1024x1536"


def _build_prompt(classification: str, urgent: bool, visual_concept: str = "", keywords: str = "",
                   theme: str = "cyber") -> str:
    """يبني برومبت إنجليزياً لخلفية فنية فقط (بدون أي نص)، يمنع صراحة أي كتابة
    أو أشخاص حقيقيين معروفين بالاسم في الصورة. يبدأ دائماً بتوجيه التصميم
    الموحّد (design_brief.py) قبل أي شيء آخر. عند توفر visual_concept (وصف
    كتبه Claude خصيصاً لهذا الخبر بعد فهمه)، يصبح هو محور الصورة الرئيسي.

    theme: "cyber" (الافتراضي، هوية داكنة سيبرانية) أو "grc" (هوية هادئة/
    فاتحة رسمية، بلا أي عناصر واجهة UI لتجنّب إغراء النموذج بكتابة نص)."""
    if theme == "grc":
        mood = "warm gold and soft red accent tones over a calm, muted, soft-lit palette" if urgent else \
               "soft navy and gold accents over a calm, muted, soft-lit palette"
    else:
        mood = "deeper red accent tones over a calm, muted dark palette, serious composed atmosphere" if urgent else \
               "cyan and deep blue accent tones over a calm, muted dark palette, professional atmosphere"

    if visual_concept:
        subject = visual_concept.strip().rstrip(".") + ". "
    elif keywords:
        subject = f"An expressive editorial scene related to: {keywords}. "
    else:
        subject = "An abstract cybersecurity network and data-protection motif. " if theme != "grc" else \
                   "A calm, professional governance/compliance office scene. "

    if theme == "grc":
        style = (
            "Rendered as a calm, soft-lit editorial photograph or illustration — "
            "NOT a UI mockup, NOT a screen, NOT a dashboard, NOT an app interface, "
            "and containing no cards, panels, screens, or digital displays of any "
            "kind, since those visual forms strongly tend to imply on-screen text "
            "even when told not to. Depict the scene as a real physical moment "
            f"instead (a person, an object, a place) in {mood}. Soft natural or "
            "studio lighting, shallow depth of field, premium editorial magazine "
            "quality, tall portrait orientation composition, 4k. Leave clear open "
            "space near the top or bottom third for text overlay afterward. "
        )
    else:
        style = (
            "Rendered as a modern minimalist digital illustration background, "
            f"{mood}, dark navy and black gradient background, glowing neon accent lines, "
            "abstract digital network nodes, circuit patterns, subtle particle sparkles, "
            "high-end tech magazine style, cinematic lighting, 4k quality. "
        )

    base = (
        f"{DESIGNER_BRIEF_PREFIX}"
        f"{NO_TEXT_WARNING}"
        f"{subject}"
        f"{style}"
        f"{BRAND_GUIDANCE}"
        "IMPORTANT: absolutely no text, no letters, no numbers, no words, no "
        "watermarks anywhere in the image. If people are shown, they must be "
        "generic, non-identifiable, fictional-looking individuals — never a "
        "real, named, or recognizable public figure. "
        "Pure illustrative background only."
    )
    return base


def generate_background(classification: str, urgent: bool, visual_concept: str = "",
                         keywords: str = "", api_key: str | None = None,
                         quality: str = "medium", theme: str = "cyber") -> Image.Image:
    """يولّد صورة خلفية (PIL Image) عبر OpenAI Images API. يرمي استثناءً عند الفشل
    ليتمكن المستدعي من الرجوع لخلفية Pillow المحلية كحل احتياطي (fallback).

    visual_concept: وصف بصري محدد كتبه Claude لهذا الخبر تحديداً — يُفضَّل
    دائماً عند توفره. theme: "cyber" أو "grc" (انظر _build_prompt)."""
    client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
    prompt = _build_prompt(classification, urgent, visual_concept, keywords, theme=theme)

    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=GEN_SIZE,
        quality=quality,  # low | medium | high — نستخدم medium افتراضياً لتوازن التكلفة/الجودة
        n=1,
    )
    image_b64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_b64)
    return Image.open(BytesIO(image_bytes)).convert("RGB")


def generate_backgrounds(visual_concepts: list[str], classification: str, urgent: bool,
                          api_key: str | None = None, quality: str = "medium",
                          theme: str = "cyber") -> list:
    """يولّد خلفية فنية منفصلة لكل فكرة بصرية في القائمة (حتى 3 عادةً). عند
    فشل توليد فكرة معيّنة، يُدرَج None في مكانها بدل رفع استثناء يوقف البقية
    — بحيث تحصل على أكبر عدد ممكن من الخلفيات الناجحة حتى لو فشلت واحدة."""
    results = []
    for concept in visual_concepts:
        try:
            results.append(generate_background(
                classification, urgent, visual_concept=concept, api_key=api_key,
                quality=quality, theme=theme,
            ))
        except Exception:  # noqa: BLE001
            results.append(None)
    return results


if __name__ == "__main__":
    img = generate_background(
        "Ransomware", urgent=True,
        visual_concept="A network firewall device cracking apart with red digital tendrils spreading across its surface",
    )
    img.save("/tmp/ai_bg_test.png")
    print("saved /tmp/ai_bg_test.png", img.size)
