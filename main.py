import requests
from bs4 import BeautifulSoup
import time
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")



url = "https://trouverunlogement.lescrous.fr/tools/37/search?bounds=1.4462445_49.241431_3.5592208_48.1201456"

sent_apartments = set()

def send_telegram_message(message):
    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(send_url, data=payload)
        if response.status_code != 200:
            print("Error sending message:", response.text)
    except Exception as e:
        print("Exception occurred while sending message:", e)

while True:
    try:
        response = requests.get(url)
        response.encoding = "utf-8" 
        soup = BeautifulSoup(response.text, "html.parser")
        apt_list = soup.find_all("li", class_="fr-col-12 fr-col-sm-6 fr-col-md-4 svelte-11sc5my fr-col-lg-4")

        for apt in apt_list:
            link_tag = apt.find("a")
            if not link_tag:
                continue
            apt_price_tag = apt.find("p", class_="fr-badge")
            apt_desc_tag = apt.find("p", class_="fr-card__desc")
            apt_price = apt_price_tag.get_text(strip=True) if apt_price_tag else "N/A"
            apt_name = link_tag.get_text(strip=True)
            apt_address = apt_desc_tag.get_text(strip=True) if apt_desc_tag else "N/A"
            apt_url = "https://trouverunlogement.lescrous.fr" + link_tag.get("href", "")
            if apt_url not in sent_apartments:
                sent_apartments.add(apt_url)
                message = (
                    f"*{apt_name}*\n"
                    f"Price: {apt_price}\n"
                    f"Address: {apt_address}\n"
                    f"URL: {apt_url}"
                )
                send_telegram_message(message)
                print("Sent:", message)
    except Exception as e:
        print("Error occurred during scraping or sending:", e)
    time.sleep(60)
