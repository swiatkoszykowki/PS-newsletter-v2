import os
import requests
from datetime import datetime, timedelta
from groq import Groq
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, To
from dotenv import load_dotenv

load_dotenv()

# ===================== KONFIGURACJA + DEBUG =====================
BALLDONTLIE_KEY = os.getenv("BALLDONTLIE_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")
RECIPIENTS = [r.strip() for r in os.getenv("RECIPIENTS", "").split(",") if r.strip()]

SENDGRID_TEMPLATE_ID = os.getenv("SENDGRID_TEMPLATE_ID")
BRAND_LOGO_URL = os.getenv("BRAND_LOGO_URL", "https://via.placeholder.com/600x120/111827/ffffff?text=TWOJE+LOGO")

BASE_URL = "https://api.balldontlie.io"
HEADERS = {"Authorization": BALLDONTLIE_KEY}

print("🔍 === DEBUG START ===")
print(f"🔑 BALLDONTLIE_KEY wczytany: {'TAK' if BALLDONTLIE_KEY else 'NIE'}")
if BALLDONTLIE_KEY:
    masked = BALLDONTLIE_KEY[:4] + "..." + BALLDONTLIE_KEY[-4:]
    print(f"🔑 Klucz (zamaskowany): {masked} | Długość: {len(BALLDONTLIE_KEY)}")
else:
    print("❌ Klucz jest pusty! Sprawdź secrets na GitHub.")
print(f"📅 Dzisiaj: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("🔍 === DEBUG END ===\n")

# =======================================================

def get_yesterday():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

# ==================== DARMOWE DANE + DEBUG ====================
def fetch_yesterday_games():
    date = get_yesterday()
    print(f"🔍 DEBUG: Pobieram mecze z wczoraj → data: {date}")
    
    response = requests.get(
        f"{BASE_URL}/nba/v1/games",
        headers=HEADERS,
        params={"dates[]": date}
    )
    
    print(f"🔍 DEBUG: Status odpowiedzi: {response.status_code}")
    if response.status_code != 200:
        print(f"❌ DEBUG: Treść błędu: {response.text[:500]}")
    
    response.raise_for_status()
    data = response.json()["data"]
    print(f"✅ DEBUG: Pobrano {len(data)} meczów z wczoraj")
    return data

def fetch_today_games():
    date = get_today()
    print(f"🔍 DEBUG: Pobieram mecze na dziś → data: {date}")
    
    response = requests.get(
        f"{BASE_URL}/nba/v1/games",
        headers=HEADERS,
        params={"dates[]": date}
    )
    
    print(f"🔍 DEBUG: Status odpowiedzi (dzisiaj): {response.status_code}")
    if response.status_code != 200:
        print(f"❌ DEBUG: Treść błędu (dzisiaj): {response.text[:500]}")
    
    response.raise_for_status()
    data = response.json()["data"]
    print(f"✅ DEBUG: Pobrano {len(data)} meczów na dziś")
    return data

# ==================== GENEROWANIE NEWSLETTERA ====================
def generate_newsletter(games_yest, games_today):
    client = Groq(api_key=GROQ_KEY)
    
    games_str = "\n".join([
        f"{g['visitor_team']['abbreviation']} @ {g['home_team']['abbreviation']} → {g.get('visitor_team_score', '?')}-{g.get('home_team_score', '?')} (ID: {g['id']})"
        for g in games_yest
    ]) or "Brak meczów wczoraj."

    today_str = "\n".join([
        f"{g['visitor_team']['abbreviation']} @ {g['home_team']['abbreviation']} ({g['status']})"
        for g in games_today
    ]) or "Brak meczów dzisiaj."

    # <<< POPRAWIONY PROMPT – zamknięty poprawnie >>>
    prompt = f"""Jesteś najlepszym polskim copywriterem NBA. Napisz **atrakcyjny, memiczny newsletter** po polsku.

Dane:
Mecze z wczoraj:
{games_str}

Mecze na dziś:
{today_str}

Zasady (bardzo ważne):
- Całość jako gotowy, piękny HTML od <!DOCTYPE html> do </html>
- Na samej górze wstaw logo marki: <img src="{BRAND_LOGO_URL}" style="max-width:600px; width:100%; height:auto; display:block; margin:0 auto 20px;">
- Użyj responsywnego designu + dark mode
- Dla każdego meczu z wczoraj dodaj link do box score i highlights
- Sekcja "🔥 Najlepsze highlights wczoraj"
- Emotikony, luźny styl

Na początku dokładnie: [TYTUŁ: Tutaj tytuł maila]"""

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
        message.template_id = SENDGRID_TEMPLATE_ID
        message.dynamic_template_data = {"subject": subject, "html_content": html_content}
    else:
        message.html_content = html_content

    for email in RECIPIENTS:
        message.add_to(To(email))

    response = sg.send(message)
    print(f"✅ Newsletter wysłany! Status: {response.status_code}")

# ==================== MAIN ====================
def main():
    print("🚀 Start generowania NBA Newsletter LITE... (z debugiem)")
    
    games_yest = fetch_yesterday_games()
    games_today = fetch_today_games()
    
    print(f"✅ Znaleziono {len(games_yest)} meczów z wczoraj i {len(games_today)} na dziś.")
    
    newsletter_raw = generate_newsletter(games_yest, games_today)
    
    if "[TYTUŁ:" in newsletter_raw:
        title = newsletter_raw.split("[TYTUŁ:")[1].split("]")[0].strip()
        html = newsletter_raw.split("]", 1)[1].strip()
    else:
        title = f"NBA Daily • {get_yesterday()}"
        html = newsletter_raw

    send_email(html, title)
    print("🎉 Gotowe! Newsletter leci.")

if __name__ == "__main__":
    main()
