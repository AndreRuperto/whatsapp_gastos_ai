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
    url = f"https://graph.facebook.com/v22.0/{media_id}"
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

async def enviar_imagem_whatsapp(telefone, caminho_imagem, caption=None):
    url = f"https://graph.facebook.com/v22.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        # Primeiro precisamos fazer upload da imagem para os servidores do WhatsApp
        upload_url = f"https://graph.facebook.com/v22.0/{PHONE_ID}/media"
        
        with open(caminho_imagem, "rb") as image_file:
            files = {
                'file': (os.path.basename(caminho_imagem), image_file, 'image/png')
            }
            form_data = {
                'messaging_product': 'whatsapp',
                'type': 'image/png'
            }
            
            async with httpx.AsyncClient() as client:
                upload_response = await client.post(
                    upload_url,
                    headers={"Authorization": f"Bearer {TOKEN}"},
                    files=files,
                    data=form_data
                )
                
                if upload_response.status_code != 200:
                    logger.error(f"Erro ao fazer upload da imagem: {upload_response.text}")
                    return False
                
                media_id = upload_response.json().get('id')
                
                if not media_id:
                    logger.error("Não foi possível obter o media_id após upload")
                    return False
                
                # Agora enviamos a mensagem usando o media_id
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": telefone,
                    "type": "image",
                    "image": {
                        "id": media_id,
                        "caption": caption if caption else None
                    }
                }
                
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    logger.error(f"Erro ao enviar imagem: {response.text}")
                    return False
                
                logger.info("✅ Imagem enviada com sucesso para %s", telefone)
                return True
                
    except Exception as e:
        logger.exception(f"❌ Erro ao enviar imagem: {e}")
        # Em caso de falha, tenta enviar uma mensagem de texto informando o erro
        await enviar_mensagem_whatsapp(
            telefone, 
            "❌ Desculpe, não foi possível enviar a imagem do comprovante. Erro técnico."
        )
        return False
        raise e