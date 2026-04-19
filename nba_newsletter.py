import os
import requests
from datetime import datetime, timedelta
from groq import Groq
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, To
from dotenv import load_dotenv

load_dotenv()

# ===================== KONFIGURACJA =====================
BALLDONTLIE_KEY = os.getenv("BALLDONTLIE_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")          # np. newsletter@twojadomena.pl
RECIPIENTS = os.getenv("RECIPIENTS", "").split(",")    # np. janek@gmail.com,asia@wp.pl

BASE_URL = "https://api.balldontlie.io"
HEADERS = {"Authorization": BALLDONTLIE_KEY}

# Aktualny sezon – w kwietniu 2026 prawdopodobnie 2025 lub 2026 (sprawdź raz w docs)
SEASON = 2025   # ← zmień jeśli trzeba na 2026
# =======================================================

def get_yesterday():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

# 1. Mecze z wczoraj
def fetch_yesterday_games():
    date = get_yesterday()
    response = requests.get(
        f"{BASE_URL}/nba/v1/games",
        headers=HEADERS,
        params={"dates[]": date}
    )
    response.raise_for_status()
    return response.json()["data"]

# 2. Top stats z wczorajszych meczów
def fetch_top_performers(game_ids):
    if not game_ids:
        return []
    response = requests.get(
        f"{BASE_URL}/nba/v1/stats",
        headers=HEADERS,
        params={"game_ids[]": game_ids}
    )
    response.raise_for_status()
    stats = response.json()["data"]
    # Sortujemy po punktach
    return sorted(stats, key=lambda x: x.get("pts", 0), reverse=True)[:15]

# 3. Aktualne standings
def fetch_standings():
    response = requests.get(
        f"{BASE_URL}/nba/v1/standings",
        headers=HEADERS,
        params={"season": SEASON}
    )
    response.raise_for_status()
    return response.json()["data"]

# 4. Mecze na dziś (harmonogram)
def fetch_today_games():
    date = get_today()
    response = requests.get(
        f"{BASE_URL}/nba/v1/games",
        headers=HEADERS,
        params={"dates[]": date}
    )
    response.raise_for_status()
    return response.json()["data"]

# 5. Generowanie newslettera przez Groq
def generate_newsletter(games_yest, top_players, standings, games_today):
    client = Groq(api_key=GROQ_KEY)
    
    # Przygotowujemy dane w czytelnej formie
    games_str = "\n".join([
        f"{g['visitor_team']['abbreviation']} @ {g['home_team']['abbreviation']} → {g['visitor_team_score']}-{g['home_team_score']} ({g['status']})"
        for g in games_yest
    ]) if games_yest else "Brak meczów wczoraj."

    top_str = "\n".join([
        f"{p['player']['first_name']} {p['player']['last_name']} ({p['team']['abbreviation']}): {p.get('pts',0)}pkt, {p.get('reb',0)}zb, {p.get('ast',0)}ast"
        for p in top_players[:8]
    ])

    # standings upraszczamy do top 5 + bottom 5 w każdej konferencji
    east = [s for s in standings if s.get("conference") == "East"]
    west = [s for s in standings if s.get("conference") == "West"]
    
    prompt = f"""Jesteś polskim ekspertem NBA. Napisz **atrakcyjny, luźny newsletter** na podstawie tych danych (po polsku):

Mecze z wczoraj:
{games_str}

Najlepsi zawodnicy wczoraj:
{top_str}

Aktualna tabela (konferencje East/West):
East: {[f"{t['team']['abbreviation']} ({t.get('wins',0)}-{t.get('losses',0)})") for t in east[:5]]}
West: {[f"{t['team']['abbreviation']} ({t.get('wins',0)}-{t.get('losses',0)})") for t in west[:5]]}

Mecze na dziś:
{"\n".join([f"{g['visitor_team']['abbreviation']} @ {g['home_team']['abbreviation']} ({g['status']})" for g in games_today]) if games_today else "Brak meczów dzisiaj."}

Napisz newsletter w stylu:
- Powitanie + klimat dnia
- Najważniejsze wyniki wczoraj (z humorem)
- Top 5-6 performerów
- Krótko o tabeli
- Co dziś gramy
- Zakończenie + call to action (np. "Do jutra!")

Użyj emoji, pogrubień i formatowania HTML (całość ma być gotowym <html> z inline CSS). Tytuł maila też podaj na początku jako [TYTUŁ: ...]"""

    chat = client.chat.completions.create(
        model="llama-3.3-70b-versatile",   # bardzo dobra i szybka
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=3000
    )
    
    return chat.choices[0].message.content

# 6. Wysyłka przez Sendgrid
def send_email(html_content, subject):
    sg = SendGridAPIClient(SENDGRID_KEY)
    
    message = Mail(
        from_email=FROM_EMAIL,
        subject=subject,
        html_content=html_content
    )
    
    for email in RECIPIENTS:
        if email.strip():
            message.add_to(To(email.strip()))
    
    response = sg.send(message)
    print(f"✅ Newsletter wysłany! Status: {response.status_code}")

# ===================== GŁÓWNA FUNKCJA =====================
def main():
    print("🚀 Start generowania newslettera NBA...")
    
    games_yest = fetch_yesterday_games()
    game_ids = [g["id"] for g in games_yest if g["status"] == "Final"]
    
    top_players = fetch_top_performers(game_ids)
    standings = fetch_standings()
    games_today = fetch_today_games()
    
    print(f"Znaleziono {len(games_yest)} meczów z wczoraj i {len(top_players)} statystyk graczy.")
    
    newsletter = generate_newsletter(games_yest, top_players, standings, games_today)
    
    # Groq zwraca [TYTUŁ: ...] + HTML
    if "[TYTUŁ:" in newsletter:
        title = newsletter.split("[TYTUŁ:")[1].split("]")[0].strip()
        html = newsletter.split("]", 1)[1].strip()
    else:
        title = f"NBA Daily – {get_yesterday()}"
        html = newsletter
    
    send_email(html, title)
    print("🎉 Gotowe!")

if __name__ == "__main__":
    main()
