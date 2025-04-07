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

async def obter_url_midia(media_id: str) -> str:
    url = f"https://graph.facebook.com/v19.0/{media_id}"
    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            media_info = response.json()
            return media_info.get("url")
    except Exception as e:
        logger.exception(f"❌ Erro ao obter URL da mídia com ID {media_id}:")
        return None

async def baixar_midia(url: str, caminho_destino: str):
    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            with open(caminho_destino, "wb") as f:
                f.write(response.content)
        logger.info(f"✅ Mídia salva em {caminho_destino}")
    except Exception as e:
        logger.exception(f"❌ Erro ao baixar a mídia da URL {url}:")