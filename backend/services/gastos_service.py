import logging
import psycopg2
import datetime
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")

def salvar_fatura(descricao, valor, categoria, meio_pagamento, parcelas):
    """
    Salva os gastos parcelados na tabela `fatura_cartao` com as informações corretas.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        data_compra = datetime.datetime.now()  # Data da compra
        dia_fechamento = 7  # Defina o dia de fechamento da fatura

        for i in range(parcelas):
            data_fim = (data_compra + datetime.timedelta(days=30 * i)).replace(day=dia_fechamento)

            parcela_texto = f"{i+1}/{parcelas}"  # Exemplo: "1/2", "2/2"

            cursor.execute(
                "INSERT INTO fatura_cartao (descricao, valor, categoria, meio_pagamento, parcela, data_inicio, data_fim) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (descricao, valor / parcelas, categoria, meio_pagamento, parcela_texto, data_compra, data_fim)
            )

        conn.commit()
        cursor.close()
        conn.close()

        print("✅ Fatura salva com sucesso!")

    except Exception as e:
        print(f"❌ Erro ao salvar fatura: {e}")

def salvar_gasto(descricao, valor, categoria, meio_pagamento, parcelas):
    """
    Salva o gasto no banco de dados PostgreSQL.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    for i in range(parcelas):
        data = datetime.datetime.now() + datetime.timedelta(days=30 * i)
        cursor.execute(
            "INSERT INTO gastos (descricao, valor, categoria, meio_pagamento, parcelas, data) VALUES (%s, %s, %s, %s, %s, %s)",
            (descricao, valor / parcelas, categoria, meio_pagamento, parcelas, data)
        )

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

def pagar_fatura():
    """
    Remove todas as compras parceladas que vencem no mês atual.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        primeiro_dia = datetime.date.today().replace(day=1)
        ultimo_dia = primeiro_dia + datetime.timedelta(days=30)

        cursor.execute(
            "DELETE FROM fatura_cartao WHERE data_fim BETWEEN %s AND %s",
            (primeiro_dia, ultimo_dia)
        )

        conn.commit()
        cursor.close()
        conn.close()

        print("✅ Fatura do mês paga! Compras removidas.")

    except Exception as e:
        print(f"❌ Erro ao pagar fatura: {e}")

def registrar_salario(mensagem):
    """
    Registra um novo salário no banco de dados.
    """
    try:
        valor = float(mensagem.split()[-1])
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO salario (valor, data) VALUES (%s, NOW())", (valor,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "💰 Salário registrado com sucesso!"}
    except Exception as e:
        print(f"❌ Erro ao registrar salário: {e}")
        return {"status": "❌ Erro ao registrar salário"}