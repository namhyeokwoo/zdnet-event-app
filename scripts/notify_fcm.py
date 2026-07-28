"""FCM 푸시 알림 발송 — firebase-admin 사용, 단일기기 direct-token 방식.

FCM_SERVICE_ACCOUNT_JSON(서비스계정 JSON, 한 줄로 minify된 값)과
FCM_DEVICE_TOKEN(hub-app 설정 화면에서 확인한 기기 토큰) 환경변수가
둘 다 설정돼 있을 때만 발송한다. 둘 중 하나라도 없으면 조용히 스킵
(FCM 미설정 상태에서도 기존 파이프라인이 깨지지 않도록).
"""
import json
import os
import sys

import firebase_admin
from firebase_admin import credentials, messaging


def send(title: str, body: str) -> None:
    sa_json = os.environ.get("FCM_SERVICE_ACCOUNT_JSON", "")
    device_token = os.environ.get("FCM_DEVICE_TOKEN", "")
    if not sa_json or not device_token:
        print("[알림 스킵] FCM_SERVICE_ACCOUNT_JSON 또는 FCM_DEVICE_TOKEN 미설정")
        return
    cred = credentials.Certificate(json.loads(sa_json))
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=device_token,
    )
    messaging.send(message)
    print(f"[알림 발송] {title}")


if __name__ == "__main__":
    send(sys.argv[1], sys.argv[2])
