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
2) اختر **أفضل 3 مواضيع مختلفة تماماً عن بعضها** (وليس موضوعاً واحداً) حسب
   أولويتها اليوم لجمهور GRC (تحديث تنظيمي ملزم، معيار جديد، تقرير مخاطر
   مؤثر، أو ممارسة حوكمة مهمة). لا تكرار لنفس الموضوع بصياغة مختلفة.
3) لكل موضوع من الثلاثة، اكتب محتوى عربي احترافي رسمي (أسلوب مؤسسي) خالٍ من
   الحشو، بنفس جودة واكتمال موضوع واحد عادي (كل الحقول المطلوبة أدناه لكل
   موضوع على حدة). صمّم لكل موضوع ثلاث أفكار بصرية (visual_concepts) بأسلوب
   **أبيض/فاتح رسمي مؤسسي** (مستندات، أختام، موازين، شهادات — بلا أشخاص أو
   نصوص أو شعارات).
4) أعد الصياغة دائماً؛ لا تنسخ نصوصاً حرفية من المصادر.
5) إن لم توجد مواضيع جديدة تستحق النشر، صرّح بذلك عبر "no_news": true وأعد "candidates": [].

أعد الإجابة **بصيغة JSON فقط** بدون أي نص إضافي قبله أو بعده، وفق هذا المخطط بالضبط
(لاحظ: "candidates" مصفوفة تحتوي 3 عناصر بالضبط):

{
  "no_news": false,
  "candidates": [
    {
      "classification": "تحديث تنظيمي | إطار عمل جديد | تقرير وأبحاث | أفضل ممارسات حوكمة | إدارة مخاطر | تدقيق وامتثال | فعالية وتدريب | تحذير عاجل",
      "urgency": "عادي | مرتفع | عاجل",
      "visual_concepts": [
        "وصف بالإنجليزية (15-25 كلمة) لفكرة تصميم أولى بأسلوب أبيض/فاتح مؤسسي رسمي",
        "فكرة تصميم ثانية مختلفة تماماً عن الأولى",
        "فكرة تصميم ثالثة مختلفة عن الأوليين"
      ],
      "image_title": "عنوان لا يتجاوز 8 كلمات لعرضه داخل الصورة",
      "hook_title": "عنوان جذاب أطول قليلاً لبداية المنشور",
      "image_summary": "جملة واحدة مختصرة (حتى 16-18 كلمة) كاملة المعنى بذاتها، لن تُقصّ",
      "summary": "شرح مختصر أكثر تفصيلاً (2-4 جمل)",
      "why_it_matters": "لماذا يهم هذا الموضوع لمسؤولي GRC تحديداً (1-2 جملة)",
      "who_is_affected": "من المتأثر (جملة أو نقاط قصيرة)",
      "recommended_actions": ["إجراء 1", "إجراء 2", "إجراء 3"],
      "key_takeaway": "الخلاصة العملية الأهم بجملة واحدة",
      "cta": "دعوة للتفاعل",
      "hashtags": ["#وسم1", "#وسم2", "..."],
      "source": "اسم المصدر فقط (بدون رابط أو أي إضافة أخرى)",
      "full_caption": "النص الكامل الجاهز للنشر كتعليق، بأسلوب رسمي مؤسسي، مع الهاشتاقات في النهاية"
    }
  ]
}

كرّر نفس بنية الكائن أعلاه بالضبط لكل من الموضوعين الآخرين داخل نفس مصفوفة
"candidates" حتى يصبح إجمالي عناصرها 3. اجعل كل visual_concepts متمركزة
تقريباً (غير قريبة من الحواف) لأنها ستُقصّ لاحقاً لمقاسي إنستغرام (4:5) و
LinkedIn (1:1)."""


def generate_candidate_grc_topics(count: int = 3, api_key: str | None = None) -> dict:
    """يستدعي Anthropic API ويعيد {"no_news": bool, "candidates": [...]} بعدد
    'count' مواضيع GRC مرشحة كاملة النص، بدون أي توليد صور."""
    client = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model=MODEL,
        max_tokens=10000,
        system=CANDIDATES_SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[
            {
                "role": "user",
                "content": (
                    f"ابحث الآن عن أفضل {count} مواضيع GRC مختلفة خلال آخر 48-72 ساعة، "
                    "ثم أنتج المحتوى الكامل لكل واحد منها وفق التعليمات، وأعد النتيجة "
                    "بصيغة JSON فقط تحتوي مصفوفة candidates."
                ),
            }
        ],
    )

    full_text = "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return _extract_json(full_text)


if __name__ == "__main__":
    result = generate_daily_grc_content()
    print(json.dumps(result, ensure_ascii=False, indent=2))
