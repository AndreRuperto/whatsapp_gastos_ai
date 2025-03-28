import requests
import json
import datetime
import os
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

API_MOEDAS_DISPONIVEIS = os.getenv("API_MOEDAS_DISPONIVEIS")
API_COTACAO= os.getenv("API_COTACAO")
API_CONVERSOES_DISPONIVEIS = os.getenv("API_CONVERSOES_DISPONIVEIS")

def verificar_moedas_disponiveis():
    """
    Verifica quais moedas listadas realmente retornam cotações válidas.
    """
    try:
        response = requests.get(API_MOEDAS_DISPONIVEIS)
        response.raise_for_status()
        todas_moedas = response.json()

        data = {
            "ultima_atualizacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "todas_moedas": todas_moedas
        }

        with open("data/moedas.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print("✅ Arquivo `moedas.json` atualizado com sucesso!")

    except Exception as e:
        print(f"❌ Erro ao verificar moedas disponíveis: {e}")
        return {}

def verificar_conversoes_disponiveis():
    try:
        response = requests.get(API_CONVERSOES_DISPONIVEIS)
        response.raise_for_status()
        dados = response.json()

        # Reorganiza os dados no formato: { "USD": ["BRL", ...], ... }
        conversoes = defaultdict(list)
        for par, descricao in dados.items():
            if "-" in par:
                origem, destino = par.split("-")
                conversoes[origem].append(destino)

        # Monta estrutura final
        estrutura_final = {
            "ultima_atualizacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "conversoes_disponiveis": dict(conversoes)
        }

        # Cria pasta se necessário e salva o arquivo
        caminho = "data/conversoes.json"
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(estrutura_final, f, indent=4, ensure_ascii=False)

        print("✅ Arquivo 'conversoes.json' gerado com sucesso!")

    except Exception as e:
        print(f"❌ Erro ao gerar conversoes.json: {e}")


if __name__ == "__main__":
    verificar_moedas_disponiveis()
    verificar_conversoes_disponiveis()