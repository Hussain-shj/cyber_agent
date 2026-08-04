"""
agent_runner.py
نقطة التشغيل الرئيسية للإيجنت اليومي:
  1) توليد المحتوى (بحث + تصنيف + تقييم + كتابة + 3 أفكار تصميم بصرية) عبر
     Anthropic API.
  2) توليد 3 خلفيات فنية عبر OpenAI Images API بناءً على الأفكار الثلاث التي
     كتبها Claude (إن توفر OPENAI_API_KEY)، ثم تركيب النصوص العربية فوقها؛
     مع رجوع تلقائي لكل تصميم لم تُتوفَّر له خلفية فنية إلى الرسم المحلي
     المجاني بـ Pillow.
  3) إعادة استخدام نفس الخلفيات الفنية الثلاث لتوليد نسخ بمقاسات منصات أخرى
     (LinkedIn المربع افتراضياً) دون أي تكلفة OpenAI إضافية.
  4) رفع كل الصور إلى GitHub للحصول على روابط عامة.
  5) نشر منشور واحد (أول تصميم) على Instagram — فقط إذا AUTO_PUBLISH=true.

الوضع الافتراضي هو "مراجعة" (Dry Run): يولّد كل شيء ويحفظه محلياً في posts/
بدون نشر فعلي، حتى تتم مراجعته يدوياً أولاً. للتفعيل الكامل، اضبط
AUTO_PUBLISH=true في متغيرات البيئة بعد أن تتأكد من جودة المخرجات.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from content_generator import generate_daily_content
from image_generator import generate_designs, generate_platform_designs
from github_uploader import upload_all, upload_image_to_github
from instagram_publisher import publish_post

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cyber-agent")


def run() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    out_dir = os.path.join("posts", stamp)

    log.info("1/4 — توليد المحتوى عبر Anthropic API (بحث + كتابة)...")
    content = generate_daily_content()

    if content.get("no_news"):
        log.info("لا يوجد خبر جديد يستحق النشر اليوم. إنهاء التشغيل.")
        return

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "content.json"), "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    log.info("تم إنتاج المحتوى: %s", content.get("hook_title"))

    log.info("2/4 — توليد التصاميم البصرية (3 أفكار من Claude → 3 خلفيات فنية)...")

    ai_backgrounds = []
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai_image_generator import generate_backgrounds
            concepts = content.get("visual_concepts") or []
            if concepts:
                log.info("أفكار Claude البصرية الثلاث: %s", concepts)
                ai_backgrounds = generate_backgrounds(
                    concepts,
                    content["classification"],
                    content.get("urgency") == "عاجل",
                    quality=os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
                )
                ok = sum(1 for b in ai_backgrounds if b is not None)
                log.info("تم توليد %d من %d خلفيات فنية بنجاح.", ok, len(concepts))
            else:
                log.warning("لا توجد visual_concepts في المحتوى — سيُستخدم التصميم المحلي بالكامل.")
        except Exception as exc:  # noqa: BLE001
            log.warning("فشل توليد الخلفيات الفنية (%s) — سيُستخدم التصميم المحلي بديلاً.", exc)
            ai_backgrounds = []

    image_paths = generate_designs(content, out_dir, ai_backgrounds=ai_backgrounds)
    log.info("تم حفظ التصاميم محلياً في: %s (لن تبقى بعد انتهاء الحاوية)", out_dir)

    # --- صور إضافية بمقاسات منصات أخرى (اختياري) ---
    # مفعّل افتراضياً لـ LinkedIn (مقاس مربع 1080×1080). يعيد استخدام نفس
    # ai_backgrounds أعلاه (بقصّ مختلف يناسب المقاس الجديد) دون أي تكلفة
    # OpenAI إضافية. يمكن تعطيله أو توسيعه عبر EXTRA_PLATFORMS (قائمة
    # مفصولة بفواصل من مفاتيح PLATFORM_SIZES في image_generator.py، مثل:
    # "linkedin,instagram_square").
    extra_platforms = [
        p.strip() for p in os.environ.get("EXTRA_PLATFORMS", "linkedin").split(",") if p.strip()
    ]
    for platform in extra_platforms:
        try:
            platform_paths = generate_platform_designs(
                content, out_dir, platform=platform, ai_backgrounds=ai_backgrounds,
            )
            image_paths += platform_paths
            log.info("تم توليد %d صور إضافية لمنصة '%s'.", len(platform_paths), platform)
        except Exception as exc:  # noqa: BLE001
            log.warning("فشل توليد صور منصة '%s' (%s) — سيُتجاوَز.", platform, exc)

    # --- رفع دائم للمراجعة على GitHub (بغض النظر عن AUTO_PUBLISH) ---
    # ملفات حاوية Railway مؤقتة وتُحذف بعد كل تشغيل Cron، لذا نرفع دائماً نسخة
    # إلى GitHub ليتمكن المستخدم من فتحها ومراجعتها بسهولة من المتصفح.
    repo = os.environ.get("GITHUB_REPO")
    gh_token = os.environ.get("GITHUB_TOKEN")
    branch = os.environ.get("GITHUB_BRANCH", "main")

    public_urls: list[str] = []
    if repo and gh_token:
        log.info("3/4 — رفع النص والتصاميم إلى GitHub للمراجعة...")
        review_folder = f"posts/{stamp}"
        content_path = os.path.join(out_dir, "content.json")
        upload_image_to_github(content_path, repo, branch, gh_token, dest_folder=review_folder)
        public_urls = upload_all(image_paths, repo, branch, gh_token, dest_folder=review_folder)
        for u in public_urls:
            log.info("رابط للمراجعة: %s", u)
        log.info("افتح مجلد '%s' في مستودعك على GitHub لمشاهدة كل شيء.", review_folder)
    else:
        log.warning(
            "GITHUB_REPO/GITHUB_TOKEN غير مضبوطين — لن يتم رفع أي شيء للمراجعة، "
            "والملفات ستُفقد بعد إغلاق الحاوية. أضف المتغيرين في Railway لرؤية المخرجات."
        )

    auto_publish = os.environ.get("AUTO_PUBLISH", "false").lower() == "true"
    if not auto_publish:
        log.info("وضع المراجعة (Dry Run) مفعّل — لن يتم النشر تلقائياً على Instagram.")
        return

    if not public_urls:
        log.error("لا يمكن النشر على Instagram بدون رابط صورة عام — تحقق من إعدادات GitHub.")
        return

    log.info("4/4 — نشر المنشور على Instagram...")
    ig_user_id = os.environ["IG_BUSINESS_ACCOUNT_ID"]
    ig_token = os.environ["IG_ACCESS_TOKEN"]
    caption = content["full_caption"]
    image_url = public_urls[0]
    post_id = publish_post(ig_user_id, image_url, caption, ig_token)
    log.info("تم النشر بنجاح! معرّف المنشور: %s", post_id)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        log.exception("فشل تشغيل الإيجنت: %s", exc)
        sys.exit(1)
