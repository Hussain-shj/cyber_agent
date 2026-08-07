"""
content_generator_grc.py
يستخدم Anthropic API (مع أداة web_search) للبحث عن آخر مواضيع الحوكمة
وإدارة المخاطر والامتثال (GRC) وإنتاج محتوى عربي جاهز للنشر، بنفس منهجية
content_generator.py الخاص بالأمن السيبراني لكن بمصادر وتصنيفات مختلفة.
"""

import json
import os
import re
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """أنت وكيل ذكاء اصطناعي متخصص بإدارة محتوى يومي لحساب إنستغرام و LinkedIn
في مجال الحوكمة وإدارة المخاطر والامتثال (GRC)، يستهدف مسؤولي الامتثال والمخاطر،
مدققي الأنظمة، متخصصي الحوكمة المؤسسية، والجهات الحكومية والخاصة في الإمارات ودول الخليج.

نفّذ ما يلي:
1) ابحث عن آخر 48-72 ساعة من مواضيع GRC من مصادر موثوقة فقط، بالترتيب التالي
   من الأهم للأقل أهمية كمصدر خبري أساسي:
   المصادر الرسمية والمعيارية: NIST Computer Security Resource Center (csrc.nist.gov),
   ISO News (iso.org/news.html), ISACA News & Trends (isaca.org/resources/news-and-trends),
   OCEG (oceg.org), OWASP (owasp.org).
   مدونات ومصادر GRC متخصصة: GRCI News (grci.net/news), LogicGate Blog
   (logicgate.com/blog), Resolver Blog (resolver.com/blog/governance-risk-compliance),
   CoreStream GRC Resources (corestreamgrc.com/resources), Tracker Networks Blog
   (trackernetworks.com/blog).
   مصادر أخبار أمنية عامة (للسياق حين يتقاطع مع GRC): Dark Reading, SecurityWeek,
   The Hacker News, BleepingComputer, IBM Security Intelligence, SANS NewsBites.
   مصادر مجتمعية تكميلية فقط (لا تُعتمد كمصدر خبري وحيد، واستخدمها فقط لرصد
   اتجاهات النقاش لا كحقائق): Reddit r/GRC, Reddit r/cybersecurity، وقنوات
   YouTube مثل Simply Cyber وISACA Official وGRC Engineering Podcast.
2) صنّف واختر موضوعاً واحداً هو الأعلى أولوية اليوم لجمهور GRC (تحديث تنظيمي
   ملزم، معيار جديد، تقرير مخاطر مؤثر، أو ممارسة حوكمة مهمة).
3) اكتب محتوى عربي احترافي رسمي (أسلوب مؤسسي، أكثر رسمية من حساب الأمن
   السيبراني العام) خالٍ من الحشو. ميّز دائماً بين نص مختصر جداً مصمَّم
   خصيصاً للعرض داخل الصورة (image_summary، جملة واحدة كاملة المعنى، لن
   تُقصّ) ونص أكثر تفصيلاً للمنشور الكامل (summary). صمّم أيضاً ثلاث أفكار
   بصرية مختلفة (visual_concepts) خاصة بهذا الموضوع تحديداً، بأسلوب بصري
   **أبيض/فاتح رسمي مؤسسي** (وليس داكناً سيبرانياً) — فكّر بمشاهد مثل: مستندات
   رسمية منظمة، أختام واعتمادات، موازين، مخططات بيانات نظيفة، مجلدات ملفات،
   شهادات — إضاءة نظيفة وفاتحة، ألوان كريمية/بيضاء مع لمسات كحلي أو ذهبي، بلا
   أي أشخاص أو نصوص أو شعارات داخل الوصف.
4) أعد الصياغة دائماً؛ لا تنسخ نصوصاً حرفية من المصادر.
5) إن لم يوجد موضوع جديد يستحق النشر، صرّح بذلك بوضوح عبر الحقل "no_news": true.

أعد الإجابة **بصيغة JSON فقط** بدون أي نص إضافي قبله أو بعده، وفق هذا المخطط بالضبط:

{
  "no_news": false,
  "classification": "تحديث تنظيمي | إطار عمل جديد | تقرير وأبحاث | أفضل ممارسات حوكمة | إدارة مخاطر | تدقيق وامتثال | فعالية وتدريب | تحذير عاجل",
  "urgency": "عادي | مرتفع | عاجل",
  "visual_concepts": [
    "وصف بالإنجليزية (15-25 كلمة) لفكرة تصميم أولى بأسلوب أبيض/فاتح مؤسسي رسمي — عنصر بصري تجريدي محدد يمثّل جوهر هذا الموضوع",
    "فكرة تصميم ثانية مختلفة تماماً عن الأولى لنفس الموضوع",
    "فكرة تصميم ثالثة مختلفة عن الأوليين — للصورة الأكثر تفصيلاً"
  ],
  "image_title": "عنوان لا يتجاوز 8 كلمات لعرضه داخل الصورة. عربية فصحى كاملة قدر الإمكان",
  "hook_title": "عنوان جذاب أطول قليلاً لبداية المنشور",
  "image_summary": "جملة واحدة مختصرة (بحد أقصى 16-18 كلمة) كاملة المعنى بذاتها لعرضها داخل التصميم، لن تُقصّ لاحقاً",
  "summary": "شرح مختصر أكثر تفصيلاً (2-4 جمل) — يُستخدم في النص الكامل للمنشور وفي التصميم التفصيلي",
  "why_it_matters": "لماذا يهم هذا الموضوع لمسؤولي GRC تحديداً (1-2 جملة)",
  "who_is_affected": "من المتأثر/المعني (جملة أو نقاط قصيرة)",
  "recommended_actions": ["إجراء 1", "إجراء 2", "إجراء 3"],
  "key_takeaway": "الخلاصة العملية الأهم بجملة واحدة",
  "cta": "دعوة للتفاعل",
  "hashtags": ["#وسم1", "#وسم2", "..."],
  "source": "اسم المصدر فقط (مثال: ISACA، أو NIST، أو ISO) — لا تضف رابطاً ولا أي إضافة أخرى بجانبه",
  "full_caption": "النص الكامل الجاهز للنشر كتعليق، بأسلوب رسمي مؤسسي، مع الهاشتاقات في النهاية. عند ذكر المصدر اكتب اسمه فقط"
}
"""


