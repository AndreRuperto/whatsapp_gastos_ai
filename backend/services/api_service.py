import logging
import requests
import json
import os

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Diretório do script atual
MOEDAS_FILE = os.path.join(BASE_DIR, "..", "data", "moedas.json")
CONVERSOES_FILE = os.path.join(BASE_DIR, "..", "data", "conversoes.json")

with open(MOEDAS_FILE, "r", encoding="utf-8") as file:
    dados_moedas = json.load(file)

with open(CONVERSOES_FILE, "r", encoding="utf-8") as file:
    dados_conversoes = json.load(file)

API_COTACAO = os.getenv("API_COTACAO")
API_CEP = os.getenv("API_CEP")
CONVERSOES = dados_conversoes.get("conversoes_disponiveis", {})
MOEDAS = dados_moedas.get("todas_moedas", {})
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

def obter_cotacao(API_COTACAO, MOEDAS, CONVERSOES, moeda_origem, moeda_destino='BRL'):
    moeda_origem = moeda_origem.upper()
    moeda_destino = moeda_destino.upper()

    nome_origem = MOEDAS.get(moeda_origem, moeda_origem)
    nome_destino = MOEDAS.get(moeda_destino, moeda_destino)

    # 💡 Verifica se é uma conversão entre a mesma moeda
    if moeda_origem == moeda_destino:
        return "🤔 Você realmente quer converter uma moeda para ela mesma? Isso é um loop infinito financeiro! 🔁💸? 😂"

    # ❌ Verifica se a conversão é permitida
    if moeda_destino not in CONVERSOES.get(moeda_origem, []):
        return (
            f"🚫 Conversão não disponível entre {moeda_origem} e {moeda_destino}.\n"
            f"Consulte as conversões válidas ou tente outra moeda. 😉"
        )

    # ✅ Consulta a cotação na API
    try:
        response = requests.get(f"{API_COTACAO}{moeda_origem}-{moeda_destino}")
        response.raise_for_status()
        data = response.json()
        key = f"{moeda_origem}{moeda_destino}"

        if key in data:
            valor = float(data[key]['bid'])
            return (
                f"💱 Conversão: {nome_origem} → {nome_destino}\n"
                f"💰 1 {moeda_origem} = {valor:.4f} {moeda_destino}"
            )
        else:
            return "⚠️ Conversão não encontrada na API. Verifique os códigos usados."
    except Exception as e:
        logger.exception("❌ Erro ao buscar cotação:")
        return f"❌ Erro ao buscar cotação: {str(e)}"

def listar_moedas_disponiveis(MOEDAS):
    lista = ["🪙 Moedas disponíveis:"]

    for codigo, nome in sorted(MOEDAS.items()):
        lista.append(f"• {codigo}: {nome}")

    return "\n".join(lista)

def listar_conversoes_disponiveis(CONVERSOES):
    lista = [f"💱 Conversões disponíveis:"]

    for origem, destinos in sorted(CONVERSOES.items()):
        destinos_str = ", ".join(sorted(destinos))
        lista.append(f"• {origem} → {destinos_str}")

    return "\n".join(lista)

def listar_conversoes_disponiveis_moeda(CONVERSOES, origem):
    moeda = origem.upper()
    lista = [f"💱 Conversões disponíveis pra {moeda}:"]
    destinos = sorted(CONVERSOES[moeda])
    destinos_str = ", ".join(destinos)
    lista.append(f"• {moeda} → {destinos_str}")
    return "\n".join(lista)

def buscar_cep(cep: str):
    try:
        response = requests.get(f"{API_CEP}{cep}")
        
        if response.status_code == 200:
            dados = response.json()
            return (
                f"📍 Endereço encontrado:\n"
                f"• CEP: {dados.get('cep')}\n"
                f"• Logradouro: {dados.get('address')}\n"
                f"• Bairro: {dados.get('district')}\n"
                f"• Cidade: {dados.get('city')} - {dados.get('state')}\n"
                f"• DDD: {dados.get('ddd')}"
            )
        
        elif response.status_code == 400:
            return "❌ CEP inválido. Verifique se digitou corretamente (apenas números)."
        
        elif response.status_code == 404:
            return "🔍 CEP não encontrado. Tente outro valor."

        else:
            return f"⚠️ Erro inesperado (status {response.status_code}). Tente novamente mais tarde."

    except requests.RequestException as e:
        return f"❌ Erro ao buscar o CEP: {str(e)}"