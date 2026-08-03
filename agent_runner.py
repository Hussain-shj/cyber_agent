"""
agent_runner.py
نقطة التشغيل الرئيسية للإيجنت اليومي:
  1) توليد المحتوى (بحث + تصنيف + تقييم + كتابة) عبر Anthropic API.
  2) توليد 3 تصاميم صور بالهوية البصرية السيبرانية.
  3) رفع الصور إلى GitHub للحصول على روابط عامة.
  4) نشر منشور واحد (أول تصميم) على Instagram — فقط إذا AUTO_PUBLISH=true.

الوضع الافتراضي هو "مراجعة" (Dry Run): يولّد كل شيء ويحفظه محلياً في posts/
بدون نشر فعلي، حتى تتم مراجعته يدوياً أولاً. للتفعيل الكامل، اضبط
AUTO_PUBLISH=true في متغيرات البيئة بعد أن تتأكد من جودة المخرجات.
"""

import json
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from content_generator import generate_daily_content
from image_generator import generate_designs
from github_uploader import upload_all
from instagram_publisher import publish_post

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cyber-agent")


def run() -> None:
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
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

    log.info("2/4 — توليد 3 تصاميم بصرية...")
    image_paths = generate_designs(content, out_dir)
    log.info("تم حفظ التصاميم في: %s", out_dir)

    auto_publish = os.environ.get("AUTO_PUBLISH", "false").lower() == "true"
    if not auto_publish:
        log.info("وضع المراجعة (Dry Run) مفعّل — لن يتم النشر تلقائياً.")
        log.info("راجع الملفات في '%s' ثم انشر يدوياً، أو فعّل AUTO_PUBLISH=true.", out_dir)
        return

    log.info("3/4 — رفع الصورة المختارة إلى GitHub للحصول على رابط عام...")
    repo = os.environ["GITHUB_REPO"]           # مثال: username/cyber-agent
    branch = os.environ.get("GITHUB_BRANCH", "main")
    gh_token = os.environ["GITHUB_TOKEN"]
    # ننشر التصميم الأول (design_1_standard) كصورة المنشور اليومي
    chosen_image = image_paths[0]
    public_urls = upload_all([chosen_image], repo, branch, gh_token)
    image_url = public_urls[0]
    log.info("رابط الصورة العام: %s", image_url)

    log.info("4/4 — نشر المنشور على Instagram...")
    ig_user_id = os.environ["IG_BUSINESS_ACCOUNT_ID"]
    ig_token = os.environ["IG_ACCESS_TOKEN"]
    caption = content["full_caption"]
    post_id = publish_post(ig_user_id, image_url, caption, ig_token)
    log.info("تم النشر بنجاح! معرّف المنشور: %s", post_id)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        log.exception("فشل تشغيل الإيجنت: %s", exc)
        sys.exit(1)
