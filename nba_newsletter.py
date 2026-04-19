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
print(f"🔑 BALLDONTLIE_KEY: {'TAK' if BALLDONTLIE_KEY else 'NIE'}")
if BALLDONTLIE_KEY:
    print(f"   (zamaskowany): {BALLDONTLIE_KEY[:4]}...{BALLDONTLIE_KEY[-4:]} | długość: {len(BALLDONTLIE_KEY)}")

print(f"🔑 SENDGRID_KEY: {'TAK' if SENDGRID_KEY else 'NIE'}")
if SENDGRID_KEY:
    print(f"   (zamaskowany): {SENDGRID_KEY[:4]}...{SENDGRID_KEY[-4:]} | długość: {len(SENDGRID_KEY)}")
else:
    print("❌ SendGrid klucz pusty!")

print(f"📧 FROM_EMAIL: {FROM_EMAIL or 'BRAK'}")
print(f"📅 Dzisiaj: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("🔍 === DEBUG END ===\n")

# =======================================================

def get_yesterday():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%
