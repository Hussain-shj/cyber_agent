"""
propose_topics.py
المرحلة الأولى من تدفق "اختيار الموضوع قبل توليد الصور": يبحث ويكتب نصاً
كاملاً لعدة مواضيع مرشحة (بما فيها 3 أفكار بصرية لكل موضوع)، بدون أي استدعاء
لتوليد صور — منخفض التكلفة. يرفع النتيجة كملف واحد إلى GitHub تحت
posts/candidates/{stamp}.json ليراجعه المستخدم.

بعد المراجعة (ومراجعة/تعديل الأفكار البصرية مباشرة في GitHub إن رغبت)، اضبط
SELECTED_TOPIC_INDEX (0 أو 1 أو 2) في متغيرات البيئة، ثم شغّل agent_runner.py
(يدوياً أو حسب جدولته) — سيقرأ هذا الملف تلقائياً ويولّد الصور للموضوع
المختار فقط عبر OpenAI.

يُشغَّل هذا كخدمة Railway منفصلة (Cron) بجدول أبكر من agent_runner.py، لإعطاء
وقت كافٍ للمراجعة قبل التشغيل التالي.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from content_generator import generate_candidate_topics
from github_uploader import upload_image_to_github

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("propose-topics")


def run() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")

    log.info("1/2 — البحث وكتابة مواضيع مرشحة عبر Anthropic API (بدون صور)...")
    result = generate_candidate_topics(count=10)

    candidates = result.get("candidates") or []
    if result.get("no_news") or not candidates:
        log.info("لا توجد مواضيع جديدة تستحق الاقتراح اليوم. إنهاء التشغيل.")
        return

    log.info("تم إنتاج %d مواضيع مرشحة:", len(candidates))
    for i, c in enumerate(candidates):
        log.info("  [%d] %s — %s", i, c.get("classification", "?"), c.get("hook_title", "?"))

    os.makedirs("/tmp/candidates_out", exist_ok=True)
    local_path = f"/tmp/candidates_out/{stamp}.json"
    with open(local_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    repo = os.environ.get("GITHUB_REPO")
    gh_token = os.environ.get("GITHUB_TOKEN")
    branch = os.environ.get("GITHUB_BRANCH", "main")

    if not (repo and gh_token):
        log.warning(
            "GITHUB_REPO/GITHUB_TOKEN غير مضبوطين — لا يمكن رفع المواضيع المرشحة "
            "للمراجعة، وستُفقد بعد إغلاق الحاوية."
        )
        return

    log.info("2/2 — رفع المواضيع المرشحة إلى GitHub للمراجعة...")
    url = upload_image_to_github(local_path, repo, branch, gh_token, dest_folder="posts/candidates")
    log.info("رابط المراجعة: %s", url)
    log.info(
        "افتح الملف أعلاه، راجع المواضيع (وعدّل visual_concepts مباشرة إن "
        "أردت)، ثم اضبط SELECTED_TOPIC_INDEX (0/1/2) وشغّل agent_runner.py."
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        log.exception("فشل تشغيل اقتراح المواضيع: %s", exc)
        sys.exit(1)
