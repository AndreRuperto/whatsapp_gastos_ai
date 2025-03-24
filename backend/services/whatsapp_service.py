import requests
import os
import logging
from dotenv import load_dotenv

load_dotenv()
WHATSAPP_BOT_URL = os.getenv("WHATSAPP_BOT_URL")
TOKEN = os.getenv("TOKEN")
PHONE_ID = os.getenv("PHONE_ID")

logger = logging.getLogger(__name__)

def enviar_mensagem_whatsapp(telefone, mensagem):
    url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "text",
        "text": {"body": mensagem}
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()