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


def _build_prompt(classification: str, urgent: bool, keywords: str = "") -> str:
    """يبني برومبت إنجليزياً لخلفية فنية فقط (بدون أي نص) بهوية سيبرانية داكنة،
    يمنع صراحة أي كتابة أو أشخاص حقيقيين في الصورة."""
    mood = "dramatic red and dark tones, alarming urgent atmosphere" if urgent else \
           "cyan and deep blue tones, professional and calm atmosphere"

    base = (
        "A modern minimalist cybersecurity-themed digital background illustration, "
        f"{mood}, dark navy and black gradient background, glowing neon accent lines, "
        "abstract digital network nodes, circuit patterns, subtle particle sparkles, "
        "high-end tech magazine style, cinematic lighting, 4k quality. "
    )
    if keywords:
        base += f"Visual motif related to: {keywords}. "
    base += (
        "IMPORTANT: absolutely no text, no letters, no numbers, no words, no logos, "
        "no watermarks anywhere in the image. No real human faces or people. "
        "Pure abstract/illustrative background only."
    )
    return base


def generate_background(classification: str, urgent: bool, keywords: str = "",
                         api_key: str | None = None, quality: str = "medium") -> Image.Image:
    """يولّد صورة خلفية (PIL Image) عبر OpenAI Images API. يرمي استثناءً عند الفشل
    ليتمكن المستدعي من الرجوع لخلفية Pillow المحلية كحل احتياطي (fallback)."""
    client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
    prompt = _build_prompt(classification, urgent, keywords)

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


if __name__ == "__main__":
    img = generate_background("تحذير عاجل", urgent=True, keywords="data breach, hacking")
    img.save("/tmp/ai_bg_test.png")
    print("saved /tmp/ai_bg_test.png", img.size)
