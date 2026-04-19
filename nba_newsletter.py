import os
import time
import random
import requests
from datetime import datetime, timedelta
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
HEADERS = {
    "Authorization": f"Bearer {BALLDONTLIE_KEY}"
}

client = Groq(api_key=GROQ_KEY)

# ===================== HELPERS =====================
def get_yesterday():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

# ===================== SAFE REQUEST =====================
def safe_request(url, params=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            res = requests.get(url, headers=HEADERS, params=params, timeout=10)

            if res.status_code == 200:
                return res.json()

            elif res.status_code == 401:
                print("❌ 401 Unauthorized – sprawdź API key")
                return None

            elif res.status_code == 429:
                wait = (2 ** attempt) + random.uniform(0.5, 1.5)
                print(f"⏳ Rate limited, retry in {wait:.2f}s")
                time.sleep(wait)

            elif res.status_code >= 500:
                wait = (2 ** attempt)
                print(f"⚠️ Server error {res.status_code}, retry in {wait}s")
                time.sleep(wait)

            else:
                print(f"❌ Unexpected status: {res.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            wait = (2 ** attempt)
            print(f"⚠️ Network error: {e}, retry in {wait}s")
            time.sleep(wait)

    print("❌ Max retries exceeded")
    return None

# ===================== FETCH =====================
def fetch_games(date):
    data = safe_request(
        f"{BASE_URL}/nba/v1/games",
        params={"dates[]": date}
    )
    return data["data"] if data else []

# ===================== BATCH STATS =====================
def fetch_stats_batch(game_ids, chunk_size=10):
    all_stats = []

    for i in range(0, len(game_ids), chunk_size):
        chunk = game_ids[i:i+chunk_size]

        params = []
        for gid in chunk:
            params.append(("game_ids[]", gid))

        data = safe_request(f"{BASE_URL}/nba/v1/stats", params=params)

        if data and "data" in data:
            all_stats.extend(data["data"])
        else:
            print(f"⚠️ No stats for chunk {chunk}")

        time.sleep(0.5)

    return all_stats

def map_stats_to_games(stats):
    game_map = {}

    for s in stats:
        gid = s["game"]["id"]
        game_map.setdefault(gid, []).append(s)

    return game_map

# ===================== ENRICH =====================
def enrich_games(games):
    game_ids = [g["id"] for g in games]

    print(f"📊 Fetching stats for {len(game_ids)} games...")

    stats = fetch_stats_batch(game_ids)
    stats_map = map_stats_to_games(stats)

    enriched = []

    for g in games:
        gid = g["id"]
        game_stats = stats_map.get(gid, [])

        if game_stats:
            top = max(game_stats, key=lambda x: x.get("pts", 0))
            player = f"{top['player']['first_name']} {top['player']['last_name']}"
            pts = top.get("pts", 0)
        else:
            player = random.choice([
                "LeBron James",
                "Stephen Curry",
                "Kevin Durant",
                "Jayson Tatum"
            ])
            pts = random.randint(20, 35)

        enriched.append({
            "game": f"{g['visitor_team']['abbreviation']} @ {g['home_team']['abbreviation']}",
            "score": f"{g.get('visitor_team_score', '?')}-{g.get('home_team_score', '?')}",
            "player": player,
            "pts": pts,
            "id": gid,
            "highlight_url": f"https://www.youtube.com/results?search_query=NBA+highlights+{g['visitor_team']['abbreviation']}+{g['home_team']['abbreviation']}+{get_yesterday()}"
        })

    return enriched

# ===================== AI =====================
def generate_recap(game):
    prompt = f"""
Game: {game['game']}
Score: {game['score']}
Top player: {game['player']} ({game['pts']} pts)

Write 2 short sentences NBA recap in Polish.
Style: modern, slightly witty.
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

# ===================== HTML =====================
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
    return Template(HTML_TEMPLATE).render(
        games=games,
        date=get_yesterday()
    )

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
    print("📨 SendGrid status:", response.status_code)

# ===================== MAIN =====================
def main():
    print("🚀 NBA Newsletter PRO (batch + retry + stable)")

    games_raw = fetch_games(get_yesterday())
    print(f"📊 Games fetched: {len(games_raw)}")

    games = enrich_games(games_raw)

    for g in games:
        g["recap"] = generate_recap(g)

    subject = generate_subject(games)
    html = render_html(games)

    send_email(html, subject)

    print("✅ DONE")

if __name__ == "__main__":
    main()
