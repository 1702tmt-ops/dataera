"""
E-RA ENERGY MONITOR - Bản chạy 1 lần (dùng cho GitHub Actions)

Khác với bản chạy vòng lặp (while True) trên máy cá nhân, bản này:
- Chạy 1 LẦN rồi kết thúc (vì lịch chạy mỗi giờ do GitHub Actions lo,
  không phải do code tự lặp/tự đợi).
- Đọc Token từ biến môi trường EOH_TOKEN (KHÔNG ghi cứng token vào code)
  để an toàn khi đẩy code lên GitHub.
- Vẫn giữ nguyên logic: giờ Việt Nam, tính tiêu thụ = giá trị lũy kế hiện tại
  trừ giá trị lũy kế lần trước (đọc từ dòng cuối CSV), xử lý trường hợp
  công tơ bị reset.

CÁCH DÙNG THỦ CÔNG (nếu muốn test trên máy trước khi đẩy lên GitHub):
    export EOH_TOKEN="dan_token_cua_ban_vao_day"     (Windows: set EOH_TOKEN=...)
    pip install requests
    python era_collector_once.py
"""

import requests
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ==============================
# CẤU HÌNH
# ==============================

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

TOKEN = os.environ.get("EOH_TOKEN")

CONFIG_ID = 175199

CSV_FILE = "era_energy.csv"

URL = "https://backend.eoh.io/api/chip_manager/configs/value_history_v3/"


# ==============================
# XỬ LÝ THỜI GIAN
# ==============================

def to_vn_time_str(x):
    """Chuyển timestamp từ API (epoch hoặc chuỗi ISO UTC) sang giờ Việt Nam."""
    try:
        if isinstance(x, (int, float)):
            ts = x / 1000 if x > 10**12 else x
            dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            s = str(x).replace("Z", "+00:00")
            dt_utc = datetime.fromisoformat(s)
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        return dt_utc.astimezone(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(x)


# ==============================
# LẤY GIÁ TRỊ TỪ E-RA
# ==============================

def get_latest_value():
    if not TOKEN:
        print("LỖI: chưa có Token. Hãy đặt biến môi trường EOH_TOKEN "
              "(trên GitHub Actions: thêm vào Secrets tên EOH_TOKEN).")
        sys.exit(1)

    headers = {
        "Authorization": f"Token {TOKEN}",
        "Accept": "application/json",
    }

    now_utc = datetime.now(timezone.utc)
    date_to = now_utc.strftime("%Y-%m-%dT%H:%M:%S")
    date_from = (now_utc - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")

    params = {
        "configs": CONFIG_ID,
        "date_from": date_from,
        "date_to": date_to,
    }

    response = requests.get(URL, params=params, headers=headers, timeout=30)

    if response.status_code != 200:
        print("Lỗi API:", response.status_code)
        print(response.text)
        return None, None

    data = response.json()
    config = data["configs"][0]
    points = config["head"] + config["tail"]

    if not points:
        return None, None

    latest = points[-1]
    timestamp_vn = to_vn_time_str(latest["x"])
    value = latest["y"]

    return timestamp_vn, value


# ==============================
# CSV
# ==============================

def create_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(["Time", "Accumulated", "Consumption"])


def load_previous_value():
    if not os.path.exists(CSV_FILE):
        return None, None

    with open(CSV_FILE, "r", encoding="utf-8-sig") as file:
        rows = list(csv.reader(file))

    if len(rows) <= 1:
        return None, None

    last_row = rows[-1]
    try:
        return last_row[0], float(last_row[1])
    except (IndexError, ValueError):
        return None, None


def save_data(timestamp, value, consumption):
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, value, consumption])


# ==============================
# CHẠY 1 LẦN
# ==============================

def main():
    create_csv()
    last_time, previous_value = load_previous_value()

    timestamp, value = get_latest_value()

    if value is None:
        print("Không lấy được dữ liệu lần này.")
        return

    if timestamp == last_time:
        print(f"[{timestamp}] Dữ liệu chưa cập nhật so với lần trước, bỏ qua.")
        return

    if previous_value is None:
        consumption = 0
        print("Giá trị ban đầu:", value)
    else:
        consumption = round(value - previous_value, 3)
        if consumption < 0:  # công tơ bị reset
            consumption = 0
        print("Thời gian:", timestamp)
        print("Giá trị tích lũy:", value)
        print("Tiêu thụ kỳ này:", consumption)

    save_data(timestamp, value, consumption)
    print("Đã lưu vào:", CSV_FILE)


if __name__ == "__main__":
    main()
