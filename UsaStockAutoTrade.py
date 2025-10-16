import time
from datetime import datetime, time as dtime
from utils.api import (
    fetch_access_token,
    fetch_cash_amount,
    get_current_price,
    send_discord_message,
    check_order_status
)
from utils.order_api import (
    buy_order,
    sell_order,
    cancel_order
)
from utils.helpers import (
    fetch_data,
    add_indicators,
    check_buy_condition,
    check_sell_condition,
    optimize_thresholds_bruteforce,
    map_exchange_code,
    safe_float
)

# ==============================================================
# 🧩 설정 영역 (이곳만 바꾸면 전체 동작 자동 반영)
# ==============================================================
MARKET_CLOSE = dtime(5, 0)
MARKET_OPEN = dtime(18, 0)
TICKER = "SES"               # 종목
EXCHANGE = "NYS"             # 거래소 코드
INTERVAL = "5m"              # 데이터 주기: "2m" / "5m" / "1d"
PERIOD = "60d"                # 데이터 기간: "60d" / "60d" / "max
MODE = "ma5_touch"           # 매수 전략 모드 ("lower_recover", "ma_cross", "combo", "ma5_touch")

UPDATE_INTERVAL = 300        # 5분마다 데이터 및 전략 갱신
REALTIME_INTERVAL = 3       # 실시간 가격 체크 주기 (초)
DISCORD_INTERVAL = 30        # 현황 보고 주기 (초)
INITIAL_BALANCE = 10000      # 초기 자본 (백테스트용)

# ==============================================================

