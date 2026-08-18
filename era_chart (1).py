"""
E-RA ENERGY CHART - Vẽ biểu đồ điện năng tiêu thụ từ file era_energy.csv
(file này do era_collector.py tạo ra)

4 chế độ xem:
    hour  -> tiêu thụ theo từng giờ trong 1 NGÀY cụ thể
    day   -> tổng tiêu thụ theo từng ngày trong 1 THÁNG cụ thể
    month -> tổng tiêu thụ theo từng tháng trong 1 NĂM cụ thể
    year  -> tổng tiêu thụ theo từng năm (toàn bộ dữ liệu)

CÁCH DÙNG:
    pip install pandas matplotlib

    python era_chart.py --view hour  --date 2026-08-18
    python era_chart.py --view day   --month 2026-08
    python era_chart.py --view month --year 2026
    python era_chart.py --view year

    Nếu không truyền --date/--month/--year, script tự lấy ngày/tháng/năm
    GẦN NHẤT có trong dữ liệu.

Mỗi lần chạy, biểu đồ sẽ:
    - Hiện lên màn hình (nếu máy bạn hỗ trợ hiển thị đồ họa)
    - Đồng thời lưu thành file ảnh .png trong cùng thư mục
"""

import argparse
import sys
import pandas as pd
import matplotlib.pyplot as plt

CSV_FILE = "era_energy.csv"


def load_data(csv_file=CSV_FILE):
    try:
        df = pd.read_csv(csv_file, encoding="utf-8-sig")
    except FileNotFoundError:
        print(f"Không tìm thấy file: {csv_file}")
        print("Hãy chạy era_collector.py trước để tạo dữ liệu.")
        sys.exit(1)

    if df.empty:
        print("File CSV chưa có dữ liệu nào.")
        sys.exit(1)

    df["Time"] = pd.to_datetime(df["Time"])
    df = df.sort_values("Time").set_index("Time")
    return df


def chart_by_hour(df, date_str=None):
    """Biểu đồ tiêu thụ theo từng giờ trong 1 ngày cụ thể."""
    if date_str is None:
        date_str = df.index[-1].strftime("%Y-%m-%d")

    day_data = df[df.index.strftime("%Y-%m-%d") == date_str]

    if day_data.empty:
        print(f"Không có dữ liệu cho ngày {date_str}")
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(day_data.index.strftime("%H:%M"), day_data["Consumption"], color="#2E8B57")
    ax.set_title(f"Điện năng tiêu thụ theo giờ - Ngày {date_str}")
    ax.set_xlabel("Giờ")
    ax.set_ylabel("Tiêu thụ (kWh)")
    plt.xticks(rotation=45)
    plt.tight_layout()

    out_file = f"chart_hour_{date_str}.png"
    plt.savefig(out_file, dpi=150)
    print(f"Đã lưu biểu đồ: {out_file}")
    plt.show()


def chart_by_day(df, month_str=None):
    """Biểu đồ tổng tiêu thụ theo từng ngày trong 1 tháng cụ thể."""
    if month_str is None:
        month_str = df.index[-1].strftime("%Y-%m")

    month_data = df[df.index.strftime("%Y-%m") == month_str]

    if month_data.empty:
        print(f"Không có dữ liệu cho tháng {month_str}")
        return

    daily = month_data["Consumption"].resample("D").sum()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(daily.index.strftime("%d"), daily.values, color="#4682B4")
    ax.set_title(f"Điện năng tiêu thụ theo ngày - Tháng {month_str}")
    ax.set_xlabel("Ngày")
    ax.set_ylabel("Tiêu thụ (kWh)")
    plt.tight_layout()

    out_file = f"chart_day_{month_str}.png"
    plt.savefig(out_file, dpi=150)
    print(f"Đã lưu biểu đồ: {out_file}")
    plt.show()


def chart_by_month(df, year_str=None):
    """Biểu đồ tổng tiêu thụ theo từng tháng trong 1 năm cụ thể."""
    if year_str is None:
        year_str = df.index[-1].strftime("%Y")

    year_data = df[df.index.strftime("%Y") == year_str]

    if year_data.empty:
        print(f"Không có dữ liệu cho năm {year_str}")
        return

    monthly = year_data["Consumption"].resample("ME").sum()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(monthly.index.strftime("%m"), monthly.values, color="#DAA520")
    ax.set_title(f"Điện năng tiêu thụ theo tháng - Năm {year_str}")
    ax.set_xlabel("Tháng")
    ax.set_ylabel("Tiêu thụ (kWh)")
    plt.tight_layout()

    out_file = f"chart_month_{year_str}.png"
    plt.savefig(out_file, dpi=150)
    print(f"Đã lưu biểu đồ: {out_file}")
    plt.show()


def chart_by_year(df):
    """Biểu đồ tổng tiêu thụ theo từng năm (toàn bộ dữ liệu có sẵn)."""
    yearly = df["Consumption"].resample("YE").sum()

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(yearly.index.strftime("%Y"), yearly.values, color="#B22222")
    ax.set_title("Điện năng tiêu thụ theo năm")
    ax.set_xlabel("Năm")
    ax.set_ylabel("Tiêu thụ (kWh)")
    plt.tight_layout()

    out_file = "chart_year.png"
    plt.savefig(out_file, dpi=150)
    print(f"Đã lưu biểu đồ: {out_file}")
    plt.show()


def main():
    parser = argparse.ArgumentParser(description="Vẽ biểu đồ điện năng từ era_energy.csv")
    parser.add_argument("--view", choices=["hour", "day", "month", "year"], required=True,
                         help="Chế độ xem: hour / day / month / year")
    parser.add_argument("--date", help="Ngày cụ thể, định dạng YYYY-MM-DD (dùng cho --view hour)")
    parser.add_argument("--month", help="Tháng cụ thể, định dạng YYYY-MM (dùng cho --view day)")
    parser.add_argument("--year", help="Năm cụ thể, định dạng YYYY (dùng cho --view month)")
    parser.add_argument("--csv", default=CSV_FILE, help="Đường dẫn tới file CSV (mặc định: era_energy.csv)")

    args = parser.parse_args()
    df = load_data(args.csv)

    if args.view == "hour":
        chart_by_hour(df, args.date)
    elif args.view == "day":
        chart_by_day(df, args.month)
    elif args.view == "month":
        chart_by_month(df, args.year)
    elif args.view == "year":
        chart_by_year(df)


if __name__ == "__main__":
    main()