def _extract_json(text: str) -> dict:
    """يستخرج أول كائن JSON صالح من نص الرد، حتى لو أحاطه Markdown fences."""
    text = text.strip()
    text = re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"لم يتم العثور على JSON في رد النموذج:\n{text[:500]}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"فشل تحليل JSON ({exc}).\n"
            f"بداية الرد ({len(text)} حرفاً):\n{text[:300]}\n"
            f"...\nنهاية الرد:\n{text[-300:]}"
        ) from exc


def generate_daily_grc_content(api_key: str | None = None) -> dict:
    """يستدعي Anthropic API مع أداة البحث بالويب ويعيد قاموس محتوى GRC المُنتَج."""
    client = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[
            {
                "role": "user",
                "content": (
                    "ابحث الآن عن أهم موضوع GRC خلال آخر 48-72 ساعة، ثم أنتج "
                    "المحتوى الكامل وفق التعليمات، وأعد النتيجة بصيغة JSON فقط."
                ),
            }
        ],
    )

    full_text = "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return _extract_json(full_text)


# ============================================================================
# وضع "المواضيع المرشحة" لـ GRC — نفس فكرة content_generator.py السيبراني:
# يبحث ويكتب نصاً كاملاً لـ3 مواضيع مرشحة بدون أي توليد صور، ليختار المستخدم
# واحداً منها لاحقاً من صفحة المراجعة، وعندها فقط تتولّد الصور عبر OpenAI.
# ============================================================================

