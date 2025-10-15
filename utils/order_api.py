import requests, json, yaml
from utils.api import send_discord_message
from utils.helpers import map_exchange_code
# ✅ 설정 로드
with open("config.yaml", encoding="utf-8") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

app_key = config["APP_KEY"]
app_secret = config["APP_SECRET"]
cano = config["CANO"]
account_product_code = config["ACNT_PRDT_CD"]
url_base = config["URL_BASE"]
access_token = config["ACCESS_TOKEN"]

TR_ID_BUY = "TTTT1002U"
TR_ID_SELL = "TTTT1006U"


# ==============================================
# ✅ 매수 함수 (시장가)
# ==============================================
def buy_order(symbol, qty, exchange_short, target_price="0"):
    try:
        exchange = map_exchange_code(exchange_short)  # ✅ 자동 변환

        url = f"{url_base}/uapi/overseas-stock/v1/trading/order"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {access_token}",
            "appKey": app_key,
            "appSecret": app_secret,
            "tr_id": TR_ID_BUY,
            "custtype": "P"
        }

        body = {
            "CANO": cano,
            "ACNT_PRDT_CD": account_product_code,
            "OVRS_EXCG_CD": exchange,  # ✅ 풀네임으로 자동 변환
            "PDNO": symbol,
            "ORD_QTY": str(qty),
            "OVRS_ORD_UNPR": f"{float(target_price):.2f}" if target_price != "0" else "0",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": "00",  # 지정가
        }

        print(f"[DEBUG] buy_order body: {body}")
        res = requests.post(url, headers=headers, data=json.dumps(body))
        data = res.json()

        if data.get("rt_cd") == "0":
            send_discord_message(f"✅ [{symbol}] 매수 성공 ({exchange}) | {qty}주")
            return True
        else:
            msg = data.get("msg1", "알 수 없는 오류")
            send_discord_message(f"❗[{symbol}] 매수 실패 ({exchange}) → {msg}")
            return False

    except Exception as e:
        send_discord_message(f"[매수 주문 에러] {e}")
        return False

# ==============================================
# ✅ 매도 함수 (시장가)
# ==============================================
def sell_order(symbol, qty, exchange_short, target_price="0"):
    try:
        exchange = map_exchange_code(exchange_short)   # ✅ 자동 변환

        url = f"{url_base}/uapi/overseas-stock/v1/trading/order"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {access_token}",
            "appKey": app_key,
            "appSecret": app_secret,
            "tr_id": TR_ID_SELL,
            "custtype": "P"
        }

        body = {
            "CANO": cano,
            "ACNT_PRDT_CD": account_product_code,
            "OVRS_EXCG_CD": exchange,
            "PDNO": symbol,
            "ORD_QTY": str(qty),
            "OVRS_ORD_UNPR": f"{float(target_price):.2f}" if target_price != "0" else "0",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": "00",
        }

        print(f"[DEBUG] sell_order body: {body}")
        res = requests.post(url, headers=headers, data=json.dumps(body))
        data = res.json()

        if data.get("rt_cd") == "0":
            send_discord_message(f"💰 [{symbol}] 매도 성공 ({exchange}) | {qty}주 @ {target_price}")
            return True
        else:
            msg = data.get("msg1", "알 수 없는 오류")
            send_discord_message(f"❗[{symbol}] 매도 실패 ({exchange}) → {msg}")
            return False

    except Exception as e:
        send_discord_message(f"[매도 주문 에러] {e}")
        return False