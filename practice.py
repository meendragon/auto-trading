# practice.py
import yaml
from utils.api import fetch_access_token, send_discord_message

# -------------------------------------------------------
# ✅ 설정 로드
# -------------------------------------------------------
with open("config.yaml", encoding="utf-8") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

# -------------------------------------------------------
# ✅ 메인 루틴 (연결 시작)
# -------------------------------------------------------
if __name__ == "__main__":
    send_discord_message("🚀 Practice 모드 시작 — 서버 연결 테스트 중...")
    access_token = fetch_access_token(force_refresh=True)
    send_discord_message("✅ API 연결 테스트 완료 (Access Token 정상 발급)")
    print("✅ 연결 테스트 완료")