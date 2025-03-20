import requests
import os
import logging
from dotenv import load_dotenv

load_dotenv()
WHATSAPP_BOT_URL = os.getenv("WHATSAPP_BOT_URL")
logger = logging.getLogger(__name__)

def enviar_mensagem_whatsapp(telefone, mensagem):
    logger.info(f"📨 Enviando mensagem para {telefone}: {mensagem}")

    payload = {"number": telefone, "message": mensagem}
    
    try:
        response = requests.post(WHATSAPP_BOT_URL, json=payload)
        response.raise_for_status()
        return {"status": "Mensagem enviada"}
    except requests.exceptions.RequestException as e:
        logger.exception("❌ Erro ao enviar mensagem via WhatsApp:")
        return {"status": "Erro ao enviar mensagem", "error": str(e)}