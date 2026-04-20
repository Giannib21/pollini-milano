import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

# --- CONFIGURAZIONE ---
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "pollini-milano")  # il tuo topic ntfy
# ----------------------

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]

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

def parse_pollini(html):
    soup = BeautifulSoup(html, "html.parser")
    risultati = []

    # Trova tutte le righe pianta
    righe_pianta = soup.find_all("div", class_=lambda c: c and "col-xs-1-4" in c and "col-sm-1-5" in c)

    for riga in righe_pianta:
        # Nome pianta
        nome_tag = riga.find("div", class_="col-auto")
        if not nome_tag:
            continue
        nome = nome_tag.get_text(strip=True)
        if not nome:
            continue

        # Trova il blocco dati adiacente (stesso row-table padre o fratello)
        parent = riga.find_parent("div", class_=lambda c: c and "row-table" in c)
        if not parent:
            # Prova a salire di livello
            parent = riga.find_parent()

        # Cerca tutti i div con classe pollineMedia nello stesso contenitore padre
        dati_container = riga.find_parent()
        if not dati_container:
            continue

        celle = dati_container.find_all("div", class_="pollineMedia")
        if not celle:
            continue

        # Abbina ogni cella al giorno tramite la classe altriDati-<giorno>-<num>
        previsioni = []
        for cella in celle:
            classes = cella.get("class", [])
            giorno_str = None
            numero = None
            for cls in classes:
                for g in GIORNI:
                    if cls.startswith(f"altriDati-{g}-"):
                        giorno_str = g.capitalize()
                        try:
                            numero = int(cls.split("-")[-1])
                        except ValueError:
                            pass
                        break
            livello = cella.get_text(strip=True)
            if giorno_str and livello:
                previsioni.append((numero or 0, giorno_str, livello))

        previsioni.sort(key=lambda x: x[0])

        if previsioni:
            risultati.append((nome, previsioni))

    return risultati

def format_message(dati):
    oggi = datetime.now()
    intestazione = f"🌿 Pollini Milano — {oggi.strftime('%d/%m/%Y')}\n"
    intestazione += "─" * 28 + "\n"

    corpo = ""
    for nome, previsioni in dati:
        corpo += f"\n🌱 {nome}\n"
        for _, giorno, livello in previsioni:
            emoji_livello = get_emoji(livello)
            corpo += f"  {giorno[:3]}: {emoji_livello}\n"

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