if __name__ == "__main__":
    access_token = fetch_access_token()
    positions = {}

    send_discord_message(f"🚀 자동매매 시작 (티커: {TICKER}, 모드: {MODE})")

    df = None
    last_update = 0
    last_discord_update = 0
    take_profit = 1.0
    stop_loss = -3.0

    while True:
        try:
            now = time.time()
            now_time = datetime.now().time()

            if now_time >= MARKET_CLOSE and now_time <= MARKET_OPEN:
                send_discord_message(f"🛑 장 마감({MARKET_CLOSE.strftime('%H:%M')}) 도달 — 자동매매 종료")
                '''
                # 모든 포지션 정리
                for symbol, pos in positions.items():
                    send_discord_message(f"⚠️ {symbol} 장 마감 전 포지션 청산 시도")
                    sell_order(symbol, pos['qty'], EXCHANGE, get_current_price(symbol, EXCHANGE))

                send_discord_message("✅ 모든 포지션 청산 완료. 프로그램 종료합니다.")
                '''
                break  # 루프 종료


            # (1) 주기적 데이터 갱신 + 전략 재최적화
            if df is None or now - last_update >= UPDATE_INTERVAL:
                send_discord_message(f"📊 [{TICKER}] 데이터 및 전략 갱신 중...")
                df = fetch_data(TICKER, interval=INTERVAL, period=PERIOD)


                take_profit, stop_loss = optimize_thresholds_bruteforce(
                    TICKER,
                    interval=INTERVAL,
                    period=PERIOD,
                    modes=(MODE,)
                )[2:4]

                send_discord_message(
                    f"🔄 [{TICKER}] 갱신된 전략 → {MODE} | 익절 {take_profit}% / 손절 {stop_loss}%"
                )
                last_update = now
                send_discord_message(f"✅ [{TICKER}] 지표/전략 갱신 완료")

            # (2) 실시간 현재가 확인
            current_price = get_current_price(TICKER, EXCHANGE)

            # (a) 보유 포지션 → 매도 감시
            if TICKER in positions:
                entry = positions[TICKER]["entry_price"]
                qty = positions[TICKER]["qty"]
                result = check_sell_condition(entry, current_price, take_profit, stop_loss)

                target_profit_price = entry * (1 + take_profit / 100)
                target_loss_price = entry * (1 + stop_loss / 100)

                if now - last_discord_update >= DISCORD_INTERVAL:
                    send_discord_message(
                        f"📈 {TICKER} 현황 | 익절가 {target_profit_price:.3f} / 손절가 {target_loss_price:.3f} | 현재가 {current_price:.3f}"
                    )
                    last_discord_update = now

                if result == "take_profit":
                    send_discord_message(f"✅ {TICKER} 익절 조건 충족 → 매도 시도")
                    success = sell_order(TICKER, qty, EXCHANGE, current_price)
                    if success:
                        send_discord_message(f"💰 {TICKER} 익절 매도 완료")
                        del positions[TICKER]
                    else:
                        send_discord_message(f"❗ {TICKER} 익절 매도 실패 → 포지션 유지")

                elif result == "stop_loss":
                    send_discord_message(f"⚠️ {TICKER} 손절 조건 충족 → 매도 시도")
                    success = sell_order(TICKER, qty, EXCHANGE, current_price)
                    if success:
                        send_discord_message(f"💔 {TICKER} 손절 매도 완료")
                        del positions[TICKER]
                    else:
                        send_discord_message(f"❗ {TICKER} 손절 매도 실패 → 포지션 유지")

                time.sleep(REALTIME_INTERVAL)
                continue

            # (b) 포지션 없음 → 매수 감시
            if TICKER not in positions:
                if now - last_discord_update >= DISCORD_INTERVAL:
                    ma_target = df["ma20"].iloc[-1].item()
                    send_discord_message(f"🎯 {TICKER} 매수 감시 중 | 모드 {MODE} | MA20={ma_target:.3f}, 현재가={current_price:.3f}")
                    last_discord_update = now

                if check_buy_condition(df, current_price, mode=MODE):
                    cash = float(fetch_cash_amount())
                    if cash > 100:
                        qty = int((cash * 1.0) // current_price)
                        if qty > 0:
                            send_discord_message(f"🟢 {TICKER} 매수 조건 충족 ({MODE}) → {qty}주 매수 시도 ({current_price} USD)")
                            success, odno = buy_order(TICKER, qty, EXCHANGE, current_price)
                            if success:
                                order_info = check_order_status(odno, symbol=TICKER, exchange=EXCHANGE)
                                if order_info:
                                    latest = order_info[-1]  # 마지막 체결내역
                                    nccs_qty = float(latest.get("nccs_qty", 0))
                                    total_ccld = sum(float(o.get("ft_ccld_qty", 0)) for o in order_info)

                                    send_discord_message(
                                        f"📊 {TICKER} 주문번호 {odno}\n"
                                        f"총 체결수량: {total_ccld}주 / 미체결수량: {nccs_qty}주\n"
                                        f"상태: {latest.get('prcs_stat_name')}"
                                    )
                                    if nccs_qty > 0: #미체결이 하나라도 잇으면 취소해야지 일단
                                        success, cancel_no = cancel_order(TICKER, odno, nccs_qty, EXCHANGE)
                                        if success:
                                            print("✅ 취소 완료:", cancel_no)
                                        else:
                                            print("❌ 취소 실패")

                                    if total_ccld > 0: #산게 하나라도 잇다면 포지션 돌려야지
                                        positions[TICKER] = {"entry_price": current_price, "qty": qty}
                                        tp_price = current_price * (1 + take_profit / 100)
                                        sl_price = current_price * (1 + stop_loss / 100)
                                        send_discord_message(f"🎯 {TICKER} 매수완료 | 익절 {tp_price:.3f} / 손절 {sl_price:.3f}")

                                else:
                                    send_discord_message(f"❗체결내역 없음: 주문번호 {odno}")


                            else:
                                send_discord_message(f"❗ {TICKER} 매수 실패 → 포지션 미등록")

            time.sleep(REALTIME_INTERVAL)

        except Exception as e:
            send_discord_message(f"[에러 발생] {e}")
            time.sleep(60)