import requests
import json
import datetime
import time
import yaml
from utils.helpers import safe_float  # ✅ safe_float 불러오기

with open('config.yaml', encoding='UTF-8') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

app_key = config['APP_KEY']
app_secret = config['APP_SECRET']
cano = config['CANO']
account_product_code = config['ACNT_PRDT_CD']
discord_webhook_url = config['DISCORD_WEBHOOK_URL']
url_base = config['URL_BASE']
access_token = config['ACCESS_TOKEN']

def fetch_access_token(force_refresh=False):
    """
    액세스 토큰 발급 (하루 1회 권장)
    """
    global access_token

    # ✅ 이미 토큰이 있고, 발급 시각이 하루 안 넘었으면 재사용
    issued_at_str = config.get("TOKEN_ISSUED_AT")
    if issued_at_str and not force_refresh:
        try:
            issued_at = datetime.datetime.strptime(issued_at_str, "%Y-%m-%d %H:%M:%S")
            if (datetime.datetime.now() - issued_at).total_seconds() < 86400:
                access_token = config.get("ACCESS_TOKEN", "")
                if access_token:
                    print("[토큰 재사용] 기존 ACCESS_TOKEN 유지")
                    return access_token
        except Exception:
            pass  # 형식 깨졌을 때는 그냥 새로 발급

    # ✅ 여기까지 왔다는 건 없거나 만료된 경우 → 새로 발급
    headers = {"Content-Type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret}
    response = requests.post(f"{url_base}/oauth2/tokenP", headers=headers, data=json.dumps(body))
    data = response.json()
    access_token = data.get("access_token", "")

    if access_token:
        config["ACCESS_TOKEN"] = access_token
        config["TOKEN_ISSUED_AT"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("config.yaml", "w", encoding="UTF-8") as f:
            yaml.dump(config, f, allow_unicode=True)

        send_discord_message("[✅ 새로운 토큰 발급 완료]")
        print("[ACCESS_TOKEN 갱신]", access_token)
    else:
        send_discord_message("[❗토큰 발급 실패] 응답: " + json.dumps(data))
        print(data)

    return access_token

def send_discord_message(message):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    payload = {"content": f"[{timestamp}] {message}"}
    requests.post(discord_webhook_url, data=payload)
    print(payload)

def fetch_present_balance():
    resp = requests.get(
        f"{url_base}/uapi/overseas-stock/v1/trading/inquire-present-balance",
        headers={
            "Content-Type": "application/json",
            "authorization": f"Bearer {access_token}",
            "appKey": app_key,
            "appSecret": app_secret,
            "tr_id": "CTRP6504R",
            "custtype": "P"
        },
        params={
            "CANO": cano,
            "ACNT_PRDT_CD": account_product_code,
            "WCRC_FRCR_DVSN_CD": "02",
            "NATN_CD": "840",
            "TR_MKET_CD": "00",
            "INQR_DVSN_CD": "00",
        }
    )

    data = resp.json()
    items = data.get('output1', [])

    if not items:
        send_discord_message("[❗] 체결 기준 잔고가 없습니다.")
        return []

    for item in items:
        종목명 = item.get("prdt_name", "-")
        수익률_float = safe_float(item.get("evlu_pfls_rt1", "0"))
        평균단가_float = safe_float(item.get("frcr_pchs_amt", "0"))
        현재가_float = safe_float(item.get("frcr_evlu_amt2", "0"))
        수량 = item.get("ord_psbl_qty1", "0")
        거래소코드 = item.get("ovrs_excg_cd", "")

        수익률_이모지 = "🟢" if 수익률_float > 0 else "🔴" if 수익률_float < 0 else "⚪"
        국기 = "🇺🇸" if 거래소코드 in ["NASD", "NYSE", "AMEX"] else "🇯🇵" if 거래소코드 == "TKSE" else "🌐"

        message = (
            f"{국기} **{종목명}**\n"
            f"{수익률_이모지} 평가손익률: {수익률_float:.2f}%\n"
            f"📈 현재가: ${현재가_float:.2f} / 🧾 매입가: ${평균단가_float:.2f}\n"
            f"📦 보유 수량: {수량}주"
        )
        send_discord_message(message)

    return items

def fetch_cash_amount():
    resp = requests.get(
        f"{url_base}/uapi/overseas-stock/v1/trading/inquire-present-balance",
        headers={
            "Content-Type": "application/json",
            "authorization": f"Bearer {access_token}",
            "appKey": app_key,
            "appSecret": app_secret,
            "tr_id": "CTRP6504R",
            "custtype": "P"
        },
        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": account_product_code,
            "WCRC_FRCR_DVSN_CD": "02",
            "NATN_CD": "840",
            "TR_MKET_CD": "00",
            "INQR_DVSN_CD" : "00",
        }
    )
    data = resp.json()
    output2 = data.get("output2", [])

    if output2 and isinstance(output2, list):
        cash_amount = output2[0].get("frcr_dncl_amt_2", "0")
    else:
        cash_amount = data.get("output3", {}).get("dncl_amt", "0")

    send_discord_message(f"[USD 사용 가능 외화] {cash_amount} USD")
    return cash_amount

def get_current_price(symbol: str, exchange: str = "NAS") -> float:
    """
    특정 거래소의 주식 현재가를 조회
    exchange: 'NAS' (나스닥), 'NYS' (뉴욕), 'AMS' (AMEX)
    """
    try:
        resp = requests.get(
            f"{url_base}/uapi/overseas-price/v1/quotations/price",
            headers={
                "Content-Type": "application/json",
                "authorization": f"Bearer {access_token}",
                "appKey": app_key,
                "appSecret": app_secret,
                "tr_id": "HHDFS00000300"
            },
            params={
                "AUTH": "",
                "EXCD": exchange,
                "SYMB": symbol
            }
        )
        data = resp.json()
        output = data.get("output", {})
        price = float(output.get("last", 0) or 0)
        return price

    except Exception as e:
        print(f"[가격 조회 오류] {symbol} ({exchange}) → {e}")
        return 0.0