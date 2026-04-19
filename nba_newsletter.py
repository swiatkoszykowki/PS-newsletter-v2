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
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")
RECIPIENTS = [r.strip() for r in os.getenv("RECIPIENTS", "").split(",") if r.strip()]

# NOWOŚĆ: ID szablonu Sendgrid (opcjonalne)
SENDGRID_TEMPLATE_ID = os.getenv("SENDGRID_TEMPLATE_ID")  # zostaw puste jeśli chcesz prosty HTML

BASE_URL = "https://api.balldontlie.io"
HEADERS = {"Authorization": BALLDONTLIE_KEY}

SEASON = 2026  # ← aktualny sezon w kwietniu 2026
# =======================================================

def get_yesterday():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

# ==================== POBIERANIE DANYCH ====================
def fetch_yesterday_games():
    date = get_yesterday()
    response = requests.get(
        f"{BASE_URL}/nba/v1/games",
        headers=HEADERS,
        params={"dates[]": date}
    )
    response.raise_for_status()
    return response.json()["data"]

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
    return sorted(stats, key=lambda x: x.get("pts", 0), reverse=True)[:12]

def fetch_standings():
    response = requests.get(
        f"{BASE_URL}/nba/v1/standings",
        headers=HEADERS,
        params={"season": SEASON}
    )
    response.raise_for_status()
    return response.json()["data"]

def fetch_today_games():
    date = get_today()
    response = requests.get(
        f"{BASE_URL}/nba/v1/games",
        headers=HEADERS,
        params={"dates[]": date}
    )
    response.raise_for_status()
    return response.json()["data"]

# ==================== GENEROWANIE NEWSLETTERA ====================
def generate_newsletter(games_yest, top_players, standings, games_today):
    client = Groq(api_key=GROQ_KEY)
    
    games_str = "\n".join([
        f"{g['visitor_team']['abbreviation']} @ {g['home_team']['abbreviation']} → {g.get('visitor_team_score', '?')}-{g.get('home_team_score', '?')} ({g['status']})"
        for g in games_yest
    ]) or "Brak meczów wczoraj."

    top_str = "\n".join([
        f"{p['player']['first_name']} {p['player']['last_name']} ({p['team']['abbreviation']}): {p.get('pts',0)}pkt {p.get('reb',0)}zb {p.get('ast',0)}ast"
        for p in top_players[:8]
    ])

    east = [s for s in standings if s.get("conference") == "East"][:6]
    west = [s for s in standings if s.get("conference") == "West"][:6]

    today_str = "\n".join([
        f"{g['visitor_team']['abbreviation']} @ {g['home_team']['abbreviation']} ({g['status']})"
        for g in games_today
    ]) or "Brak meczów dzisiaj."

    prompt = f"""Jesteś najlepszym polskim copywriterem NBA. Napisz **bardzo atrakcyjny newsletter** po polsku na podstawie tych danych.

Mecze z wczoraj:
{games_str}

Najlepsi gracze wczoraj:
{top_str}

Tabela (tylko top 6 East + West):
East: {", ".join([f"{t['team']['abbreviation']} ({t.get('wins',0)}-{t.get('losses',0)})" for t in east])}
West: {", ".join([f"{t['team']['abbreviation']} ({t.get('wins',0)}-{t.get('losses',0)})" for t in west])}

Mecze na dziś:
{today_str}

Zasady:
- Całość ma być gotowym, pięknym HTML-em (od <!DOCTYPE html> do </html>)
- Użyj nowoczesnego, responsywnego designu (mobile-first)
- Dodaj **dark mode** – użyj @media (prefers-color-scheme: dark) + CSS variables
- Dodaj sekcję "🔥 Co kręci się na X" – realistyczne hot takes, memy, cytaty (jakbyś czytał @NBA, @wojespn, polskich fanów)
- Emotikony, pogrubienia, krótkie akapity, call-to-action na końcu
- Na początku daj dokładnie: [TYTUŁ: Tutaj tytuł maila]

Styl: luźny, emocjonalny, trochę memiczny – jak polski podcast NBA o poranku."""

    chat = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        max_tokens=4000
    )
    
    return chat.choices[0].message.content

# ==================== WYSYŁKA ====================
def send_email(html_content, subject):
    sg = SendGridAPIClient(SENDGRID_KEY)
    message = Mail(from_email=FROM_EMAIL, subject=subject)

    if SENDGRID_TEMPLATE_ID:
        # Wersja z szablonem Sendgrid (najładniejsza)
        message.template_id = SENDGRID_TEMPLATE_ID
        message.dynamic_template_data = {
            "subject": subject,
            "html_content": html_content
        }
    else:
        # Wersja fallback (prosty HTML)
        message.html_content = html_content

    for email in RECIPIENTS:
        message.add_to(To(email))

    response = sg.send(message)
    print(f"✅ Newsletter wysłany! Status: {response.status_code} | Szablon: {'TAK' if SENDGRID_TEMPLATE_ID else 'NIE'}")

# ==================== MAIN ====================
def main():
    print("🚀 Start generowania NBA Newsletter...")
    
    games_yest = fetch_yesterday_games()
    game_ids = [g["id"] for g in games_yest if g.get("status") == "Final"]
    
    top_players = fetch_top_performers(game_ids)
    standings = fetch_standings()
    games_today = fetch_today_games()
    
    newsletter_raw = generate_newsletter(games_yest, top_players, standings, games_today)
    
    # Wyciągamy tytuł i HTML
    if "[TYTUŁ:" in newsletter_raw:
        title = newsletter_raw.split("[TYTUŁ:")[1].split("]")[0].strip()
        html = newsletter_raw.split("]", 1)[1].strip()
    else:
        title = f"NBA Daily • {get_yesterday()}"
        html = newsletter_raw

    send_email(html, title)
    print("🎉 Newsletter gotowy i wysłany!")

if __name__ == "__main__":
    main()
