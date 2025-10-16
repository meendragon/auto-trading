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
            output = data.get("output", {})
            order_no = output.get("ODNO", "N/A")
            send_discord_message(f"✅ [{symbol}] 매수 성공 ({exchange}) | {qty}주")
            return True, order_no
        else:
            msg = data.get("msg1", "알 수 없는 오류")
            send_discord_message(f"❗[{symbol}] 매수 실패 ({exchange}) → {msg}")
            return False,None

    except Exception as e:
        send_discord_message(f"[매수 주문 에러] {e}")
        return False,None

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

# ==============================================
# ✅ 주문 취소 함수
# ==============================================
def cancel_order(symbol, order_no, qty, exchange_short):
    """
    ✅ 해외주식 주문취소 (RVSE_CNCL_DVSN_CD='02')
    - 기존 주문번호(ODNO)를 기반으로 주문을 취소합니다.
    """
    try:
        exchange = map_exchange_code(exchange_short)  # ✅ 자동 변환

        url = f"{url_base}/uapi/overseas-stock/v1/trading/order-rvsecncl"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {access_token}",
            "appKey": app_key,
            "appSecret": app_secret,
            "tr_id": "TTTT1004U",   # ✅ 미국 실전용 (모의는 VTTT1004U)
            "custtype": "P"
        }

        body = {
            "CANO": cano,
            "ACNT_PRDT_CD": account_product_code,
            "OVRS_EXCG_CD": exchange,
            "PDNO": symbol,
            "ORGN_ODNO": order_no,          # ✅ 원주문번호 (취소할 주문번호)
            "RVSE_CNCL_DVSN_CD": "02",      # ✅ 취소 구분 코드 (01: 정정, 02: 취소)
            "ORD_QTY": str(qty),            # ✅ 취소 수량
            "OVRS_ORD_UNPR": "0",           # ✅ 취소 시 단가 0 고정
            "ORD_SVR_DVSN_CD": "0"
        }

        print(f"[DEBUG] cancel_order body: {body}")
        res = requests.post(url, headers=headers, data=json.dumps(body))
        data = res.json()

        if data.get("rt_cd") == "0":
            output = data.get("output", {})
            new_order_no = output.get("ODNO", "N/A")
            send_discord_message(
                f"🧹 [{symbol}] 주문취소 성공 ({exchange}) | 원주문: {order_no} → 취소주문번호: {new_order_no}"
            )
            return True, new_order_no
        else:
            msg = data.get("msg1", "알 수 없는 오류")
            send_discord_message(f"❗[{symbol}] 주문취소 실패 ({exchange}) → {msg}")
            return False, None

    except Exception as e:
        send_discord_message(f"[주문취소 에러] {e}")
        return False, None