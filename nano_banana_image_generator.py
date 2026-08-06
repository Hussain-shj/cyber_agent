"""
nano_banana_image_generator.py
يولّد خلفية فنية (بدون أي نص مكتوب داخلها) عبر Gemini Image API من Google
(المعروف مجتمعياً باسم "Nano Banana")، خصيصاً بأسلوب أبيض/فاتح رسمي مؤسسي
يناسب هوية GRC البصرية — نظير openai_image_generator.py لكن بمزوّد مختلف
ومزاج بصري مختلف (فاتح بدل داكن).

يحتاج مفتاح API من Google AI Studio (aistudio.google.com → Get API key)،
مجاني للتجربة (حتى مئات الصور يومياً في الفئة المجانية وقت كتابة هذا الكود،
تحقق من صفحة أسعار Google الحالية لأنها تتغيّر بمرور الوقت).

السبب في فصل الخلفية عن النص: نماذج توليد الصور الحالية لا تزال ترتكب أخطاء
إملائية متكررة عند كتابة نصوص عربية داخل الصورة، بينما النص المرسوم عبر Pillow
هنا مضمون الصحة 100% (تم التحقق من تغطية الحروف برمجياً).
"""

import os
from io import BytesIO

from google import genai
from PIL import Image

from design_brief import BRAND_GUIDANCE, DESIGNER_BRIEF_PREFIX

# النموذج الافتراضي (يُعرف مجتمعياً باسم Nano Banana). يمكن تبديله بنموذج أحدث
# عبر متغير البيئة NANO_BANANA_MODEL دون تعديل الكود، لأن أسماء نماذج Google
# تتغيّر بمرور الوقت (مثل الجيل الأحدث "Nano Banana Pro"/"Nano Banana 2").
DEFAULT_MODEL = "gemini-2.5-flash-image"


def _build_prompt(classification: str, urgent: bool, visual_concept: str = "", keywords: str = "") -> str:
    """يبني برومبت إنجليزياً لخلفية فنية فقط (بدون أي نص) بأسلوب بطاقات UI
    عائمة حديثة (مستوحى من مرجع صورة زوّدنا بها المستخدم)، بهوية GRC الهادئة/
    الفاتحة الرسمية بدل الأزرق النيون الأصلي في المرجع. يبدأ دائماً بتوجيه
    "المصمم المحترف" الثابت (DESIGNER_BRIEF) ثم مشهد مبني على تفاصيل الخبر —
    والبطاقات نفسها فارغة من أي نص عمداً، لأن Pillow يضيف النص العربي لاحقاً
    بدقة كاملة فوق هذه الخلفية."""
    mood = "warm gold and soft red accent tones over a calm, muted, soft-lit palette" \
        if urgent else \
        "soft navy and gold accents over a calm, muted, soft-lit palette"

    if visual_concept:
        subject = visual_concept.strip().rstrip(".") + ". "
    elif keywords:
        subject = f"An expressive editorial scene related to: {keywords}. "
    else:
        subject = "A calm, professional governance/compliance office scene. "

    base = (
        f"{DESIGNER_BRIEF_PREFIX}"
        f"{subject}"
        "Rendered in a modern SaaS/tech UI aesthetic: one or two floating "
        "glassmorphic card panels with soft rounded corners, subtle drop "
        "shadows, and gentle depth layering — like a premium product feature "
        "showcase. Each card contains ONLY a single centered icon relevant to "
        "the story (no text, no labels, no numbers inside the cards — text "
        "will be added separately with precise typography afterward). "
        f"Background: a soft gradient with a subtle interconnected hexagonal "
        f"wireframe/network-line pattern for depth, in {mood} (not neon blue "
        "or high-contrast tech colors). Leave clear open space around and "
        "below the card(s) for text overlay afterward. Elegant, premium, "
        "editorial — not cluttered. Tall portrait orientation composition, 4k quality. "
        f"{BRAND_GUIDANCE}"
        "If people are shown, they must be generic, non-identifiable, fictional-looking "
        "individuals (e.g. a compliance officer, an auditor, a boardroom) — never a real, "
        "named, or recognizable public figure. "
        "IMPORTANT: absolutely no text, no letters, no numbers, no words, no logos, "
        "no watermarks anywhere in the image."
    )
    return base


def generate_background(classification: str, urgent: bool, visual_concept: str = "",
                         keywords: str = "", api_key: str | None = None,
                         model: str | None = None) -> Image.Image:
    """يولّد صورة خلفية (PIL Image) عبر Gemini Image API. يرمي استثناءً عند
    الفشل ليتمكن المستدعي من الرجوع لخلفية Pillow المحلية كحل احتياطي.

    visual_concept: وصف بصري محدد كتبه Claude لهذا الموضوع تحديداً (حقل
    visual_concepts من content_generator_grc.py) — يُفضَّل دائماً عند توفره."""
    client = genai.Client(api_key=api_key or os.environ["GOOGLE_API_KEY"])
    prompt = _build_prompt(classification, urgent, visual_concept, keywords)
    model_name = model or os.environ.get("NANO_BANANA_MODEL", DEFAULT_MODEL)

    response = client.models.generate_content(model=model_name, contents=[prompt])

    for part in response.candidates[0].content.parts:
        inline_data = getattr(part, "inline_data", None)
        if inline_data is not None and inline_data.data:
            image_bytes = inline_data.data
            # بعض إصدارات الحزمة تعيد bytes مباشرة، وبعضها نصاً base64 — نتعامل مع الحالتين
            if isinstance(image_bytes, str):
                import base64
                image_bytes = base64.b64decode(image_bytes)
            return Image.open(BytesIO(image_bytes)).convert("RGB")

    raise RuntimeError("لم يُعِد Gemini أي بيانات صورة في الرد (رد نصي فقط على الأغلب).")


def generate_backgrounds(visual_concepts: list[str], classification: str, urgent: bool,
                          api_key: str | None = None, model: str | None = None) -> list:
    """يولّد خلفية فنية منفصلة لكل فكرة بصرية في القائمة (حتى 3 عادةً). عند
    فشل توليد فكرة معيّنة، يُدرَج None في مكانها بدل رفع استثناء يوقف البقية."""
    results = []
    for concept in visual_concepts:
        try:
            results.append(generate_background(
                classification, urgent, visual_concept=concept, api_key=api_key, model=model,
            ))
        except Exception:  # noqa: BLE001
            results.append(None)
    return results


if __name__ == "__main__":
    img = generate_background(
        "إطار عمل جديد", urgent=False,
        visual_concept="A formal white-background layout with an open certification "
                        "booklet and a gold wax seal, clean marble surface",
    )
    img.save("/tmp/nano_banana_test.png")
    print("saved /tmp/nano_banana_test.png", img.size)
