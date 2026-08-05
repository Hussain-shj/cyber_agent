"""
agent_runner_grc.py
نقطة التشغيل اليومية لمحتوى الحوكمة وإدارة المخاطر والامتثال (GRC) —
نظير agent_runner.py الخاص بالأمن السيبراني، بنفس البنية والمنطق، لكن:
  - يستخدم content_generator_grc.py (مصادر وتصنيفات GRC مختلفة).
  - يستخدم grc_image_generator.py (هوية بصرية بيضاء/كريمية رسمية بدل الداكنة).
  - يرفع المخرجات لمجلد "posts_grc/" منفصل في نفس مستودع GitHub، حتى لا
    تختلط مراجعة محتوى GRC بمحتوى الأمن السيبراني.
  - يدعم نظام "المواضيع المرشحة": يبحث أولاً عن اختيار محفوظ من صفحة
    المراجعة (posts_grc/candidates/selected.json)، ثم أحدث ملف مرشحين +
    SELECTED_TOPIC_INDEX_GRC، وإلا يبحث ويكتب موضوعاً مباشرة كما كان سابقاً.

يشارك نفس الوحدات المساعدة (github_uploader.py, instagram_publisher.py)
ونفس حسابات GitHub/Instagram المضبوطة أصلاً، ما لم تُضبط متغيرات بيئة خاصة
بـ GRC (انظر القسم الخاص في README).

الوضع الافتراضي "مراجعة" (Dry Run) مطابق تماماً للمشروع السيبراني: يولّد كل
شيء ويحفظه للمراجعة على GitHub بدون نشر فعلي، حتى تُفعّل AUTO_PUBLISH_GRC=true.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from content_generator_grc import generate_daily_grc_content
from grc_image_generator import generate_grc_designs, generate_grc_platform_designs
from github_uploader import (
    delete_file, download_file_json, get_file_sha, list_folder, upload_all, upload_image_to_github,
)
from instagram_publisher import publish_post

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("grc-agent")

CANDIDATES_DIR = "posts_grc/candidates"


def _load_selected_grc_candidate(repo: str, branch: str, token: str) -> dict | None:
    """نفس منطق _load_selected_candidate في agent_runner.py، لكن على مجلد
    posts_grc/candidates/ ومتغير SELECTED_TOPIC_INDEX_GRC."""
    selected_marker = None
    try:
        selected_marker = download_file_json(repo, branch, token, f"{CANDIDATES_DIR}/selected.json")
    except Exception:  # noqa: BLE001
        pass

    if selected_marker and selected_marker.get("source_file"):
        source_file = selected_marker["source_file"]
        idx = int(selected_marker.get("index", 0))
        log.info("وُجد اختيار محفوظ من صفحة المراجعة (GRC): %s [%d]", source_file, idx)
        try:
            data = download_file_json(repo, branch, token, source_file)
            candidates = data.get("candidates") or []
            if candidates and idx < len(candidates):
                chosen = candidates[idx]
                try:
                    sha = get_file_sha(repo, branch, token, f"{CANDIDATES_DIR}/selected.json")
                    if sha:
                        delete_file(repo, branch, token, f"{CANDIDATES_DIR}/selected.json", sha)
                        log.info("تم حذف ملف الاختيار المحفوظ (GRC) بعد الاستخدام.")
                except Exception as exc:  # noqa: BLE001
                    log.warning("تعذّر حذف ملف الاختيار المحفوظ (%s) — لن يمنع المتابعة.", exc)
                return chosen
            log.warning("الاختيار المحفوظ غير صالح — سيُتجاهَل.")
        except Exception as exc:  # noqa: BLE001
            log.warning("تعذّرت قراءة ملف الاختيار المحفوظ (%s) — سيُتجاهَل.", exc)

    entries = list_folder(repo, branch, token, CANDIDATES_DIR)
    files = [e for e in entries if e["type"] == "file" and e["name"].endswith(".json")
             and e["name"] != "selected.json"]
    if not files:
        return None
    files.sort(key=lambda e: e["name"], reverse=True)
    latest = files[0]
    log.info("وُجد ملف مواضيع GRC مرشحة: %s", latest["path"])

    data = download_file_json(repo, branch, token, latest["path"])
    candidates = data.get("candidates") or []
    if not candidates:
        return None

    idx = int(os.environ.get("SELECTED_TOPIC_INDEX_GRC", "0"))
    if idx >= len(candidates):
        log.warning("SELECTED_TOPIC_INDEX_GRC=%d خارج النطاق (يوجد %d) — استخدام 0.", idx, len(candidates))
        idx = 0
    log.info("تم اختيار موضوع GRC رقم %d من %d.", idx, len(candidates))
    return candidates[idx]


def run() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    out_dir = os.path.join("posts_grc", stamp)

    repo = os.environ.get("GITHUB_REPO")
    gh_token = os.environ.get("GITHUB_TOKEN")
    branch = os.environ.get("GITHUB_BRANCH", "main")

    content = None
    if repo and gh_token:
        try:
            content = _load_selected_grc_candidate(repo, branch, gh_token)
        except Exception as exc:  # noqa: BLE001
            log.warning("تعذّرت قراءة ملف المواضيع المرشحة (%s) — سيُبحث مباشرة بدلاً منه.", exc)
            content = None

    if content is not None:
        log.info("1/4 — تم استخدام موضوع GRC مُختار مسبقاً (بدون بحث جديد).")
    else:
        log.info("1/4 — لا يوجد ملف مواضيع مرشحة؛ البحث والكتابة مباشرة عبر Anthropic API...")
        content = generate_daily_grc_content()

    if content.get("no_news"):
        log.info("لا يوجد موضوع GRC جديد يستحق النشر اليوم. إنهاء التشغيل.")
        return

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "content.json"), "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    log.info("تم إنتاج المحتوى: %s", content.get("hook_title"))

    log.info("2/4 — توليد التصاميم البصرية (بهوية GRC البيضاء الرسمية)...")

    ai_backgrounds = []
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai_image_generator import generate_backgrounds
            concepts = content.get("visual_concepts") or []
            if concepts:
                log.info("أفكار Claude البصرية الثلاث (GRC): %s", concepts)
                ai_backgrounds = generate_backgrounds(
                    concepts,
                    content["classification"],
                    content.get("urgency") == "عاجل",
                    quality=os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
                )
                ok = sum(1 for b in ai_backgrounds if b is not None)
                log.info("تم توليد %d من %d خلفيات فنية بنجاح.", ok, len(concepts))
        except Exception as exc:  # noqa: BLE001
            log.warning("فشل توليد الخلفيات الفنية (%s) — سيُستخدم التصميم المحلي بديلاً.", exc)
            ai_backgrounds = []

    # ملاحظة: قوالب GRC الحالية (grc_image_generator.py) لا تدعم بعد تركيب
    # خلفية فنية خارجية فوقها (بخلاف قوالب الأمن السيبراني) — تُستخدم الرسوم
    # المحلية بالهوية البيضاء دائماً حالياً. سيُضاف الدعم لاحقاً إن احتيج.
    image_paths = generate_grc_designs(content, out_dir)
    log.info("تم حفظ تصاميم GRC محلياً في: %s", out_dir)

    extra_platforms = [
        p.strip() for p in os.environ.get("EXTRA_PLATFORMS_GRC", "linkedin").split(",") if p.strip()
    ]
    for platform in extra_platforms:
        try:
            platform_paths = generate_grc_platform_designs(content, out_dir, platform=platform)
            image_paths += platform_paths
            log.info("تم توليد %d صور إضافية لمنصة '%s'.", len(platform_paths), platform)
        except Exception as exc:  # noqa: BLE001
            log.warning("فشل توليد صور منصة '%s' (%s) — سيُتجاوَز.", platform, exc)

    # --- رفع دائم للمراجعة على GitHub (مجلد posts_grc/ منفصل) ---
    public_urls: list[str] = []
    if repo and gh_token:
        log.info("3/4 — رفع النص والتصاميم إلى GitHub للمراجعة...")
        review_folder = f"posts_grc/{stamp}"
        content_path = os.path.join(out_dir, "content.json")
        upload_image_to_github(content_path, repo, branch, gh_token, dest_folder=review_folder)
        public_urls = upload_all(image_paths, repo, branch, gh_token, dest_folder=review_folder)
        for u in public_urls:
            log.info("رابط للمراجعة: %s", u)
        log.info("افتح مجلد '%s' في مستودعك على GitHub لمشاهدة كل شيء.", review_folder)
    else:
        log.warning(
            "GITHUB_REPO/GITHUB_TOKEN غير مضبوطين — لن يتم رفع أي شيء للمراجعة."
        )

    auto_publish = os.environ.get("AUTO_PUBLISH_GRC", "false").lower() == "true"
    if not auto_publish:
        log.info("وضع المراجعة (Dry Run) مفعّل لـ GRC — لن يتم النشر تلقائياً.")
        return

    if not public_urls:
        log.error("لا يمكن النشر بدون رابط صورة عام — تحقق من إعدادات GitHub.")
        return

    # يستخدم نفس حساب Instagram المضبوط للمشروع السيبراني افتراضياً، إلا إذا
    # ضُبطت متغيرات منفصلة خاصة بـ GRC (لحساب Instagram مختلف مثلاً).
    log.info("4/4 — نشر المنشور على Instagram...")
    ig_user_id = os.environ.get("IG_BUSINESS_ACCOUNT_ID_GRC") or os.environ["IG_BUSINESS_ACCOUNT_ID"]
    ig_token = os.environ.get("IG_ACCESS_TOKEN_GRC") or os.environ["IG_ACCESS_TOKEN"]
    caption = content["full_caption"]
    image_url = public_urls[0]
    post_id = publish_post(ig_user_id, image_url, caption, ig_token)
    log.info("تم النشر بنجاح! معرّف المنشور: %s", post_id)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        log.exception("فشل تشغيل إيجنت GRC: %s", exc)
        sys.exit(1)
