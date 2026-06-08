import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

# --- CONFIGURAZIONE ---
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "pollini-milano")  # il tuo topic ntfy
# ----------------------

LIVELLI_EMOJI = {
    "assente": "🟢",
    "basso": "🟡",
    "medio": "🟠",  # "Media" nel sito
    "media": "🟠",
    "alto": "🔴",
    "molto alto": "🔴🔴",
}

def get_emoji(livello):
    livello_lower = livello.strip().lower()
    return LIVELLI_EMOJI.get(livello_lower, "⚪") + " " + livello.strip()

def scrape_pollini():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept-Language": "it-IT,it;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }
    url = "https://www.3bmeteo.com/meteo/milano/pollini"
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.text

def _estrai_livello_frassino(day_section):
    for row in day_section.find_all(
        "div", class_=lambda c: c and "space-between" in c
    ):
        name_tag = row.find("span", class_="ds-body-medium")
        if not name_tag:
            continue
        nome = name_tag.get_text(strip=True).rstrip(":")
        if nome.lower() != "frassino":
            continue
        level_tag = row.find("div", class_=lambda c: c and "tag" in c)
        if level_tag:
            return level_tag.get_text(strip=True)
    return None


def parse_pollini(html):
    soup = BeautifulSoup(html, "html.parser")
    risultati = []

    day_labels = {}
    for tab in soup.select("nav.tab-bar a.tab"):
        href = tab.get("href", "")
        if href.startswith("#"):
            day_labels[href[1:]] = tab.get_text(strip=True)

    previsioni = []
    for day_section in soup.find_all("div", class_="content-day"):
        day_id = day_section.get("id")
        if not day_id:
            continue

        livello = _estrai_livello_frassino(day_section)
        if not livello:
            continue

        giorno = day_labels.get(day_id, f"Giorno {day_id}")
        try:
            numero = int(day_id)
        except ValueError:
            numero = len(previsioni)

        previsioni.append((numero, giorno, livello))

    previsioni.sort(key=lambda x: x[0])
    if previsioni:
        risultati.append(("Frassino", previsioni))

    return risultati

def format_message(dati):
    oggi = datetime.now()
    intestazione = f"🌿 Pollini Milano — {oggi.strftime('%d/%m/%Y')}\n"
    intestazione += "─" * 28 + "\n"

    corpo = ""
    for nome, previsioni in dati:
        if "frassino" not in nome.lower():
            continue
        corpo += f"\n🌱 {nome}\n"
        for _, giorno, livello in previsioni:
            emoji_livello = get_emoji(livello)
            corpo += f"  {giorno}: {emoji_livello}\n"

    if not corpo:
        return intestazione + "\n⚠️ Nessun dato trovato. Il sito potrebbe aver cambiato struttura."

    return intestazione + corpo

def send_ntfy(message, topic):
    url = f"https://ntfy.sh/{topic}"
    oggi = datetime.now().strftime("%d/%m")
    headers = {
        "Title": f"Pollini Milano {oggi}",
        "Priority": "default",
        "Tags": "seedling",
    }
    resp = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=10)
    resp.raise_for_status()
    print(f"Notifica inviata a ntfy.sh/{topic}")

def main():
    print("Scarico dati pollini...")
    try:
        html = scrape_pollini()
        dati = parse_pollini(html)
        messaggio = format_message(dati)
        print(messaggio)
        send_ntfy(messaggio, NTFY_TOPIC)
    except Exception as e:
        # Invia comunque una notifica di errore
        errore = f"⚠️ Errore pollini Milano: {str(e)}"
        print(errore)
        try:
            send_ntfy(errore, NTFY_TOPIC)
        except Exception:
            pass

if __name__ == "__main__":
    main()
