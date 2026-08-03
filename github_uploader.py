"""
github_uploader.py
يرفع صورة PNG إلى مستودع GitHub عبر REST API للحصول على رابط عام
(raw.githubusercontent.com) يمكن لواجهة Instagram Graph API قراءته
عند إنشاء حاوية الوسائط (Media Container).
"""

import base64
import datetime
import os

import requests

GITHUB_API = "https://api.github.com"


def upload_image_to_github(
    local_path: str,
    repo: str,            # مثال: "username/cyber-agent"
    branch: str,
    token: str,
    dest_folder: str = "posts",
) -> str:
    """يرفع الملف ويعيد الرابط العام (raw) القابل للاستخدام في Instagram Graph API."""
    filename = os.path.basename(local_path)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest_path = f"{dest_folder}/{stamp}_{filename}"

    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")

    url = f"{GITHUB_API}/repos/{repo}/contents/{dest_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    payload = {
        "message": f"chore: add generated post image {stamp}",
        "content": content_b64,
        "branch": branch,
    }

    resp = requests.put(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()

    return f"https://raw.githubusercontent.com/{repo}/{branch}/{dest_path}"


def upload_all(local_paths: list[str], repo: str, branch: str, token: str) -> list[str]:
    return [upload_image_to_github(p, repo, branch, token) for p in local_paths]
