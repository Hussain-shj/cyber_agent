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

# أقرب مقاس مدعوم من OpenAI لنسبة 1080x1350 (4:5) هو الوضع الرأسي 1024x1536
GEN_SIZE = "1024x1536"


def _build_prompt(classification: str, urgent: bool, visual_concept: str = "", keywords: str = "") -> str:
    """يبني برومبت إنجليزياً لخلفية فنية فقط (بدون أي نص) بهوية سيبرانية داكنة،
    يمنع صراحة أي كتابة أو أشخاص حقيقيين في الصورة. عند توفر visual_concept
    (وصف كتبه Claude خصيصاً لهذا الخبر بعد فهمه)، يصبح هو محور الصورة الرئيسي
    بدل وصف عام يعتمد فقط على التصنيف — هذا ما يجعل التصميم فعلياً 'مبنياً
    على تحليل Anthropic API للخبر' وليس قالباً ثابتاً لكل الأخبار من نفس النوع."""
    mood = "dramatic red and dark tones, alarming urgent atmosphere" if urgent else \
           "cyan and deep blue tones, professional and calm atmosphere"

    if visual_concept:
        subject = visual_concept.strip().rstrip(".") + ". "
    elif keywords:
        subject = f"An abstract visual motif related to: {keywords}. "
    else:
        subject = "An abstract cybersecurity network and data-protection motif. "

    base = (
        f"{subject}"
        "Rendered as a modern minimalist digital illustration background, "
        f"{mood}, dark navy and black gradient background, glowing neon accent lines, "
        "abstract digital network nodes, circuit patterns, subtle particle sparkles, "
        "high-end tech magazine style, cinematic lighting, 4k quality. "
        "IMPORTANT: absolutely no text, no letters, no numbers, no words, no logos, "
        "no watermarks anywhere in the image. No real human faces or realistic people; "
        "any figure, if present at all, must be a fully abstract/geometric silhouette only. "
        "Pure abstract/illustrative background only."
    )
    return base


def generate_background(classification: str, urgent: bool, visual_concept: str = "",
                         keywords: str = "", api_key: str | None = None,
                         quality: str = "medium") -> Image.Image:
    """يولّد صورة خلفية (PIL Image) عبر OpenAI Images API. يرمي استثناءً عند الفشل
    ليتمكن المستدعي من الرجوع لخلفية Pillow المحلية كحل احتياطي (fallback).

    visual_concept: وصف بصري محدد كتبه Claude لهذا الخبر تحديداً (الحقل
    visual_concept من content_generator.py) — يُفضَّل دائماً عند توفره."""
    client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
    prompt = _build_prompt(classification, urgent, visual_concept, keywords)

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
                          api_key: str | None = None, quality: str = "medium") -> list:
    """يولّد خلفية فنية منفصلة لكل فكرة بصرية في القائمة (حتى 3 عادةً). عند
    فشل توليد فكرة معيّنة، يُدرَج None في مكانها بدل رفع استثناء يوقف البقية
    — بحيث تحصل على أكبر عدد ممكن من الخلفيات الناجحة حتى لو فشلت واحدة."""
    results = []
    for concept in visual_concepts:
        try:
            results.append(generate_background(
                classification, urgent, visual_concept=concept, api_key=api_key, quality=quality,
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
