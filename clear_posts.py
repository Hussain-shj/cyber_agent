"""
clear_posts.py
سكربت لمرة واحدة لحذف كل المحتوى القديم من مجلدي posts/ و posts_grc/ (بما
فيهما المرشحين وملفات الاختيار) في المستودع، لتبدأ من صفحة نظيفة تماماً على
كلا النظامين (الأمن السيبراني و GRC) معاً. يستخدم نفس GITHUB_REPO /
GITHUB_TOKEN / GITHUB_BRANCH المضبوطة أصلاً في متغيرات البيئة على Railway —
لا حاجة لأي إعداد إضافي.

طريقة التشغيل (الأسهل): من Railway → أي خدمة عندها Console → نفّذ:
    python clear_posts.py

أو محلياً على جهازك (بعد تجهيز نفس متغيرات البيئة في .env):
    python clear_posts.py
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_API = "https://api.github.com"

# المجلدات الجذرية التي يُراد مسحها بالكامل (كل شيء بداخلها، بما فيه المجلدات
# الفرعية مثل candidates/). أضف أي مجلد جديد هنا مستقبلاً إن احتجت.
ROOT_FOLDERS = ["posts", "posts_grc"]


def list_all_files(repo: str, branch: str, token: str, path: str) -> list[dict]:
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

    all_files = []
    for root in ROOT_FOLDERS:
        print(f"جاري البحث عن كل الملفات داخل {root}/ في {repo} ({branch})...")
        files = list_all_files(repo, branch, token, root)
        print(f"  وُجد {len(files)} ملفاً في {root}/.")
        all_files.extend(files)

    if not all_files:
        print("لا يوجد أي ملفات لحذفها. كل المجلدات نظيفة بالفعل.")
        return

    print(f"\nإجمالي {len(all_files)} ملفاً سيُحذف من كل المجلدات ({', '.join(ROOT_FOLDERS)})...")
    for i, f in enumerate(all_files, 1):
        try:
            delete_file(repo, branch, token, f["path"], f["sha"])
            print(f"  [{i}/{len(all_files)}] حُذف: {f['path']}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}/{len(all_files)}] فشل حذف {f['path']}: {exc}")

    print(f"\nانتهى. مجلدات {', '.join(ROOT_FOLDERS)} أصبحت فارغة تماماً — بداية نظيفة كاملة.")


if __name__ == "__main__":
    main()
