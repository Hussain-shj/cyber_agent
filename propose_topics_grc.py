"""
propose_topics_grc.py
نظير propose_topics.py لكن لمحتوى GRC — يبحث ويكتب نصاً كاملاً لـ3 مواضيع
GRC مرشحة (بدون أي توليد صور)، ويرفعها إلى posts_grc/candidates/{stamp}.json
ليختار المستخدم واحداً منها من صفحة المراجعة (تبويب "📝 مرشحة GRC").

يُشغَّل كخدمة Railway منفصلة (Cron)، بجدول أبكر من agent_runner_grc.py.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from content_generator_grc import generate_candidate_grc_topics
from github_uploader import upload_image_to_github

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("propose-topics-grc")


def run() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")

    log.info("1/2 — البحث وكتابة 3 مواضيع GRC مرشحة عبر Anthropic API (بدون صور)...")
    result = generate_candidate_grc_topics(count=3)

    candidates = result.get("candidates") or []
    if result.get("no_news") or not candidates:
        log.info("لا توجد مواضيع GRC جديدة تستحق الاقتراح اليوم. إنهاء التشغيل.")
        return

    log.info("تم إنتاج %d مواضيع GRC مرشحة:", len(candidates))
    for i, c in enumerate(candidates):
        log.info("  [%d] %s — %s", i, c.get("classification", "?"), c.get("hook_title", "?"))

    os.makedirs("/tmp/candidates_grc_out", exist_ok=True)
    local_path = f"/tmp/candidates_grc_out/{stamp}.json"
    with open(local_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    repo = os.environ.get("GITHUB_REPO")
    gh_token = os.environ.get("GITHUB_TOKEN")
    branch = os.environ.get("GITHUB_BRANCH", "main")

    if not (repo and gh_token):
        log.warning("GITHUB_REPO/GITHUB_TOKEN غير مضبوطين — لا يمكن رفع المواضيع المرشحة.")
        return

    log.info("2/2 — رفع المواضيع المرشحة إلى GitHub للمراجعة...")
    url = upload_image_to_github(local_path, repo, branch, gh_token, dest_folder="posts_grc/candidates")
    log.info("رابط المراجعة: %s", url)
    log.info(
        "افتح تبويب '📝 مرشحة GRC' في صفحة المراجعة، اختر موضوعاً، ثم شغّل "
        "agent_runner_grc.py من Railway."
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        log.exception("فشل تشغيل اقتراح مواضيع GRC: %s", exc)
        sys.exit(1)
