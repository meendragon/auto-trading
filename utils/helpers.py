import yfinance as yf
import pandas as pd
import numpy as np
from tqdm import tqdm

# -----------------------------
# 거래소 코드 매핑
# -----------------------------
def map_exchange_code(short_code: str) -> str:
    mapping = {
        "NYS": "NYSE",
        "NAS": "NASD",
        "AMS": "AMEX",
        "ARC": "ARCA",
        "BTS": "BATS",
        "NCM": "NCM",
    }
    return mapping.get(short_code.upper(), short_code.upper())

# -----------------------------
# 기술적 지표 계산 (MA, Bollinger)
# -----------------------------
def add_indicators(df, window=20):
    df["ma20"] = df["close"].rolling(window=window).mean()
    df["stddev"] = df["close"].rolling(window=window).std()
    df["upper"] = df["ma20"] + (df["stddev"] * 2)
    df["lower"] = df["ma20"] - (df["stddev"] * 2)
    df["ma5"] = df["close"].rolling(window=5).mean()

    df = df.dropna().reset_index(drop=True)
    return df

# -----------------------------
# 데이터 가져오기 (3분, 5분, 일봉 선택 가능)
# -----------------------------
def fetch_data(ticker, interval="5m", period="5d"):
    """
    interval: "3m", "5m", "1d"
    period:  "5d", "1mo", "3mo" 등
    """
    data = yf.download(ticker, interval=interval, period=period,
                       progress=False, auto_adjust=False)
    data = data.rename(columns={"Close": "close", "High": "high", "Low": "low"})
    data = add_indicators(data)
    return data

# -----------------------------
# 매수 조건
# -----------------------------
def check_buy_condition(df, current_price, mode="lower_recover", **kwargs):
    """
    mode:
      - "lower_recover" : 볼린저 하단선 이탈 후 회복
      - "ma_cross"      : 단기 MA가 중기 MA 상향 돌파
      - "near_ma"       : 현재가가 특정 이동평균선 근처
      - "ma5_touch"     : 상승 추세 중 MA5 근접 후 반등
      - "combo"         : 복합 조건
    """
    # 데이터 최소 2행 이상 확보
    if len(df) < 2:
        return False

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close_prev = prev["close"].item()
    ma5_prev = prev["ma5"].item()
    ma20_prev = prev["ma20"].item()
    lower_prev = prev["lower"].item()

    close_now = latest["close"].item()
    ma5_now = latest["ma5"].item()
    ma20_now = latest["ma20"].item()
    lower_now = latest["lower"].item()

    # --- 주요 조건 계산 ---

    # (1) 볼린저 하단 이탈 후 회복
    lower_recover = (close_prev < lower_prev) and (current_price > lower_now)

    # (2) 단기 이평이 중기 이평을 상향 돌파
    ma_cross = (ma5_prev < ma20_prev) and (ma5_now > ma20_now)

    # (3) 현재가가 이동평균선 근처 (기본 tolerace=0.001)
    target_ma = kwargs.get("target_ma", "ma20")
    tolerance = kwargs.get("tolerance", 0.001)
    ma_val = ma5_now if target_ma == "ma5" else ma20_now
    near_ma = abs((current_price - ma_val) / ma_val) <= tolerance

    # (4) 상승추세 중 MA5 근접 반등
    ma5_touch = (
        (ma5_now > ma20_now) and                 # 상승 추세
        abs((current_price - ma5_now) / ma5_now) <= 0.001 and  # MA5 근접
        (current_price > close_prev)             # 직전 종가 대비 반등
    )

    # --- 모드별 분기 ---
    if mode == "lower_recover":
        return lower_recover
    elif mode == "ma_cross":
        return ma_cross
    elif mode == "near_ma":
        return near_ma
    elif mode == "ma5_touch":
        return ma5_touch
    elif mode == "combo":
        # 복합 전략 예시: 하단 회복 + 단기이평 반등
        strict = kwargs.get("strict", False)
        if strict:
            return lower_recover and ma_cross and ma5_touch
        else:
            return (lower_recover and ma5_touch) or ma_cross
    else:
        raise ValueError(f"Unknown mode: {mode}")

# -----------------------------
# 매도 조건 (익절/손절)
# -----------------------------
def check_sell_condition(entry_price, current_price,
                         take_profit_pct=1.0, stop_loss_pct=-3.0):
    profit_rate = (current_price - entry_price) / entry_price * 100
    if profit_rate >= take_profit_pct:
        return "take_profit"
    elif profit_rate <= stop_loss_pct:
        return "stop_loss"
    return None

# -----------------------------
# 브루트포스 최적화
# -----------------------------
def optimize_thresholds_bruteforce(ticker,
                                   interval="5m",
                                   period="5d",
                                   take_profit_range=(0.5, 2.0, 0.5),
                                   stop_loss_range=(-5.0, -1.0, 1.0),
                                   modes=("lower_recover", "ma_cross", "ma5_touch", "combo")):
    df = fetch_data(ticker, interval=interval, period=period)
    results = []

    take_profit_values = np.arange(*take_profit_range)
    stop_loss_values = np.arange(*stop_loss_range)

    for mode in tqdm(modes, desc="Mode Loop"):
        for tp in take_profit_values:
            for sl in stop_loss_values:
                balance = 10000
                position = None
                entry_price = 0.0
                wins = 0
                losses = 0

                for i in range(2, len(df)):
                    row = df.iloc[i]
                    high = row["high"].item()
                    low = row["low"].item()
                    close = row["close"].item()
                    sub_df = df.iloc[:i + 1]

                    if len(sub_df) < 2:
                        continue

                    # 매수
                    if position is None:
                        if check_buy_condition(sub_df, close, mode=mode):
                            entry_price = low  # ✅ 다음 캔들에서 저가 기준으로 진입했다고 가정
                            position = True

                    # 매도
                    else:
                        target_profit_price = entry_price * (1 + tp / 100)
                        target_loss_price = entry_price * (1 + sl / 100)

                        # ✅ 고가가 익절가 도달했으면 익절
                        if high >= target_profit_price:
                            balance *= (1 + tp / 100)
                            wins += 1
                            position = None

                        # ✅ 저가가 손절가 도달했으면 손절
                        elif low <= target_loss_price:
                            balance *= (1 + sl / 100)
                            losses += 1
                            position = None

                total_trades = wins + losses
                win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

                results.append((interval, mode, tp, sl, balance, win_rate, total_trades))

    # 최종 결과
    best = max(results, key=lambda x: x[4])
    print(
        f"\n🏆 [{best[0]}] 최적 모드: {best[1]} | 익절 {best[2]}% / 손절 {best[3]}%"
        f" → 최종 자본 ${best[4]:.2f} | 승률 {best[5]:.1f}% ({best[6]}회 거래)"
    )
    return best

# ✅ 안전한 float 변환
def safe_float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0