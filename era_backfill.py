"""
E-RA ENERGY BACKFILL - Lấy dữ liệu LỊCH SỬ (trước đây) từ E-Ra, gộp vào era_energy.csv

Khác với era_collector_once.py (chỉ lấy 1 điểm mới nhất mỗi lần chạy),
script này quét ngược lại nhiều ngày trước, lấy TOÀN BỘ điểm dữ liệu thô
(ghi mỗi 10 phút) trong từng ngày, rồi tổng hợp thành các mốc THEO GIỜ
(giống định dạng era_collector_once.py đang dùng), và GỘP vào file CSV
hiện có (nếu đã có), không ghi đè mất dữ liệu cũ.

CHỈ CẦN CHẠY 1 LẦN (hoặc vài lần nếu muốn kéo thêm) - sau đó
era_collector_once.py sẽ tiếp tục chạy nối tiếp mỗi giờ như bình thường.

CÁCH DÙNG:
    export EOH_TOKEN="token_cua_ban"
    pip install requests
    python era_backfill.py --days 30
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

TOKEN = os.environ.get("EOH_TOKEN")
CONFIG_ID = 175199
CSV_FILE = "era_energy.csv"
URL = "https://backend.eoh.io/api/chip_manager/configs/value_history_v3/"


def to_vn_dt(x):
    """Chuyển timestamp raw từ API (epoch hoặc chuỗi ISO UTC) sang datetime có timezone VN."""
    if isinstance(x, (int, float)):
        ts = x / 1000 if x > 10**12 else x
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
    else:
        s = str(x).replace("Z", "+00:00")
        dt_utc = datetime.fromisoformat(s)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(VN_TZ)


def fetch_day_points(date_from_utc, date_to_utc, session):
    """Gọi API lấy toàn bộ điểm raw (head+tail) trong 1 khoảng thời gian (thường là 1 ngày)."""
    headers = {
        "Authorization": f"Token {TOKEN}",
        "Accept": "application/json",
    }
    params = {
        "configs": CONFIG_ID,
        "date_from": date_from_utc.strftime("%Y-%m-%dT%H:%M:%S"),
        "date_to": date_to_utc.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    resp = session.get(URL, params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"  [!] Lỗi API ({resp.status_code}) cho khoảng "
              f"{params['date_from']} -> {params['date_to']}: {resp.text[:200]}")
        return []

    data = resp.json()
    try:
        config = data["configs"][0]
    except (KeyError, IndexError):
        return []

    points = config.get("head", []) + config.get("tail", [])
    return points


def resample_to_hourly(all_points):
    """
    Nhận vào list điểm thô [{"x":.., "y":..}, ...] (đã gộp nhiều ngày),
    trả về dict {Time (chuỗi giờ VN "YYYY-MM-DD HH:00:00"): giá trị lũy kế}
    bằng cách lấy điểm CUỐI CÙNG trong mỗi giờ (giống cách hệ thống ghi theo giờ).
    """
    # Chuyển hết sang (datetime_vn, value), sắp xếp theo thời gian
    parsed = []
    for p in all_points:
        try:
            dt_vn = to_vn_dt(p["x"])
            parsed.append((dt_vn, p["y"]))
        except Exception:
            continue
    parsed.sort(key=lambda t: t[0])

    hourly = {}
    for dt_vn, value in parsed:
        hour_floor = dt_vn.replace(minute=0, second=0, microsecond=0)
        key = hour_floor.strftime("%Y-%m-%d %H:%M:%S")
        # Giữ điểm CUỐI CÙNG quan sát được trong giờ đó (gần nhất với cuối giờ)
        hourly[key] = value

    return hourly


def load_existing_csv():
    """Đọc file CSV hiện có (nếu có), trả về dict {Time: Accumulated}."""
    existing = {}
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            next(reader, None)  # bỏ header
            for row in reader:
                if len(row) < 2:
                    continue
                try:
                    existing[row[0]] = float(row[1])
                except ValueError:
                    continue
    return existing


def write_csv(merged_dict):
    """Ghi lại toàn bộ CSV từ dict {Time: Accumulated}, tự tính lại Consumption theo thứ tự thời gian."""
    times_sorted = sorted(merged_dict.keys())

    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Time", "Accumulated", "Consumption"])

        prev_value = None
        for t in times_sorted:
            value = merged_dict[t]
            if prev_value is None:
                consumption = 0
            else:
                consumption = round(value - prev_value, 3)
                if consumption < 0:  # công tơ bị reset
                    consumption = 0
            writer.writerow([t, value, consumption])
            prev_value = value

    return len(times_sorted)


def main():
    parser = argparse.ArgumentParser(description="Lấy dữ liệu lịch sử từ E-Ra")
    parser.add_argument("--days", type=int, default=30,
                         help="Số ngày lấy ngược lại tính từ hiện tại (mặc định 30, "
                              "khớp với thời gian lưu raw data của datastream)")
    args = parser.parse_args()

    if not TOKEN:
        print("LỖI: chưa có Token. Đặt biến môi trường EOH_TOKEN trước khi chạy.")
        sys.exit(1)

    print(f"Bắt đầu lấy dữ liệu {args.days} ngày gần nhất cho config {CONFIG_ID}...")

    now_utc = datetime.now(timezone.utc)
    all_points = []

    import requests
    session = requests.Session()

    # Quét theo từng ngày (24h) để đảm bảo lấy đủ độ phân giải raw (10 phút/điểm),
    # tránh trường hợp API downsample bớt dữ liệu khi hỏi 1 khoảng quá dài.
    for i in range(args.days):
        date_to = now_utc - timedelta(days=i)
        date_from = date_to - timedelta(days=1)

        print(f"  Ngày {i+1}/{args.days}: {date_from.strftime('%Y-%m-%d')} "
              f"-> {date_to.strftime('%Y-%m-%d')} ...", end=" ")

        points = fetch_day_points(date_from, date_to, session)
        print(f"{len(points)} điểm")
        all_points.extend(points)

        time.sleep(0.3)  # tránh gọi API quá dồn dập

    if not all_points:
        print("Không lấy được điểm dữ liệu nào. Kiểm tra lại Token / CONFIG_ID.")
        sys.exit(1)

    print(f"\nTổng cộng {len(all_points)} điểm thô (có thể trùng lặp giữa các ngày).")

    hourly = resample_to_hourly(all_points)
    print(f"Sau khi gộp theo giờ: {len(hourly)} mốc giờ duy nhất.")

    existing = load_existing_csv()
    print(f"Dữ liệu đã có sẵn trong {CSV_FILE}: {len(existing)} dòng.")

    merged = {**existing, **hourly}  # dữ liệu mới lấy sẽ bổ sung/khớp lại theo giờ
    total = write_csv(merged)

    print(f"\nHoàn tất! Đã ghi {total} dòng vào {CSV_FILE}.")


if __name__ == "__main__":
    main()
