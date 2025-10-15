import time
from utils.api import (
    fetch_access_token,
    fetch_cash_amount,
    get_current_price,
    send_discord_message
)
from utils.order_api import (
    buy_order,
    sell_order
)
from utils.helpers import (
    fetch_5min_data,
    add_indicators,
    check_buy_condition,
    check_sell_condition,
    optimize_sell_thresholds,
    map_exchange_code
)

if __name__ == "__main__":
    ticker = "SES"
    exchange = "NYS"
    access_token = fetch_access_token()
    positions = {}
    take_profit, stop_loss = optimize_sell_thresholds(ticker)
    send_discord_message(f"🧮 초기 브루트포스 결과 → 익절 {take_profit}% / 손절 {stop_loss}%")
    send_discord_message(f"🚀 자동매매 시작 (티커: {ticker})")

    df = None
    last_update = 0
    last_discord_update = 0
    update_interval = 300        # 5분마다 yfinance 갱신 + 브루트포스 재실행
    realtime_interval = 1        # 1초마다 실시간 가격 체크
    discord_interval = 30        # 30초마다 현황 보고

    while True:
        try:
            now = time.time()

            # (1) 5분마다 데이터 갱신 + 브루트포스 재실행
            if df is None or now - last_update >= update_interval:
                send_discord_message(f"📊 [{ticker}] 데이터 및 전략 갱신 중...")
                df = fetch_5min_data(ticker)
                df = add_indicators(df)

                take_profit, stop_loss = optimize_sell_thresholds(ticker)
                send_discord_message(f"🔄 [{ticker}] 갱신된 전략 → 익절 {take_profit}% / 손절 {stop_loss}%")

                last_update = now
                send_discord_message(f"✅ [{ticker}] 지표/전략 갱신 완료")

            # (2) 실시간 현재가
            current_price = get_current_price(ticker, exchange)

            # (a) 보유 포지션 매도 감시
            if ticker in positions:
                entry = positions[ticker]["entry_price"]
                result = check_sell_condition(entry, current_price, take_profit, stop_loss)
                target_profit_price = entry * (1 + take_profit / 100)
                target_loss_price = entry * (1 + stop_loss / 100)

                # ✅ 일정 주기 현황 메시지
                if now - last_discord_update >= discord_interval:
                    send_discord_message(
                        f"📈 {ticker} 현황 | 익절가 {target_profit_price:.3f} / 손절가 {target_loss_price:.3f} | 현재가 {current_price:.3f}"
                    )
                    last_discord_update = now

                # ✅ 매도 조건 충족 시
                if result == "take_profit":
                    send_discord_message(f"✅ {ticker} 익절 조건 충족 → 매도 시도")
                    success = sell_order(ticker, positions[ticker]["qty"],current_price)
                    if success:
                        send_discord_message(f"💰 {ticker} 익절 매도 완료")
                        del positions[ticker]
                    else:
                        send_discord_message(f"❗ {ticker} 익절 매도 실패 → 포지션 유지")

                elif result == "stop_loss":
                    send_discord_message(f"⚠️ {ticker} 손절 조건 충족 → 매도 시도")
                    success = sell_order(ticker, qty, exchange,current_price)
                    if success:
                        send_discord_message(f"💔 {ticker} 손절 매도 완료")
                        del positions[ticker]
                    else:
                        send_discord_message(f"❗ {ticker} 손절 매도 실패 → 포지션 유지")

                time.sleep(realtime_interval)
                continue

            # (b) 포지션 없으면 매수 감시
            if not ticker in positions:
                ma_target = float(df["ma20"].iloc[-1])

                # ✅ 일정 주기 현황 보고
                if now - last_discord_update >= discord_interval:
                    send_discord_message(
                        f"🎯 {ticker} 매수 목표가 {ma_target:.3f} | 현재가 {current_price:.3f}"
                    )
                    last_discord_update = now

                # ✅ 매수 조건 충족 시
                if check_buy_condition(df, current_price):
                    cash = float(fetch_cash_amount())
                    if cash > 100:
                        qty = int((cash * 0.7 ) // current_price)
                        if qty > 0:
                            send_discord_message(f"🟢 {ticker} 매수 조건 충족 → {qty}주 매수 ({current_price} USD)")

                            success = buy_order(ticker, qty, exchange,current_price)

                            if success:  # ✅ 주문 성공 시에만 포지션 추가
                                positions[ticker] = {"entry_price": current_price, "qty": qty}
                                target_profit_price = current_price * (1 + take_profit / 100)
                                target_loss_price = current_price * (1 + stop_loss / 100)
                                send_discord_message(
                                    f"🎯 {ticker} 매수완료 | 익절 {target_profit_price:.3f} / 손절 {target_loss_price:.3f}"
                                )
                            else:
                                send_discord_message(f"❗ {ticker} 매수 실패 → 포지션 미등록")

            time.sleep(realtime_interval)

        except Exception as e:
            send_discord_message(f"[에러 발생] {e}")
            time.sleep(60)