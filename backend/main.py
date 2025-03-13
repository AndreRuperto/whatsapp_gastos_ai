from fastapi import FastAPI, Request, Form
import os
import psycopg2
import datetime
import requests  # Importado para fazer chamadas HTTP
from dotenv import load_dotenv
import json

# Carregar variáveis de ambiente
load_dotenv()

app = FastAPI()

# Configuração do Banco de Dados PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Criar tabelas caso não existam
cursor.execute('''
    CREATE TABLE IF NOT EXISTS gastos (
        id SERIAL PRIMARY KEY,
        descricao TEXT,
        valor REAL,
        categoria TEXT,
        meio_pagamento TEXT,
        parcelas INT DEFAULT 1,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS salario (
        id SERIAL PRIMARY KEY,
        valor REAL,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS fatura_cartao (
        id SERIAL PRIMARY KEY,
        valor REAL,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()
cursor.close()
conn.close()

# URL do WhatsApp Bot (Servidor Node.js)
WHATSAPP_BOT_URL = os.getenv("WHATSAPP_BOT_URL", "http://localhost:3000/send")
API_COTACAO = os.getenv("API_COTACAO", "https://economia.awesomeapi.com.br/json/last/")

with open("backend/moedas.json", "r", encoding="utf-8") as file:
    dados_moedas = json.load(file)

# Ajuste para acessar corretamente as moedas disponíveis
MOEDAS = dados_moedas.get("moedas_disponiveis", {})

MOEDA_EMOJIS = {
    "USD": "🇺🇸",  # Dólar Americano (bandeira dos EUA)
    "EUR": "🇺🇳",  # Euro (bandeira da ONU)
    "GBP": "🏴",  # Libra Esterlina (bandeira da Inglaterra)
    "BTC": "🪙",   # Bitcoin (emoji de moeda)
    "ETH": "💎"    # Ethereum (diamante)
}

@app.post("/webhook")
async def receber_mensagem(
    Body: str = Form(...), 
    From: str = Form(...)
):
    """
    Recebe mensagens do WhatsApp e processa conforme necessário.
    """
    mensagem = Body.strip()
    telefone = From.replace("whatsapp:", "").replace("+", "")

    if mensagem.lower() == "total gasto no mês?":
        total = calcular_total_gasto()
        resposta = f"📊 Total gasto no mês: R$ {format(total, ',.2f').replace(',', '.')}"
        enviar_mensagem_whatsapp(telefone, resposta)
        return {"status": "OK", "resposta": resposta}

    if "salario" in mensagem.lower():
        status = registrar_salario(mensagem)
        enviar_mensagem_whatsapp(telefone, status["status"])
        return status

    if "fatura" in mensagem.lower():
        status = registrar_fatura_cartao(mensagem)
        enviar_mensagem_whatsapp(telefone, status["status"])
        return status
    
    if mensagem == "cotação":
        resposta = obter_cotacao_principais()
        enviar_mensagem_whatsapp(telefone, resposta)
        return {"status": "OK", "resposta": resposta}

    if mensagem.startswith("cotação "):
        moeda = mensagem.split(" ")[1].upper()
        resposta = obter_cotacao(moeda)
        enviar_mensagem_whatsapp(telefone, resposta)
        return {"status": "OK", "resposta": resposta}

    descricao, valor, categoria, meio_pagamento, parcelas = processar_mensagem(mensagem)
    salvar_gasto(descricao, valor, categoria, meio_pagamento, parcelas)
    
    resposta = f"✅ Gasto de R$ {format(valor, ',.2f').replace(',', '.')} em '{categoria}' registrado com sucesso!"
    enviar_mensagem_whatsapp(telefone, resposta)

    return {"status": "OK", "resposta": resposta}

def obter_cotacao_principais():
    """
    Obtém as cotações das 5 principais moedas (USD, EUR, GBP, BTC, ETH).
    """
    moedas = ["USD", "EUR", "GBP", "BTC", "ETH"]
    
    # Construção correta da URL da API
    url = f"{API_COTACAO}" + ",".join([f"{m}-BRL" for m in moedas])
    print(f"📡 Buscando cotações na URL: {url}")

    try:
        response = requests.get(url)
        data = response.json()
        print("📊 Dados recebidos:", data)

        cotacoes = []
        for moeda in moedas:
            key = f"{moeda}BRL"
            if key in data:
                valor = float(data[key]['bid'])
                emoji = MOEDA_EMOJIS.get(moeda, "💰")
                valor_formatado = f"R$ {format(valor, ',.2f').replace(',', '.')}"
                cotacoes.append(f"{emoji} {moeda}: {valor_formatado}")
        
        if not cotacoes:
            return "⚠️ Nenhuma cotação encontrada. Verifique a API."
        
        return "📈 Cotações principais:\n\n" + "\n".join(cotacoes)

    except Exception as e:
        print("❌ Erro ao buscar cotações:", str(e))  # Debug
        return f"❌ Erro ao buscar cotações: {str(e)}"

def obter_cotacao(moeda: str):
    """
    Obtém a cotação da moeda informada e retorna o nome da moeda.
    """
    moeda = moeda.upper()
    nome_moeda = MOEDAS.get(moeda, "Moeda não encontrada")
    
    try:
        response = requests.get(f"https://economia.awesomeapi.com.br/json/last/{moeda}-BRL")
        data = response.json()
        key = f"{moeda}BRL"
        
        if key in data:
            valor = float(data[key]['bid'])
            return f"💰 {nome_moeda} ({moeda}/BRL): R${valor:.2f}"
        else:
            return "⚠️ Moeda não encontrada. Use códigos como USD, EUR, BTC..."
    except Exception as e:
        return f"❌ Erro ao buscar cotação: {str(e)}"

def enviar_mensagem_whatsapp(telefone, mensagem):
    """
    Envia uma mensagem via WhatsApp Web.js para o usuário correto.
    """
    payload = {
        "number": telefone.replace("whatsapp:", "").replace("+", ""),  # Número do usuário
        "message": mensagem
    }
    
    try:
        response = requests.post(WHATSAPP_BOT_URL, json=payload)
        response.raise_for_status()
        return {"status": "Mensagem enviada"}
    except requests.exceptions.RequestException as e:
        return {"status": "Erro ao enviar mensagem", "error": str(e)}

def processar_mensagem(mensagem: str):
    """
    Processa a mensagem recebida e tenta extrair os dados de um gasto.
    """
    try:
        partes = mensagem.split()
        meio_pagamento = partes[-2] if partes[-2] in ["pix", "crédito", "débito"] else "Desconhecido"
        valor = float(partes[-1])
        descricao = " ".join(partes[:-2]) if meio_pagamento != "Desconhecido" else " ".join(partes[:-1])
        categoria = definir_categoria(descricao)
        parcelas = 1

        if meio_pagamento == "crédito" and "x" in descricao:
            descricao, parcelas = descricao.rsplit(" ", 1)
            parcelas = int(parcelas.replace("x", ""))

        return descricao, valor, categoria, meio_pagamento, parcelas
    except Exception:
        return "Erro", 0.0, "Desconhecido", "Desconhecido", 1


def definir_categoria(descricao: str):
    categorias = {
        # 🍽️ Alimentação (35 palavras-chave)
        "almoço": "Alimentação",
        "jantar": "Alimentação",
        "café": "Alimentação",
        "lanchonete": "Alimentação",
        "pizza": "Alimentação",
        "hamburguer": "Alimentação",
        "churrasco": "Alimentação",
        "restaurante": "Alimentação",
        "delivery": "Alimentação",
        "sushi": "Alimentação",
        "padaria": "Alimentação",
        "bar": "Alimentação",
        "fast food": "Alimentação",
        "marmita": "Alimentação",
        "doceria": "Alimentação",
        "brigadeiro": "Alimentação",
        "chocolate": "Alimentação",
        "brownie": "Alimentação",
        "festival gastronômico": "Alimentação",
        "rodízio": "Alimentação",
        "buffet": "Alimentação",
        "petiscos": "Alimentação",
        "food truck": "Alimentação",
        "vinho": "Alimentação",
        "cerveja": "Alimentação",
        "bebidas": "Alimentação",
        "feijoada": "Alimentação",
        "coxinha": "Alimentação",
        "esfiha": "Alimentação",
        "pastel": "Alimentação",
        "salgado": "Alimentação",
        "tapioca": "Alimentação",
        "sorvete": "Alimentação",
        "gelato": "Alimentação",
        "milkshake": "Alimentação",
        "cupcake": "Alimentação",

        # 🚗 Transporte (20 palavras-chave)
        "uber": "Transporte",
        "99": "Transporte",
        "ônibus": "Transporte",
        "metrô": "Transporte",
        "trem": "Transporte",
        "gasolina": "Transporte",
        "estacionamento": "Transporte",
        "pedágio": "Transporte",
        "bike": "Transporte",
        "patinete": "Transporte",
        "carro": "Transporte",
        "manutenção carro": "Transporte",
        "reboque": "Transporte",
        "taxi": "Transporte",
        "mototáxi": "Transporte",
        "passagem": "Transporte",
        "aéreo": "Transporte",
        "uber eats": "Transporte",      # Se for entrega, pode recategorizar
        "combustível": "Transporte",
        "lava rápido": "Transporte",

        # 🏠 Moradia (20 palavras-chave)
        "aluguel": "Moradia",
        "condomínio": "Moradia",
        "iptu": "Moradia",
        "seguro residencial": "Moradia",
        "faxina": "Moradia",
        "reforma": "Moradia",
        "móvel": "Moradia",
        "imobiliária": "Moradia",
        "decoração": "Moradia",
        "mudança": "Moradia",
        "pintura": "Moradia",
        "limpeza": "Moradia",
        "síndico": "Moradia",
        "guarita": "Moradia",
        "porteiro": "Moradia",
        "manutenção casa": "Moradia",
        "jardinagem": "Moradia",
        "ar condicionado": "Moradia",
        "gás encanado": "Moradia",
        "portão": "Moradia",

        # 🔌 Contas e Serviços Públicos (15 palavras-chave)
        "luz": "Contas",
        "água": "Contas",
        "internet": "Contas",
        "celular": "Contas",
        "tv a cabo": "Contas",
        "telefonia": "Contas",
        "taxa lixo": "Contas",
        "energia": "Contas",
        "iluminação": "Contas",
        "esgoto": "Contas",
        "contador": "Contas",
        "ipva": "Contas",
        "dpvat": "Contas",
        "licenciamento": "Contas",
        "multas": "Contas",

        # 🛒 Supermercado (15 palavras-chave)
        "mercado": "Supermercado",
        "compras": "Supermercado",
        "hortifruti": "Supermercado",
        "açougue": "Supermercado",
        "feira": "Supermercado",
        "peixaria": "Supermercado",
        "frios": "Supermercado",
        "mercearia": "Supermercado",
        "limpeza": "Supermercado",
        "higiene": "Supermercado",
        "perfumaria": "Supermercado",
        "empório": "Supermercado",
        "hipermercado": "Supermercado",
        "suprimentos": "Supermercado",
        "armazém": "Supermercado",

        # 🎭 Lazer e Entretenimento (15 palavras-chave)
        "cinema": "Lazer",
        "show": "Lazer",
        "teatro": "Lazer",
        "netflix": "Lazer",
        "spotify": "Lazer",
        "prime video": "Lazer",
        "disney+": "Lazer",
        "xbox game pass": "Lazer",
        "playstation plus": "Lazer",
        "steam": "Lazer",
        "livro": "Lazer",
        "parque": "Lazer",
        "passeio": "Lazer",
        "viagem": "Lazer",
        "ingresso": "Lazer",

        # 🏥 Saúde (20 palavras-chave)
        "farmácia": "Saúde",
        "remédio": "Saúde",
        "médico": "Saúde",
        "dentista": "Saúde",
        "hospital": "Saúde",
        "exame": "Saúde",
        "academia": "Saúde",
        "pilates": "Saúde",
        "fisioterapia": "Saúde",
        "nutricionista": "Saúde",
        "psicólogo": "Saúde",
        "massagem": "Saúde",
        "terapia": "Saúde",
        "plano de saúde": "Saúde",
        "suplemento": "Saúde",
        "vacina": "Saúde",
        "óculos": "Saúde",
        "lente de contato": "Saúde",
        "cirurgia": "Saúde",
        "bem-estar": "Saúde",

        # 🎓 Educação (10 palavras-chave)
        "faculdade": "Educação",
        "curso": "Educação",
        "apostila": "Educação",
        "plataforma educacional": "Educação",
        "mentoria": "Educação",
        "workshop": "Educação",
        "palestra": "Educação",
        "treinamento": "Educação",
        "aula particular": "Educação",
        "material escolar": "Educação",

        # 💻 Tecnologia (15 palavras-chave)
        "notebook": "Tecnologia",
        "computador": "Tecnologia",
        "fones de ouvido": "Tecnologia",
        "mouse": "Tecnologia",
        "teclado": "Tecnologia",
        "tablet": "Tecnologia",
        "monitor": "Tecnologia",
        "ssd": "Tecnologia",
        "pendrive": "Tecnologia",
        "cabo usb": "Tecnologia",
        "hd externo": "Tecnologia",
        "streaming": "Tecnologia",
        "smartphone": "Tecnologia",
        "console": "Tecnologia",
        "carregador": "Tecnologia",

        # 👗 Vestuário (15 palavras-chave)
        "roupa": "Vestuário",
        "tênis": "Vestuário",
        "calçado": "Vestuário",
        "camiseta": "Vestuário",
        "calça": "Vestuário",
        "blusa": "Vestuário",
        "moletom": "Vestuário",
        "casaco": "Vestuário",
        "acessórios": "Vestuário",
        "joias": "Vestuário",
        "mala": "Vestuário",
        "bolsa": "Vestuário",
        "meias": "Vestuário",
        "cinto": "Vestuário",
        "biquíni": "Vestuário",

        # 🎁 Presentes (6 palavras-chave)
        "presente": "Presentes",
        "lembrancinha": "Presentes",
        "aniversário": "Presentes",
        "casamento": "Presentes",
        "amigo secreto": "Presentes",
        "mimo": "Presentes",

        # ❤️ Doações (5 palavras-chave)
        "doação": "Doações",
        "vaquinha": "Doações",
        "ong": "Doações",
        "ajuda": "Doações",
        "solidariedade": "Doações",

        # 💰 Finanças (10 palavras-chave)
        "investimento": "Finanças",
        "poupança": "Finanças",
        "cartão de crédito": "Finanças",
        "empréstimo": "Finanças",
        "seguro": "Finanças",
        "juros": "Finanças",
        "financiamento": "Finanças",
        "consórcio": "Finanças",
        "aplicação": "Finanças",
        "corretora": "Finanças",

        # ⚙️ Serviços (15 palavras-chave)
        "barbearia": "Serviços",
        "cabeleireiro": "Serviços",
        "manicure": "Serviços",
        "estética": "Serviços",
        "encanador": "Serviços",
        "eletricista": "Serviços",
        "reparo": "Serviços",
        "fotografia": "Serviços",
        "freelancer": "Serviços",
        "tradução": "Serviços",
        "lavanderia": "Serviços",
        "pet shop": "Serviços",
        "faxineira": "Serviços",
        "costureira": "Serviços",
        "carpintaria": "Serviços",

        # 📦 Assinaturas (10 palavras-chave)
        "revista": "Assinaturas",
        "jornal": "Assinaturas",
        "plano anual": "Assinaturas",
        "mensalidade": "Assinaturas",
        "patreon": "Assinaturas",
        "apoia.se": "Assinaturas",
        "twitch sub": "Assinaturas",
        "club de assinatura": "Assinaturas",
        "newsletter paga": "Assinaturas",
        "finclass": "Assinaturas",

        # 🐱 Pets (10 palavras-chave)
        "ração": "Pets",
        "petisco": "Pets",
        "veterinário": "Pets",
        "vacina pet": "Pets",
        "casinha": "Pets",
        "areia": "Pets",
        "banho e tosa": "Pets",
        "coleira": "Pets",
        "brinquedo pet": "Pets",
        "remédio pet": "Pets",

        # 🛠️ Hobby & DIY (8 palavras-chave)
        "ferramenta": "Hobby/DIY",
        "madeira": "Hobby/DIY",
        "tinta spray": "Hobby/DIY",
        "cola quente": "Hobby/DIY",
        "artesanato": "Hobby/DIY",
        "bordado": "Hobby/DIY",
        "tricot": "Hobby/DIY",
        "crochê": "Hobby/DIY",

        # 🌱 Jardinagem (5 palavras-chave)
        "mudas": "Jardinagem",
        "adubo": "Jardinagem",
        "fertilizante": "Jardinagem",
        "vaso": "Jardinagem",
        "regador": "Jardinagem",
    }

    # Percorre o dicionário e verifica se a palavra-chave está na descrição
    for chave, categoria in categorias.items():
        if chave in descricao.lower():
            return categoria
    return "Outros"

def salvar_gasto(descricao, valor, categoria, meio_pagamento, parcelas):
    """
    Salva o gasto no banco de dados PostgreSQL.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    for i in range(parcelas):
        data = datetime.datetime.now() + datetime.timedelta(days=30 * i)
        cursor.execute("INSERT INTO gastos (descricao, valor, categoria, meio_pagamento, parcelas, data) VALUES (%s, %s, %s, %s, %s, %s)", 
                       (descricao, valor / parcelas, categoria, meio_pagamento, parcelas, data))

    conn.commit()
    cursor.close()
    conn.close()


def calcular_total_gasto():
    """
    Calcula o total gasto no mês atual.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(valor) FROM gastos WHERE data >= date_trunc('month', CURRENT_DATE)")
    total = cursor.fetchone()[0] or 0.0
    cursor.close()
    conn.close()
    return total


def registrar_salario(mensagem):
    """
    Registra um novo salário no banco de dados.
    """
    try:
        valor = float(mensagem.split()[-1])
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO salario (valor) VALUES (%s)", (valor,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "💰 Salário registrado com sucesso!"}
    except:
        return {"status": "❌ Erro ao registrar salário"}


def registrar_fatura_cartao(mensagem):
    """
    Registra o valor da fatura do cartão.
    """
    try:
        valor = float(mensagem.split()[-1])
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO fatura_cartao (valor) VALUES (%s)", (valor,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "💳 Fatura do cartão registrada com sucesso!"}
    except:
        return {"status": "❌ Erro ao registrar fatura"}