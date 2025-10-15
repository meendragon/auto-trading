import requests, yaml, json

with open("config.yaml", encoding="utf-8") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

url = "https://openapi.koreainvestment.com:9443/uapi/overseas-price/v1/quotations/search-info"
headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Authorization": f"Bearer {config['ACCESS_TOKEN']}",
    "appKey": config["APP_KEY"],
    "appSecret": config["APP_SECRET"],
    "tr_id": "CTPF1702R",
    "custtype": "P"
}
params = {
    "PRDT_TYPE_CD": "513",   # ✅ 512=NASDAQ / 513=NYSE / 529=AMEX
    "PDNO": "SES"            # ✅ 종목코드
}

res = requests.get(url, headers=headers, params=params)
print("STATUS:", res.status_code)
print("TEXT:", res.text)

if res.status_code == 200 and res.text.strip():
    data = res.json()
    info = data.get("output", {})
    print(f"✅ {info.get('prdt_name')} ({info.get('ovrs_excg_name')}) / 현재가: {info.get('ovrs_now_pric1')}")
else:
    print("⚠️ 응답이 비정상 (도메인, 토큰, TR ID, 파라미터 확인)")