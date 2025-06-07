import os
import csv
import time
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# ================= CẤU HÌNH =================
# Thay Telegram thành Discord webhook
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1380807005962371214/ZvDzloveJjS3syPVgMGvG_SpSeOeX2_NyV4XO4YJ4TXpt65XzxJJsFPYGwyEZu2Wd5Mc"  # Thay bằng webhook thực
BACKUP_SOURCE = "https://www.investing.com/economic-calendar/"  # Nguồn dự phòng

# ================ TIỆN ÍCH ==================
def send_discord_alert(message):
    """Gửi cảnh báo qua Discord Webhook"""
    try:
        data = {
            "content": message
        }
        response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
        if response.status_code != 204:
            print(f"⚠️ Lỗi gửi Discord: {response.status_code} {response.text}")
    except Exception as e:
        print(f"⚠️ Lỗi gửi Discord: {e}")

def log_error(error_msg):
    """Ghi log lỗi"""
    with open("scraper_errors.log", "a") as f:
        f.write(f"{datetime.now()}: {error_msg}\n")

# ============ CORE SCRAPING ================
class ForexFactoryScraper:
    def __init__(self):
        self.driver = self._init_driver()
        self.last_update = None

    def _init_driver(self):
        """Khởi tạo trình duyệt ảo"""
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-webgl")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        return webdriver.Chrome(options=options)

    def _scrape_events(self):
        """Trích xuất dữ liệu từ ForexFactory"""
        try:
            print("🌐 Đang truy cập ForexFactory...")
            self.driver.get("https://www.forexfactory.com/calendar")

            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".calendar__row"))
            )
            time.sleep(3)  # Đợi render JS

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            events = []
            high_impact_count = 0

            for row in soup.select('.calendar__row:not(.calendar__row--header)'):
                try:
                    if not row.select_one('.calendar__time'):
                        continue

                    event_data = {
                        'Time': row.select_one('.calendar__time').get_text(strip=True) or "All Day",
                        'Currency': row.select_one('.calendar__currency').get_text(strip=True) if row.select_one('.calendar__currency') else "N/A",
                        'Event': row.select_one('.calendar__event').get_text(strip=True) if row.select_one('.calendar__event') else "N/A",
                        'Impact': row.select_one('.calendar__impact span')['title'] if row.select_one('.calendar__impact span') else "Unknown",
                        'Actual': row.select_one('.calendar__actual').get_text(strip=True) if row.select_one('.calendar__actual') else "N/A",
                        'Forecast': row.select_one('.calendar__forecast').get_text(strip=True) if row.select_one('.calendar__forecast') else "N/A",
                        'Previous': row.select_one('.calendar__previous').get_text(strip=True) if row.select_one('.calendar__previous') else "N/A"
                    }

                    if "High" in event_data['Impact']:
                        high_impact_count += 1
                        alert_msg = f"🚨 **SỰ KIỆN QUAN TRỌNG**\n{event_data['Time']} {event_data['Currency']} - {event_data['Event']}"
                        send_discord_alert(alert_msg)

                    events.append(event_data)

                except Exception as e:
                    log_error(f"Lỗi xử lý dòng: {str(e)}")
                    continue

            self.last_update = datetime.now().strftime("%Y-%m-%d %H:%M")
            return events, high_impact_count

        except Exception as e:
            log_error(f"Lỗi scrape chính: {str(e)}")
            return None, 0

    def _save_to_csv(self, events):
        """Lưu dữ liệu vào CSV"""
        try:
            os.makedirs("data", exist_ok=True)
            filename = f"data/economic_calendar_{datetime.now().strftime('%Y%m%d')}.csv"

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'Time', 'Currency', 'Event', 'Impact',
                    'Actual', 'Forecast', 'Previous'
                ])
                writer.writeheader()
                writer.writerows(events)

            return filename
        except Exception as e:
            log_error(f"Lỗi lưu file: {str(e)}")
            return None

    def run(self):
        """Chạy quy trình chính"""
        try:

            print("🔄 Bắt đầu cập nhật dữ liệu...")
            events, hi_count = self._scrape_events()

            if not events:
                print("❌ Không lấy được dữ liệu, thử nguồn dự phòng...")
                return False

            saved_file = self._save_to_csv(events)
            if saved_file:
                summary = (
                    f"📊 **CẬP NHẬT THÀNH CÔNG**\n"
                    f"• Sự kiện: {len(events)}\n"
                    f"• High Impact: {hi_count}\n"
                    f"• File: {saved_file}"
                )
                send_discord_alert(summary)
                print(f"✅ Đã lưu {len(events)} sự kiện ({hi_count} High Impact)")
                return True

            return False

        except Exception as e:
            log_error(f"Lỗi hệ thống: {str(e)}")
            return False

    def __del__(self):
        """Dọn dẹp khi đóng"""
        if hasattr(self, 'driver'):
            self.driver.quit()

# =============== MAIN ================
if __name__ == "__main__":
    scraper = ForexFactoryScraper()

    if scraper.run():
        print("🎯 Hoàn tất!")
    else:
        print("💥 Có lỗi xảy ra!")
        send_discord_alert("⚠️ **LỖI HỆ THỐNG**\nScraper gặp sự cố nghiêm trọng!")

    input("Nhấn Enter để đóng...")