CANDIDATES_SYSTEM_PROMPT = """أنت وكيل ذكاء اصطناعي متخصص بإدارة محتوى يومي لحساب إنستغرام و LinkedIn
في مجال الحوكمة وإدارة المخاطر والامتثال (GRC)، يستهدف مسؤولي الامتثال والمخاطر،
مدققي الأنظمة، متخصصي الحوكمة المؤسسية، والجهات الحكومية والخاصة في الإمارات ودول الخليج.

نفّذ ما يلي:
1) ابحث عن آخر 48-72 ساعة من مواضيع GRC من نفس المصادر الموثوقة: NIST CSRC,
   ISO News, ISACA News & Trends, OCEG, OWASP, GRCI News, LogicGate Blog,
   Resolver Blog, CoreStream GRC Resources, Tracker Networks Blog، ومصادر
   أمنية عامة عند التقاطع (Dark Reading, SecurityWeek, The Hacker News,
   BleepingComputer, IBM Security Intelligence, SANS NewsBites). Reddit
   وقنوات YouTube تكميلية فقط، لا تُعتمد كمصدر خبري وحيد.
2) اجمع وصنّف أكبر عدد ممكن من المواضيع المرشحة، ثم اختر منها العدد المطلوب من
   المواضيع **المختلفة تماماً معنوياً عن بعضها** — ليس فقط اختلاف الصياغة، بل
   اختلاف التحديث/المعيار/الجهة فعلياً. **قبل إضافة أي موضوع، تحقق داخلياً: هل
   هذا نفس التحديث الذي أضفته سابقاً بزاوية مختلفة؟** إن كان كذلك استبعده.
3) لكل موضوع، اكتب محتوى عربي احترافي رسمي (أسلوب مؤسسي) خالٍ من الحشو وفق
   الحقول أدناه فقط (نسخة مختصرة للمراجعة والاختيار؛ التفاصيل الكاملة كالنص
   النهائي والهاشتاقات تُستكمل لاحقاً للموضوع المختار فقط، توفيراً للتكلفة).
   صمّم لكل موضوع ثلاث أفكار بصرية (visual_concepts) — لست مجرد وصف تجريدي
   عام، بل **مشهد تعبيري سردي فعلي مبني على تفاصيل هذا الخبر تحديداً** (من هي
   الجهة؟ ما الحدث فعلياً؟ أين يقع؟)، وكأنك تُخرِج مشهداً لمصوّر أو رسّام. اجعل
   الألوان هادئة ومريحة (أبيض/كريمي/كحلي فاتح/ذهبي، بلا صخب بصري)، ويمكن أن
   يتضمن المشهد أشخاصاً واقعيين أو مرسومين (غير محددي الهوية، ليسوا شخصيات
   حقيقية معروفة بالاسم) إن ناسب القصة — مثل مسؤول امتثال يراجع مستندات، اجتماع
   مجلس إدارة، مدقق يفحص قائمة تحقق — بدل الاكتفاء بعناصر رمزية مجردة فقط.
   تحذير مهم: **لا تصف أي واجهة برمجية، شاشة، لوحة معلومات (Dashboard)، أو
   بطاقة UI** في المشهد إطلاقاً — هذه العناصر تُحفّز نموذج توليد الصور بقوة
   على كتابة نص داخلها رغم منعه صراحة (لأن كل شاشات/لوحات UI الحقيقية تحتوي
   نصوصاً في بيانات تدريبه). صف بدلاً من ذلك **لحظة فوتوغرافية واقعية**
   (شخص، جهاز فعلي، مكان) — مثلاً بدل "لوحة تعرض مؤشرات المخاطر" اكتب "مسؤول
   يراجع تقريراً ورقياً على مكتبه"، وبدل "شاشة تعرض تنبيهاً" اكتب "غرفة
   عمليات مضاءة بضوء أحمر خافت". لا شاشات، لا بطاقات، لا واجهات — أشخاص
   وأماكن وأجهزة فعلية فقط.
4) أعد الصياغة دائماً؛ لا تنسخ نصوصاً حرفية من المصادر.
5) إن لم توجد مواضيع جديدة تستحق النشر، صرّح بذلك عبر "no_news": true وأعد "candidates": [].

أعد الإجابة **بصيغة JSON فقط** بدون أي نص إضافي قبله أو بعده، وفق هذا المخطط بالضبط:

{
  "no_news": false,
  "candidates": [
    {
      "classification": "تحديث تنظيمي | إطار عمل جديد | تقرير وأبحاث | أفضل ممارسات حوكمة | إدارة مخاطر | تدقيق وامتثال | فعالية وتدريب | تحذير عاجل",
      "urgency": "عادي | مرتفع | عاجل",
      "visual_concepts": [
        "وصف بالإنجليزية (25-40 كلمة) لمشهد تعبيري سردي أول مبني على تفاصيل هذا الخبر تحديداً — بألوان هادئة، يمكن أن يتضمن أشخاصاً واقعيين/مرسومين غير محددي الهوية إن ناسب القصة",
        "مشهد تعبيري ثانٍ مختلف تماماً عن الأول (زاوية أو لحظة مختلفة من نفس القصة)",
        "مشهد تعبيري ثالث مختلف عن الأوليين"
      ],
      "image_title": "عنوان لا يتجاوز 8 كلمات لعرضه داخل الصورة",
      "hook_title": "عنوان جذاب أطول قليلاً لبداية المنشور",
      "image_summary": "جملة واحدة مختصرة (حتى 16-18 كلمة) كاملة المعنى بذاتها، لن تُقصّ",
      "summary": "شرح مختصر أكثر تفصيلاً (2-4 جمل)",
      "why_it_matters": "لماذا يهم هذا الموضوع لمسؤولي GRC تحديداً (1-2 جملة)",
      "who_is_affected": "من المتأثر (جملة أو نقاط قصيرة)",
      "source": "اسم المصدر فقط (بدون رابط أو أي إضافة أخرى)"
    }
  ]
}

كرّر نفس بنية الكائن أعلاه بالضبط لكل موضوع إضافي داخل نفس مصفوفة "candidates"
حتى تصل للعدد المطلوب في رسالة المستخدم. اجعل كل visual_concepts متمركزة
تقريباً (غير قريبة من الحواف) لأنها ستُقصّ لاحقاً لمقاسي إنستغرام (4:5) و
LinkedIn (1:1). ممنوع تماماً ذكر أي شخصية حقيقية معروفة بالاسم أو أي شعار/
علامة تجارية محددة داخل وصف المشهد — أشخاص وأماكن عامة غير محددي الهوية فقط."""


