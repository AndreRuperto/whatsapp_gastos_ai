import psycopg2
import logging
from dotenv import load_dotenv
import os

load_dotenv()
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")

def inicializar_bd(DATABASE_URL):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
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
        descricao TEXT,
        valor REAL,
        categoria TEXT,
        meio_pagamento TEXT,
        parcela TEXT,
        data_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_fim DATE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lembretes (
            id SERIAL PRIMARY KEY,
            telefone TEXT,
            mensagem TEXT,
            cron TEXT,
            data_inclusao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensagens_recebidas (
            id SERIAL PRIMARY KEY,
            mensagem_id TEXT UNIQUE,
            telefone TEXT,
            data_recebida TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome TEXT,
            telefone TEXT UNIQUE,
            autorizado BOOLEAN DEFAULT false,
            data_inclusao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()