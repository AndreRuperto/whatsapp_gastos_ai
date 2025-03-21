import logging
import requests
import json
import os

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Diretório do script atual
MOEDAS_FILE = os.path.join(BASE_DIR, "..", "data", "moedas.json")

with open(MOEDAS_FILE, "r", encoding="utf-8") as file:
    dados_moedas = json.load(file)


MOEDAS = dados_moedas.get("moedas_disponiveis", {})
MOEDA_EMOJIS = {
    "USD": "🇺🇸",
    "EUR": "🇺🇳",
    "GBP": "🏴",
    "BTC": "🪙",
    "ETH": "💎"
}

def obter_cotacao_principais(API_COTACAO, MOEDA_EMOJIS):
    moedas = ["USD", "EUR", "GBP", "BTC", "ETH"]
    url = f"{API_COTACAO}" + ",".join([f"{m}-BRL" for m in moedas])
    logger.info("📡 Buscando cotações na URL: %s", url)

    try:
        response = requests.get(url)
        data = response.json()
        logger.info("📊 Dados recebidos: %s", data)

        cotacoes = []
        for moeda in moedas:
            key = f"{moeda}BRL"
            if key in data:
                valor = float(data[key]['bid'])
                emoji = MOEDA_EMOJIS.get(moeda, "💰")
                valor_formatado = f"R$ {valor:,.2f}"
                cotacoes.append(f"{emoji} {moeda}: {valor_formatado}")

        if not cotacoes:
            return "⚠️ Nenhuma cotação encontrada. Verifique a API."
        return "📈 Cotações principais:\n\n" + "\n".join(cotacoes)
    except Exception as e:
        logger.exception("❌ Erro ao buscar cotações:")
        return f"❌ Erro ao buscar cotações: {str(e)}"

def obter_cotacao(API_COTACAO, moeda, MOEDAS):
    moeda = moeda.upper()
    nome_moeda = MOEDAS.get(moeda, "Moeda não encontrada")

    try:
        response = requests.get(f"{API_COTACAO}{moeda}-BRL")
        data = response.json()
        key = f"{moeda}BRL"
        if key in data:
            valor = float(data[key]['bid'])
            return f"💰 {nome_moeda} ({moeda}/BRL): R${valor:.2f}"
        else:
            return "⚠️ Moeda não encontrada. Use códigos como USD, EUR, BTC..."
    except Exception as e:
        logger.exception("❌ Erro ao buscar cotação:")
        return f"❌ Erro ao buscar cotação: {str(e)}"