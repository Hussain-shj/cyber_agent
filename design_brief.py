"""
design_brief.py
توجيه التصميم الموحّد (Design Brief) الذي يجب أن يبدأ به أي برومبت يُرسَل
لأي نموذج توليد صور (OpenAI أو Nano Banana/Gemini أو غيرهما مستقبلاً) —
مكان واحد للتعديل بدل تكراره في كل ملف مزوّد على حدة.

الأصل: طلب المستخدم بالعربية —
"كمصمم محترف في الأمن السيبراني وGRC، صمم لي تصميماً يصلح لينكدإن، يكون واضح
وبألوان هادئة، تعبر بشكل مباشر عن النص المذكور أدناه، استخدم صوراً تعبر عن
الخبر كأشخاص أو أجهزة أو هوية الشركة المنبثقة من الخبر."
"""

DESIGNER_BRIEF_PREFIX = (
    "You are a professional visual designer specializing in cybersecurity and "
    "GRC (governance, risk & compliance) content. Design a clear, LinkedIn-ready "
    "visual using calm, muted colors that directly expresses the news described "
    "below. Use imagery that reflects the actual story — such as people, devices "
    "or equipment, or visual cues tied to the real company/technology involved "
    "(e.g. matching device styling or color scheme) — rather than a generic "
    "unrelated motif. "
)

# تحذير صارم منفصل ضد النص داخل الصورة — مضاف بعد ملاحظات فعلية بأن نماذج
# الصور تتجاهل أحياناً تعليمة "no text" العامة عندما يتضمن وصف المشهد عناصر
# UI أو بطاقات تلمّح لتصنيفات/فئات محددة (مثل "بطاقات تعرض: كذا وكذا")،
# فيكتب النموذج تلك الأسماء كتسميات فعلية داخل الصورة، وغالباً بتهجئة خاطئة.
NO_TEXT_WARNING = (
    "CRITICAL constraint, follow exactly: the image must contain ZERO text of "
    "any kind — no words, no labels, no captions, no category names, no numbers, "
    "no acronyms, not even single letters, anywhere in the image, including "
    "inside or beside any card, panel, icon, or UI element. If your scene "
    "concept involves cards, panels, or dashboard-style elements, render them "
    "completely empty of any label or caption — represent each concept through "
    "pure visual symbolism (shape, icon, color) only, never through a written "
    "word. Do not attempt to spell out any term related to the story. All real "
    "text (headline, details, source) will be added afterward with precise "
    "typography — your job is the image only. "
)

# ملاحظة حقوق ملكية فكرية: لا نطلب من النموذج رسم شعار شركة حقيقي حرفياً (غالباً
# ما تُرسَم الشعارات المسجَّلة بشكل مشوّه وغير دقيق من نماذج الصور الحالية، وقد
# يُنسب خطأً للشركة المعنية إن نُشر). بدلاً من ذلك نطلب إشارة بصرية للهوية
# (شكل الجهاز، الألوان المميزة، السياق) دون إعادة إنتاج الشعار الفعلي.
BRAND_GUIDANCE = (
    "If a specific real company or product is mentioned, you may reflect its "
    "visual identity contextually (device shape, characteristic colors, "
    "industry setting) but do NOT attempt to reproduce its exact real logo or "
    "trademark mark, since AI models typically render logos inaccurately — "
    "keep any branding references stylized and abstract rather than literal. "
)
