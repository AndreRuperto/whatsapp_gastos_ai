import requests
import json
import datetime

load_dotenv()

API_DISPONIVEIS = os.getenv("API_DISPONIVEIS", "https://economia.awesomeapi.com.br/json/available/uniq")
API_COTACAO = os.getenv("API_COTACAO", "https://economia.awesomeapi.com.br/json/last/")

def verificar_moedas_disponiveis():
    """
    Verifica quais moedas listadas realmente retornam cotações válidas.
    """
    try:
        response = requests.get(API_DISPONIVEIS)
        response.raise_for_status()
        todas_moedas = response.json()

        moedas_funcionando = {}

        for moeda, nome in todas_moedas.items():
            url = f"{API_COTACAO}{moeda}-BRL"
            try:
                cotacao_response = requests.get(url)
                cotacao_response.raise_for_status()
                data = cotacao_response.json()

                if f"{moeda}BRL" in data:
                    moedas_funcionando[moeda] = nome  # Adiciona a moeda com o nome correspondente

            except:
                continue  # Pula moedas que não retornam valores válidos

        return moedas_funcionando

    except Exception as e:
        print(f"❌ Erro ao verificar moedas disponíveis: {e}")
        return {}

def atualizar_json():
    """
    Atualiza o arquivo `moedas.json` com as moedas realmente funcionais.
    """
    funcionando = verificar_moedas_disponiveis()

    data = {
        "ultima_atualizacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "moedas_disponiveis": funcionando
    }

    with open("moedas.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print("✅ Arquivo `moedas.json` atualizado com sucesso!")

if __name__ == "__main__":
    atualizar_json()