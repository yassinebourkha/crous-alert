"""Une vérification CROUS, prévue pour une exécution planifiée par GitHub Actions."""
import argparse
import json
import logging
import os
from pathlib import Path
import sys
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://trouverunlogement.lescrous.fr"
BOUNDS = "1.4462445_49.241431_3.5592208_48.1201456"
STATE_PATH = Path(os.getenv("STATE_PATH", ".state/sent_apartments.json"))


def session():
    client = requests.Session()
    client.headers["User-Agent"] = "crous-alert/1.0 (personal housing availability monitor)"
    # Ne pas réessayer les POST Telegram : cela pourrait envoyer deux messages.
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET"], respect_retry_after_header=False)
    client.mount("https://", HTTPAdapter(max_retries=retry))
    return client


def soup_at(client, url):
    if urlparse(url).netloc != urlparse(BASE_URL).netloc:
        raise ValueError("Lien de recherche extérieur au site CROUS")
    response = client.get(url, timeout=(10, 30))
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")


def search_url(client):
    if os.getenv("CROUS_SEARCH_URL"):
        return os.environ["CROUS_SEARCH_URL"]
    home = soup_at(client, BASE_URL + "/")
    link = home.select_one('a[href*="/tools/"][href*="/search"]')
    if not link:
        raise ValueError("Campagne CROUS active introuvable")
    path = urljoin(BASE_URL, link["href"]).split("?")[0]
    return path + "?" + urlencode({"bounds": BOUNDS})


def results_from(soup):
    for tag in soup.select('script[type="application/json"][data-sveltekit-fetched]'):
        if "/search/" not in tag.get("data-url", ""):
            continue
        envelope = json.loads(tag.get_text())
        if envelope.get("status") != 200:
            raise ValueError("La recherche CROUS a renvoyé une erreur")
        data = json.loads(envelope["body"])["results"]
        if not isinstance(data.get("items"), list):
            raise ValueError("Liste CROUS invalide")
        return data
    raise ValueError("Résultats CROUS absents : site indisponible ou structure modifiée")


def collect(client):
    url = search_url(client)
    visited, offers, seen_items = set(), {}, set()
    while url:
        if url in visited or len(visited) >= 100:
            raise ValueError("Pagination CROUS incohérente")
        visited.add(url)
        soup = soup_at(client, url)
        data = results_from(soup)
        for item in data["items"]:
            seen_items.add(str(item["id"]))
            if item.get("available") is not True or item.get("inUnavailabilityPeriod"):
                continue
            residence = item.get("residence") or {}
            address = residence.get("address") or "Non précisée"
            if isinstance(address, dict):
                address = " ".join(str(v) for v in address.values() if v)
            rents = [mode["rent"]["min"] / 100 for mode in item.get("occupationModes", [])
                     if mode.get("rent", {}).get("min") is not None]
            price = f"À partir de {min(rents):.2f} €" if rents else "Non précisé"
            detail_url = urljoin(url, f"accommodations/{item['id']}")
            offers[detail_url] = (
                f"Logement CROUS disponible\n{residence.get('label', '')} — {item['label']}\n"
                f"Loyer : {price}\nAdresse : {address}\n{detail_url}"
            )
        next_link = soup.select_one('a.fr-pagination__link--next[href]')
        url = urljoin(url, next_link["href"]) if next_link else None
        if not url and len(seen_items) < data["total"]["value"]:
            raise ValueError("Pagination CROUS incomplète ; aucune alerte envoyée")
    return offers


def load_state(path):
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
        raise ValueError("Historique invalide ; arrêt pour éviter les doublons")
    return set(data)


def save_state(path, sent):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(sorted(sent), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def send_telegram(client, token, chat_id, message):
    response = client.post(f"https://api.telegram.org/bot{token}/sendMessage",
                           json={"chat_id": chat_id, "text": message,
                                 "link_preview_options": {"is_disabled": True}},
                           timeout=(10, 30))
    if response.status_code != 200 or response.json().get("ok") is not True:
        raise RuntimeError(f"Envoi Telegram refusé (HTTP {response.status_code})")


def notify(client, offers, sent, path, token, chat_id):
    count = 0
    for url, message in offers.items():
        if url in sent:
            continue
        send_telegram(client, token, chat_id, message)
        sent.add(url)
        # Sauver chaque succès, même si un envoi suivant échoue.
        save_state(path, sent)
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Vérifier le CROUS sans envoyer ni sauvegarder")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    try:
        if not args.dry_run and (not token or not chat_id):
            raise ValueError("Ajouter TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID aux secrets Actions du dépôt")
        sent = load_state(STATE_PATH)
        with session() as client:
            offers = collect(client)
            logging.info("%s logement(s) disponible(s), %s nouveau(x)",
                         len(offers), len(set(offers) - sent))
            if args.dry_run:
                return 0
            count = notify(client, offers, sent, STATE_PATH, token, chat_id)
            logging.info("%s alerte(s) envoyée(s)", count)
        return 0
    except Exception as exc:
        message = str(exc)
        for secret in (token, chat_id):
            if secret:
                message = message.replace(secret, "[SECRET]")
        logging.error("%s", message)
        return 1


if __name__ == "__main__":
    sys.exit(main())
