"""
clear_posts.py
سكربت لمرة واحدة لحذف كل المحتوى القديم من مجلد posts/ في المستودع، لتبدأ
من صفحة نظيفة تماماً. يستخدم نفس GITHUB_REPO / GITHUB_TOKEN / GITHUB_BRANCH
المضبوطة أصلاً في متغيرات البيئة على Railway — لا حاجة لأي إعداد إضافي.

طريقة التشغيل (الأسهل): من Railway → خدمتك → تبويب Console → نفّذ:
    python clear_posts.py

أو محلياً على جهازك (بعد تجهيز نفس متغيرات البيئة في .env):
    python clear_posts.py
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_API = "https://api.github.com"


def list_all_files(repo: str, branch: str, token: str, path: str = "posts") -> list[dict]:
    """يسرد كل الملفات (وليس المجلدات) داخل مسار معيّن بشكل متكرر (recursive)."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    resp = requests.get(url, headers=headers, params={"ref": branch}, timeout=30)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()

    files = []
    for item in resp.json():
        if item["type"] == "file":
            files.append(item)
        elif item["type"] == "dir":
            files.extend(list_all_files(repo, branch, token, item["path"]))
    return files


def delete_file(repo: str, branch: str, token: str, path: str, sha: str) -> None:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    payload = {"message": f"chore: clear old post {path}", "sha": sha, "branch": branch}
    resp = requests.delete(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()


def main() -> None:
    repo = os.environ["GITHUB_REPO"]
    token = os.environ["GITHUB_TOKEN"]
    branch = os.environ.get("GITHUB_BRANCH", "main")

    print(f"جاري البحث عن كل الملفات داخل posts/ في {repo} ({branch})...")
    files = list_all_files(repo, branch, token)

    if not files:
        print("لا يوجد أي ملفات لحذفها. المجلد نظيف بالفعل.")
        return

    print(f"تم العثور على {len(files)} ملفاً. سيتم حذفها الآن...")
    for i, f in enumerate(files, 1):
        try:
            delete_file(repo, branch, token, f["path"], f["sha"])
            print(f"  [{i}/{len(files)}] حُذف: {f['path']}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}/{len(files)}] فشل حذف {f['path']}: {exc}")

    print("انتهى. مجلد posts/ أصبح فارغاً — التشغيل القادم للإيجنت سيبدأ من جديد تماماً.")


if __name__ == "__main__":
    main()
