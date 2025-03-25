import logging
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
WHATSAPP_BOT_URL = os.getenv("WHATSAPP_BOT_URL")
TOKEN = os.getenv("TOKEN")
PHONE_ID = os.getenv("PHONE_ID")

logger = logging.getLogger(__name__)

async def enviar_mensagem_whatsapp(telefone, mensagem):
    url = f"https://graph.facebook.com/v22.0/{PHONE_ID}/messages"
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

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info("✅ Mensagem enviada com sucesso para %s", telefone)
    except httpx.HTTPStatusError as exc:
        logger.error("❌ Erro ao enviar mensagem: %s", exc.response.text)
    except Exception as e:
        logger.exception("❌ Erro inesperado ao enviar mensagem:")