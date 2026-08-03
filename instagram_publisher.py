"""
instagram_publisher.py
ينشر صورة + تعليق على حساب Instagram Business/Creator عبر Meta Graph API.

المتطلبات المسبقة (تُجهَّز مرة واحدة من Meta Developers):
  - صفحة فيسبوك مرتبطة بحساب Instagram احترافي (Business/Creator).
  - تطبيق Meta App فيه صلاحيات: instagram_basic, instagram_content_publish,
    pages_show_list, pages_read_engagement.
  - Access Token طويل الأمد (Long-Lived Page/User Token) بصلاحية الحساب أعلاه.
  - معرف حساب Instagram Business (IG_BUSINESS_ACCOUNT_ID) — يُستخرج مرة واحدة
    عبر: GET /{page-id}?fields=instagram_business_account
"""

import time

import requests

GRAPH_API = "https://graph.facebook.com/v20.0"


class InstagramPublishError(RuntimeError):
    pass


def _check(resp: requests.Response):
    if resp.status_code >= 400:
        raise InstagramPublishError(f"{resp.status_code}: {resp.text}")
    return resp.json()


def create_media_container(ig_user_id: str, image_url: str, caption: str, access_token: str) -> str:
    url = f"{GRAPH_API}/{ig_user_id}/media"
    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }
    data = _check(requests.post(url, data=payload, timeout=30))
    return data["id"]


def wait_until_ready(container_id: str, access_token: str, timeout_s: int = 60) -> None:
    url = f"{GRAPH_API}/{container_id}"
    waited = 0
    while waited < timeout_s:
        data = _check(requests.get(url, params={"fields": "status_code", "access_token": access_token}, timeout=30))
        status = data.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise InstagramPublishError(f"فشل تجهيز الحاوية: {data}")
        time.sleep(3)
        waited += 3
    raise InstagramPublishError("انتهت مهلة انتظار تجهيز الوسائط.")


def publish_container(ig_user_id: str, container_id: str, access_token: str) -> str:
    url = f"{GRAPH_API}/{ig_user_id}/media_publish"
    payload = {"creation_id": container_id, "access_token": access_token}
    data = _check(requests.post(url, data=payload, timeout=30))
    return data["id"]


def publish_post(ig_user_id: str, image_url: str, caption: str, access_token: str) -> str:
    """تسلسل النشر الكامل: إنشاء حاوية -> انتظار الجاهزية -> نشر. يعيد معرّف المنشور."""
    container_id = create_media_container(ig_user_id, image_url, caption, access_token)
    wait_until_ready(container_id, access_token)
    return publish_container(ig_user_id, container_id, access_token)
