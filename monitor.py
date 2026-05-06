import requests
import os
import random
import time
from datetime import datetime, timezone, timedelta

# ===== 설정 =====
GOODS_CODE  = os.environ.get("GOODS_CODE", "26004520")
SPORTS_CODE = "07001"
TEAM_CODE   = "PB004"
PLAY_DATE   = "20260510"
PERF_URL    = (
    "https://ticket.interpark.com/Contents/Sports/GoodsInfo"
    f"?SportsCode={SPORTS_CODE}&TeamCode={TEAM_CODE}"
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

def get_headers():
    return {
        "referer": "https://ticket.interpark.com/",
        "user-agent": random.choice(USER_AGENTS),
        "accept": "application/json, text/plain, */*",
        "accept-language": "ko-KR,ko;q=0.9",
        "sec-ch-ua-mobile": "?0",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
    }


# ===== 잔여석 조회 =====
def check_remain() -> list[dict] | None:
    url = (
        f"https://api-ticketfront.interpark.com/v1/goods/{GOODS_CODE}"
        f"/playSeq/PlayDate/{PLAY_DATE}/ALL"
    )
    for attempt in range(1, 4):
        try:
            time.sleep(random.uniform(2, 4))
            resp = requests.get(url, headers=get_headers(), timeout=15)
            if resp.status_code == 403:
                print(f"  [403 차단 | 시도 {attempt}/3]")
                time.sleep(random.uniform(5, 8))
                continue
            resp.raise_for_status()
            return resp.json().get("data", {}).get("remainSeat", [])
        except Exception as e:
            print(f"  [오류 | 시도 {attempt}/3] {e}")
            time.sleep(random.uniform(3, 5))
    return None


# ===== 텔레그램 알림 =====
def send_telegram(message: str):
    resp = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": message},
        timeout=10,
    )
    if not resp.ok:
        print(f"[텔레그램 전송 실패] {resp.status_code} {resp.text}")
    else:
        print("[텔레그램 전송 성공]")


# ===== 메인 =====
def main():
    formatted_date = f"{PLAY_DATE[:4]}년 {PLAY_DATE[4:6]}월 {PLAY_DATE[6:]}일"
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).strftime("%m/%d %H:%M")

    send_telegram(
        f"🔍 취소표 모니터링 시작\n"
        f"📅 {formatted_date}\n"
        f"🎟 goodsCode: {GOODS_CODE}\n"
        f"🕐 {now} (KST)"
    )
    print(f"🔍 [{formatted_date}] 모니터링 시작")

    remain = check_remain()
    print(f"  remainSeat: {remain}")

    if remain is None:
        send_telegram(
            f"⚠️ API 접근 차단 (403)\n"
            f"📅 {formatted_date}\n"
            f"🕐 {now} (KST)\n\n"
            f"인터파크 서버가 GitHub Actions IP를 차단했습니다.\n"
            f"잠시 후 자동으로 재시도됩니다."
        )
        print("⚠️ 403 차단 - 다음 실행에서 재시도")
        return

    # 잔여석 있고 휠체어석 제외
    available = [
        r for r in remain
        if r.get("remainCnt", 0) > 0 and "휠체어" not in r.get("seatGradeName", "")
    ]
    lru_available = [r for r in available if "1루" in r.get("seatGradeName", "")]

    if available:
        other_available = [r for r in available if "1루" not in r.get("seatGradeName", "")]

        seats_text = ""
        if lru_available:
            seats_text += "[ 1루 ]\n"
            seats_text += "\n".join(
                f"  ✅ {r['seatGradeName']} - 잔여 {r['remainCnt']}석"
                for r in lru_available
            )
        if other_available:
            if seats_text:
                seats_text += "\n\n"
            seats_text += "[ 기타 ]\n"
            seats_text += "\n".join(
                f"  {r['seatGradeName']} - 잔여 {r['remainCnt']}석"
                for r in other_available
            )

        title = "🚨 1루 취소표 발생!" if lru_available else "🚨 취소표 발생! (1루 없음)"
        send_telegram(
            f"{title}\n"
            f"📅 {formatted_date}\n"
            f"🕐 {now} (KST)\n\n"
            f"{seats_text}\n\n"
            f"🔗 {PERF_URL}"
        )
        print(f"✅ 취소표 알림 전송! (1루: {len(lru_available)}개)")
    else:
        send_telegram(
            f"😔 취소표 없음 (전 좌석 매진)\n"
            f"📅 {formatted_date}\n"
            f"🕐 {now} (KST)"
        )
        print("😔 취소표 없음")


if __name__ == "__main__":
    main()
