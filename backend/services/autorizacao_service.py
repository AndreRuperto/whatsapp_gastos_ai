import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def verificar_autorizacao(telefone: str) -> bool:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT autorizado FROM usuarios WHERE telefone = %s", (telefone,)
    )
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    return resultado is not None and resultado[0] is True

def liberar_usuario(telefone, nome):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # 1. Inserir na tabela usuarios
    cursor.execute("""
        INSERT INTO usuarios (telefone, autorizado, nome)
        VALUES (%s, true, %s)
        ON CONFLICT (telefone) DO UPDATE SET autorizado = true, nome = EXCLUDED.nome
    """, (telefone, nome))

    # 2. Criar schema com base no nome (transforma em minúsculo e remove espaços)
    schema = nome.lower().replace(" ", "_")
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    # 3. Criar tabelas dentro do schema
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.gastos (
            id SERIAL PRIMARY KEY,
            descricao TEXT,
            valor REAL,
            categoria TEXT,
            meio_pagamento TEXT,
            parcelas INT DEFAULT 1,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.fatura_cartao (
            id SERIAL PRIMARY KEY,
            descricao TEXT,
            valor REAL,
            categoria TEXT,
            meio_pagamento TEXT,
            parcela TEXT,
            data_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_fim DATE
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.lembretes (
            id SERIAL PRIMARY KEY,
            telefone TEXT,
            mensagem TEXT,
            cron TEXT
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.salario (
            id SERIAL PRIMARY KEY,
            valor REAL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()