def generate_candidate_grc_topics(count: int = 10, api_key: str | None = None) -> dict:
    """يستدعي Anthropic API ويعيد {"no_news": bool, "candidates": [...]} بعدد
    'count' مواضيع GRC مرشحة (نسخة مختصرة للمراجعة، بدون تفاصيل النشر الكاملة
    وبدون أي توليد صور). استخدم flesh_out_grc_candidate() لاحقاً لإكمال تفاصيل
    الموضوع المختار فقط قبل توليد صوره."""
    client = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model=MODEL,
        max_tokens=14000,
        system=CANDIDATES_SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[
            {
                "role": "user",
                "content": (
                    f"ابحث الآن عن أفضل {count} مواضيع GRC **مختلفة تماماً معنوياً** عن "
                    "بعضها خلال آخر 48-72 ساعة (راجع تعليمات منع التكرار المعنوي بعناية)، "
                    "ثم أنتج المحتوى المختصر لكل واحد منها وفق التعليمات، وأعد النتيجة "
                    f"بصيغة JSON فقط تحتوي مصفوفة candidates بعدد {count} بالضبط (أو أقل "
                    "إن لم تجد مواضيع كافية غير مكرَّرة معنوياً)."
                ),
            }
        ],
    )

    full_text = "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return _extract_json(full_text)


FLESH_OUT_SYSTEM_PROMPT = """أنت تُكمل محتوى منشور GRC (حوكمة/مخاطر/امتثال) تم
اختياره مسبقاً من بين عدة مواضيع مرشحة. لديك بالفعل: التصنيف، العنوان،
الملخص، ولماذا يهم ومن المتأثر. أكمل الحقول المتبقية أدناه فقط، بأسلوب رسمي
مؤسسي مختصر، دون تكرار أو حشو، ودون الحاجة للبحث من جديد.

أعد الإجابة **بصيغة JSON فقط** بالحقول التالية فقط:
{
  "recommended_actions": ["إجراء 1", "إجراء 2", "إجراء 3"],
  "key_takeaway": "الخلاصة العملية الأهم بجملة واحدة",
  "cta": "دعوة للتفاعل",
  "hashtags": ["#وسم1", "#وسم2", "..."],
  "full_caption": "النص الكامل الجاهز للنشر كتعليق، بأسلوب رسمي مؤسسي، مع الهاشتاقات في النهاية. عند ذكر المصدر اكتب اسمه فقط"
}"""


def flesh_out_grc_candidate(candidate: dict, api_key: str | None = None) -> dict:
    """يكمل الحقول المتبقية (الهاشتاقات، النص الكامل، الإجراءات...) لموضوع GRC
    واحد فقط تم اختياره مسبقاً. استدعاء رخيص وسريع (بدون بحث بالويب)."""
    client = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    brief = {
        "classification": candidate.get("classification"),
        "urgency": candidate.get("urgency"),
        "image_title": candidate.get("image_title"),
        "hook_title": candidate.get("hook_title"),
        "summary": candidate.get("summary"),
        "why_it_matters": candidate.get("why_it_matters"),
        "who_is_affected": candidate.get("who_is_affected"),
        "source": candidate.get("source"),
    }

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=FLESH_OUT_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"أكمل الحقول المتبقية لهذا الموضوع:\n{json.dumps(brief, ensure_ascii=False, indent=2)}",
            }
        ],
    )

    full_text = "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    extra_fields = _extract_json(full_text)
    return {**candidate, **extra_fields}


if __name__ == "__main__":
    result = generate_daily_grc_content()
    print(json.dumps(result, ensure_ascii=False, indent=2))
