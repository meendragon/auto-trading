import yfinance as yf
import pandas as pd
import numpy as np
def map_exchange_code(short_code: str) -> str:
    """
    해외주식 거래소 코드 매핑 (조회용 약어 → 주문용 코드)
    - 조회 시: NYS / NAS / AMS ...
    - 주문 시: NYSE / NASD / AMEX ...
    """
    mapping = {
        "NYS": "NYSE",
        "NAS": "NASD",
        "AMS": "AMEX",
        "ARC": "ARCA",
        "BTS": "BATS",
        "NCM": "NCM",
    }
    return mapping.get(short_code.upper(), short_code.upper())
# ✅ 기술적 지표 계산 (볼린저밴드 + 이동평균선)

def add_indicators(df, window=20):
    df["ma20"] = df["close"].rolling(window=window).mean()
    df["stddev"] = df["close"].rolling(window=window).std()
    df["upper"] = df["ma20"] + (df["stddev"] * 2)
    df["lower"] = df["ma20"] - (df["stddev"] * 2)
    df["ma5"] = df["close"].rolling(window=5).mean()
    df["ma60"] = df["close"].rolling(window=60).mean()
    df["ma448"] = df["close"].rolling(window=448).mean()  # ✅ 추가
    return df

# ✅ 5분봉 데이터 가져오기
def fetch_5min_data(ticker):
    data = yf.download(ticker, interval="5m", period="1d", progress=False, auto_adjust=False)
    data = data.rename(columns={"Close": "close", "High": "high", "Low": "low"})
    return data

def check_buy_condition(df, current_price, mode="lower_recover", **kwargs):
    """
    mode:
      - "lower_recover" : 하단선 이탈 후 회복
      - "ma_cross"      : 단기 MA가 장기 MA 상향돌파
      - "near_ma"       : 가격이 이동평균선 근처일 때
      - "combo"         : 여러 조건 조합 (예시)
    """
    latest = df.iloc[[-1]]
    prev = df.iloc[[-2]]

    close_prev = float(prev["close"].iloc[0])
    ma20_prev = float(prev["ma20"].iloc[0])
    ma448_prev = float(prev["ma448"].iloc[0])
    ma20_now = float(latest["ma20"].iloc[0])
    ma448_now = float(latest["ma448"].iloc[0])
    lower_prev = float(prev["lower"].iloc[0])
    lower_now = float(latest["lower"].iloc[0])

    # --- 조건 계산 ---
    lower_recover = (close_prev < lower_prev) and (current_price > lower_now)
    near_ma20 = abs((current_price - ma20_now) / ma20_now) <= 0.0003
    near_ma448 = abs((current_price - ma448_now) / ma448_now) <= 0.003
    ma_cross = (ma20_prev < ma448_prev) and (ma20_now > ma448_now)

    # --- case 분기 ---
    if mode == "lower_recover":
        return lower_recover

    elif mode == "ma_cross":
        return ma_cross

    elif mode == "near_ma":
        target_ma = kwargs.get("target_ma", "ma20")
        tolerance = kwargs.get("tolerance", 0.001)
        ma_val = ma20_now if target_ma == "ma20" else ma448_now
        return abs((current_price - ma_val) / ma_val) <= tolerance

    elif mode == "combo":
        # 복합 조건 예시: 하단선 회복 + 단기이평 근접
        strict = kwargs.get("strict", False)
        if strict:
            return lower_recover and near_ma20 and ma_cross
        else:
            return (lower_recover and near_ma20) or ma_cross

    else:
        raise ValueError(f"Unknown mode: {mode}")

# ✅ 매도 조건 (익절·손절 퍼센트 조정 가능)
def check_sell_condition(entry_price, current_price, take_profit_pct=1.0, stop_loss_pct=-3.0):
    profit_rate = (current_price - entry_price) / entry_price * 100
    if profit_rate >= take_profit_pct:
        return "take_profit"
    elif profit_rate <= stop_loss_pct:
        return "stop_loss"
    return None

# ✅ 백테스트 기반 익절·손절 최적화
def optimize_sell_thresholds(ticker, take_profit_range=(0.5, 2.0, 0.5), stop_loss_range=(-5.0, -1.0, 1.0)):
    df = yf.download(ticker, interval="15m", period="5d", progress=False, auto_adjust=False)
    df = df.rename(columns={"Close": "close"})
    results = []

    take_profit_values = np.arange(*take_profit_range)
    stop_loss_values = np.arange(*stop_loss_range)

    for tp in take_profit_values:
        for sl in stop_loss_values:
            balance = 10000
            position = None
            entry_price = 0.0

            for i in range(1, len(df)):
                price = float(df["close"].iloc[i].item())
                prev_price = float(df["close"].iloc[i - 1].item())

                # 단순 매수 조건: 직전보다 상승 시작 시 진입
                if position is None and price > prev_price:
                    position = True
                    entry_price = price
                elif position:
                    result = check_sell_condition(entry_price, price, take_profit_pct=tp, stop_loss_pct=sl)
                    if result == "take_profit":
                        balance *= (1 + tp / 100)
                        position = None
                    elif result == "stop_loss":
                        balance *= (1 + sl / 100)
                        position = None

            results.append((tp, sl, balance))

    best = max(results, key=lambda x: x[2])
    print(f"💹 최적 익절 {best[0]}% / 손절 {best[1]}% → 최종 자본 {best[2]:.2f}")
    return best[0], best[1]

# ✅ 안전한 float 변환
def safe_float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0