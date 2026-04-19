import os
import requests
from datetime import datetime, timedelta
from functools import lru_cache
from dotenv import load_dotenv
from jinja2 import Template
from groq import Groq
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, To

load_dotenv()

# ===================== CONFIG =====================
BALLDONTLIE_KEY = os.getenv("BALLDONTLIE_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")
RECIPIENTS = [r.strip() for r in os.getenv("RECIPIENTS", "").split(",") if r.strip()]

BASE_URL = "https://api.balldontlie.io"
HEADERS = {"Authorization": BALLDONTLIE_KEY}

client = Groq(api_key=GROQ_KEY)

# ===================== HELPERS =====================
def get_yesterday():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

# ===================== FETCH =====================
def fetch_games(date):
    res = requests.get(
        f"{BASE_URL}/nba/v1/games",
        headers=HEADERS,
        params={"dates[]": date}
    )
    res.raise_for_status()
    return res.json()["data"]

@lru_cache(maxsize=500)
def fetch_stats(game_id):
    res = requests.get(
        f"{BASE_URL}/nba/v1/stats",
        headers=HEADERS,
        params={"game_ids[]": game_id}
    )
    res.raise_for_status()
    return res.json()["data"]

# ===================== ENRICH =====================
def enrich_games(games):
    enriched = []

    for g in games:
        stats = fetch_stats(g["id"])

        if stats:
            top = max(stats, key=lambda x: x["pts"])
            player = f"{top['player']['first_name']} {top['player']['last_name']}"
            pts = top["pts"]
        else:
            player = "Brak danych"
            pts = "?"

        enriched.append({
            "game": f"{g['visitor_team']['abbreviation']} @ {g['home_team']['abbreviation']}",
            "score": f"{g.get('visitor_team_score', '?')}-{g.get('home_team_score', '?')}",
            "player": player,
            "pts": pts,
            "id": g["id"],
            "highlight_url": f"https://www.youtube.com/results?search_query=NBA+highlights+{g['visitor_team']['abbreviation']}+{g['home_team']['abbreviation']}+{get_yesterday()}"
        })

    return enriched

# ===================== AI =====================
def generate_recap(game):
    prompt = f"""
Game: {game['game']}
Score: {game['score']}
Top player: {game['player']} ({game['pts']} pts)

Write 2 short sentences NBA recap.
Style: modern, slightly witty, Polish.
"""

    chat = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=120
    )

    return chat.choices[0].message.content.strip()

def generate_subject(games):
    prompt = f"""
Create catchy Polish NBA newsletter subject line.

Games:
{", ".join([g["game"] for g in games])}

Max 10 words. Include emoji.
"""

    chat = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=60
    )

    return chat.choices[0].message.content.strip()

# ===================== TEMPLATE =====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#0f172a;font-family:Arial;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
<td align="center">
<table width="600" style="background:#111827;color:#ffffff;padding:20px;">

<tr>
<td align="center">
<h1 style="margin:0;">NBA Daily</h1>
<p style="color:#9ca3af;">{{ date }}</p>
</td>
</tr>

{% for g in games %}
<tr>
<td style="padding:16px 0;border-bottom:1px solid #374151;">
<h2 style="margin:0;">{{ g.game }} ({{ g.score }})</h2>
<p style="margin:8px 0;">{{ g.recap }}</p>
<p style="color:#fbbf24;">🔥 {{ g.player }} – {{ g.pts }} pts</p>
<a href="{{ g.highlight_url }}" style="color:#60a5fa;">▶ Highlights</a>
</td>
</tr>
{% endfor %}

<tr>
<td style="padding-top:20px;text-align:center;color:#6b7280;">
<p>Generated with AI ⚡</p>
</td>
</tr>

</table>
</td>
</tr>
</table>
</body>
</html>
"""

def render_html(games):
    template = Template(HTML_TEMPLATE)
    return template.render(games=games, date=get_yesterday())

# ===================== SEND =====================
def send_email(html, subject):
    sg = SendGridAPIClient(SENDGRID_KEY)

    message = Mail(
        from_email=FROM_EMAIL,
        subject=subject,
        html_content=html
    )

    for r in RECIPIENTS:
        message.add_to(To(r))

    response = sg.send(message)
    print("SendGrid status:", response.status_code)

# ===================== MAIN =====================
def main():
    print("🚀 NBA Newsletter PRO")

    games_raw = fetch_games(get_yesterday())
    games = enrich_games(games_raw)

    print(f"📊 Games: {len(games)}")

    # AI recaps
    for g in games:
        g["recap"] = generate_recap(g)

    subject = generate_subject(games)
    html = render_html(games)

    send_email(html, subject)

    print("✅ DONE")

if __name__ == "__main__":
    main()
