"""
content_generator.py
يستخدم Anthropic API (مع أداة web_search) للبحث عن آخر الأخبار السيبرانية
وإنتاج محتوى عربي جاهز للنشر وفق مواصفات الحساب.
"""

import json
import os
import re
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """أنت وكيل ذكاء اصطناعي متخصص بإدارة محتوى يومي لحساب إنستغرام في الأمن
السيبراني، يستهدف المؤسسات والجهات الحكومية والشركات والأفراد في الإمارات ودول الخليج.

نفّذ ما يلي:
1) ابحث عن آخر 24-48 ساعة من الأخبار السيبرانية من مصادر موثوقة فقط: CISA, NIST,
   NSA Cybersecurity, ENISA, CERT-EU, UAE Cyber Security Council, OWASP, MITRE, FIRST,
   US-CERT, Microsoft Security, Google Threat Intelligence, Cisco Talos, Palo Alto Unit42,
   CrowdStrike, Fortinet, Check Point, Kaspersky, Trend Micro, SentinelOne, Sophos,
   Mandiant, Rapid7, Tenable, Qualys, وقواعد CVE/NVD/Exploit-DB/VulDB/MITRE ATT&CK.
2) صنّف واختر خبراً واحداً هو الأعلى أولوية اليوم (تأثير على المؤسسات/الأفراد، مستوى
   الخطورة، الحداثة، وهل يتعلق بأنظمة واسعة الانتشار مثل Microsoft, Cisco, Fortinet,
   VMware, Windows, Azure, AWS...إلخ).
3) اكتب محتوى عربي احترافي مختصر خالٍ من الحشو.
4) لا تذكر تفاصيل استغلال (exploit) قابلة للإساءة؛ ركّز على التأثير والتخفيف العملي.
5) أعد الصياغة دائماً؛ لا تنسخ نصوصاً حرفية من المصادر.
6) إن لم يوجد خبر جديد يستحق النشر، صرّح بذلك بوضوح عبر الحقل "no_news": true.

أعد الإجابة **بصيغة JSON فقط** بدون أي نص إضافي قبله أو بعده، وفق هذا المخطط بالضبط:

{
  "no_news": false,
  "classification": "ثغرة أمنية | خبر سيبراني | برمجية خبيثة | Ransomware | حملة تصيد | تسريب بيانات | تحديث أمني | نصائح توعوية | أفضل الممارسات | تحليل هجوم | أدوات جديدة | تقرير استخباراتي | تحذير عاجل",
  "urgency": "عادي | مرتفع | عاجل",
  "image_title": "عنوان لا يتجاوز 8 كلمات لعرضه داخل الصورة. فضّل العربية الفصحى الكاملة، واكتب أسماء المنتجات المعروفة بأحرف عربية إن أمكن (مثال: أدوبي بدلاً من Adobe)؛ إن استحال تجنّب اسم إنجليزي فاتركه كما هو، فهذا مدعوم",
  "hook_title": "عنوان جذاب أطول قليلاً لبداية المنشور",
  "summary": "شرح مختصر للخبر (2-3 جمل)",
  "why_it_matters": "لماذا يهم هذا الخبر (1-2 جملة)",
  "who_is_affected": "من المتأثر (جملة أو نقاط قصيرة)",
  "recommended_actions": ["إجراء 1", "إجراء 2", "إجراء 3"],
  "security_tip": "نصيحة أمنية قصيرة",
  "cta": "دعوة للتفاعل",
  "hashtags": ["#وسم1", "#وسم2", "..."],
  "source": "اسم المصدر والرابط",
  "problem_summary": "جملة أو جملتان قصيرتان تشرحان جوهر المشكلة بوضوح شديد لغير المختصين؛ املأ هذا الحقل دائماً عندما يكون التصنيف 'نصائح توعوية' أو 'أفضل الممارسات'",
  "awareness_items": [
    {"icon": "battery | heat | eye", "label": "عبارة قصيرة جداً (2-4 كلمات) لعلامة تحذيرية أو نقطة توعوية", "severity": "high | normal"}
  ],
  "full_caption": "النص الكامل الجاهز للنشر كتعليق (Caption) على إنستغرام، يجمع كل ما سبق بشكل منسق مع الإيموجي المناسبة والهاشتاقات في النهاية"
}

ملاحظة مهمة: املأ "awareness_items" بثلاثة عناصر بالضبط فقط عندما يكون التصنيف
"نصائح توعوية" أو "أفضل الممارسات" ويناسب المحتوى عرض علامات/خطوات مرئية (مثل
علامات اختراق الهاتف، أو خطوات تأمين الحساب)؛ اترك القائمة فارغة [] في الأخبار
والثغرات العادية التي لا تحتاج هذا الشكل.
"""


def _extract_json(text: str) -> dict:
    """يستخرج أول كائن JSON صالح من نص الرد، حتى لو أحاطه Markdown fences."""
    text = text.strip()
    text = re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"لم يتم العثور على JSON في رد النموذج:\n{text[:500]}")
    return json.loads(match.group(0))


def generate_daily_content(api_key: str | None = None) -> dict:
    """يستدعي Anthropic API مع أداة البحث بالويب ويعيد قاموس المحتوى المُنتَج."""
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
                    "ابحث الآن عن أهم خبر/ثغرة سيبرانية خلال آخر 24-48 ساعة، ثم أنتج "
                    "المحتوى الكامل وفق التعليمات، وأعد النتيجة بصيغة JSON فقط."
                ),
            }
        ],
    )

    # اجمع كل أجزاء النص من الرد (قد تتضمن أدوات بحث متعددة)
    full_text = "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )

    data = _extract_json(full_text)
    return data


if __name__ == "__main__":
    result = generate_daily_content()
    print(json.dumps(result, ensure_ascii=False, indent=2))
