from fastapi import FastAPI, Request
import os
import psycopg2
from psycopg2 import sql
from twilio.rest import Client
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

app = FastAPI()

# Configurar credenciais do Twilio a partir do arquivo .env
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Configurar conexão com PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS gastos (
        id SERIAL PRIMARY KEY,
        descricao TEXT,
        valor REAL,
        categoria TEXT,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()
cursor.close()
conn.close()

@app.post("/webhook")
async def receber_mensagem(request: Request):
    data = await request.form()
    mensagem = data.get("Body", "").strip()
    telefone = data.get("From", "")
    
    if mensagem.lower() == "total gasto no mês?":
        return calcular_total_gasto()
    
    descricao, valor, categoria = processar_mensagem(mensagem)
    salvar_gasto(descricao, valor, categoria)
    enviar_mensagem_whatsapp(telefone, f"Gasto de R${valor:.2f} em '{categoria}' registrado com sucesso!")
    return {"status": "OK"}


def processar_mensagem(mensagem: str):
    try:
        partes = mensagem.split()
        valor = float(partes[-1])
        descricao = " ".join(partes[:-1])
        categoria = definir_categoria(descricao)
        return descricao, valor, categoria
    except Exception:
        return "Erro", 0.0, "Desconhecido"


def definir_categoria(descricao: str):
    categorias = {
        "almoço": "Alimentação",
        "jantar": "Alimentação",
        "uber": "Transporte",
        "ônibus": "Transporte",
        "mercado": "Supermercado"
    }
    for chave, categoria in categorias.items():
        if chave in descricao.lower():
            return categoria
    return "Outros"


def salvar_gasto(descricao, valor, categoria):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO gastos (descricao, valor, categoria) VALUES (%s, %s, %s)", 
                   (descricao, valor, categoria))
    conn.commit()
    cursor.close()
    conn.close()


def calcular_total_gasto():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(valor) FROM gastos WHERE data >= date_trunc('month', CURRENT_DATE)")
    total = cursor.fetchone()[0] or 0.0
    cursor.close()
    conn.close()
    return {"total_gasto": total}


def enviar_mensagem_whatsapp(telefone, mensagem):
    client.messages.create(
        from_=TWILIO_WHATSAPP_NUMBER,
        body=mensagem,
        to=telefone
    )