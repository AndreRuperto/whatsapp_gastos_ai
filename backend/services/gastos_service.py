import logging
import psycopg2
import datetime
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")

def conectar_bd():
    return psycopg2.connect(DATABASE_URL)

def salvar_fatura(descricao, valor, categoria, meio_pagamento, parcelas, schema):
    conn = conectar_bd()
    cursor = conn.cursor()
    data_compra = datetime.now().strftime("%Y-%m-%d")
    datas_fatura = calcular_datas_fatura(data_compra, parcelas)

    for i, data_fim in enumerate(datas_fatura):
        parcela_numero = f"{i+1}/{parcelas}"
        cursor.execute(f'''
            INSERT INTO {schema}.fatura_cartao (descricao, valor, categoria, meio_pagamento, parcela, data_inicio, data_fim)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (descricao, valor/parcelas, categoria, meio_pagamento, parcela_numero, data_compra, data_fim))

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Fatura registrada com datas corrigidas!")

def salvar_gasto(descricao, valor, categoria, meio_pagamento, schema, parcelas=1):
    conn = conectar_bd()
    cursor = conn.cursor()

    if meio_pagamento in ["pix", "débito"]:
        cursor.execute(f'''
            INSERT INTO {schema}.gastos (descricao, valor, categoria, meio_pagamento, parcelas)
            VALUES (%s, %s, %s, %s, %s)
        ''', (descricao, valor, categoria, meio_pagamento, parcelas))
        logger.info(f"✅ Gasto registrado: {descricao} | R$ {valor:.2f} | {categoria} | {meio_pagamento}")

    elif meio_pagamento == "crédito":
        data_inicio = datetime.now()
        for parcela in range(1, parcelas + 1):
            data_fim = (data_inicio + timedelta(days=30 * parcela)).strftime("%Y-%m-%d")
            cursor.execute(f'''
                INSERT INTO {schema}.fatura_cartao (descricao, valor, categoria, meio_pagamento, parcela, data_inicio, data_fim)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (descricao, valor / parcelas, categoria, meio_pagamento, f"{parcela}/{parcelas}", data_inicio, data_fim))
        logger.info(f"✅ Compra parcelada registrada! {parcelas}x de R$ {valor/parcelas:.2f}")

    conn.commit()
    cursor.close()
    conn.close()

def calcular_total_gasto(schema):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT SUM(valor) FROM {schema}.gastos 
        WHERE data >= date_trunc('month', CURRENT_DATE)
    """)
    total = cursor.fetchone()[0] or 0.0
    cursor.close()
    conn.close()
    return total

def pagar_fatura(schema):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(f'''
        SELECT descricao, valor, categoria, meio_pagamento FROM {schema}.fatura_cartao 
        WHERE DATE_PART('month', data_fim) = DATE_PART('month', CURRENT_DATE)
        AND DATE_PART('year', data_fim) = DATE_PART('year', CURRENT_DATE)
    ''')
    registros = cursor.fetchall()
    for descricao, valor, categoria, meio_pagamento in registros:
        cursor.execute(f'''
            INSERT INTO {schema}.gastos (descricao, valor, categoria, meio_pagamento, parcelas)
            VALUES (%s, %s, %s, %s, %s)
        ''', (descricao, valor, categoria, meio_pagamento, 1))
    cursor.execute(f'''
        DELETE FROM {schema}.fatura_cartao 
        WHERE DATE_PART('month', data_fim) = DATE_PART('month', CURRENT_DATE)
    ''')
    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"✅ Fatura paga! Total adicionado aos gastos.")

def registrar_salario(mensagem, schema):
    try:
        valor = float(mensagem.split()[-1].replace(",", "."))
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO {schema}.salario (valor, data) VALUES (%s, NOW())", (valor,))
        conn.commit()
        cursor.close()
        conn.close()
        return f"💰 Salário de R$ {valor:.2f} registrado com sucesso!"
    except Exception as e:
        print(f"❌ Erro ao registrar salário: {e}")
        return "❌ Erro ao registrar salário. Verifique o valor e tente novamente."

def calcular_datas_fatura(data_compra: str, num_parcelas: int):
    datas_pagamento = []
    data_base = datetime.strptime(data_compra, "%Y-%m-%d")
    primeiro_vencimento = (data_base.replace(day=1) + timedelta(days=32)).replace(day=7)
    for parcela in range(num_parcelas):
        datas_pagamento.append(primeiro_vencimento.strftime("%Y-%m-%d"))
        primeiro_vencimento = (primeiro_vencimento.replace(day=1) + timedelta(days=32)).replace(day=6)
    return datas_pagamento

def mensagem_ja_processada(mensagem_id: str) -> bool:
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM mensagens_recebidas WHERE mensagem_id = %s", (mensagem_id,))
    existe = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return existe

def registrar_mensagem_recebida(mensagem_id: str, telefone: str = ""):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO mensagens_recebidas (mensagem_id, telefone) VALUES (%s, %s) ON CONFLICT DO NOTHING", (mensagem_id, telefone))
    conn.commit()
    cursor.close()
    conn.close()

def listar_lembretes(telefone, schema):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(f"SELECT id, mensagem, cron FROM {schema}.lembretes WHERE telefone = %s", (telefone,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [{"id": row[0], "mensagem": row[1], "cron": row[2]} for row in rows]

def apagar_lembrete(telefone, lembrete_id, schema):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {schema}.lembretes WHERE id = %s AND telefone = %s", (lembrete_id, telefone))
    sucesso = cursor.rowcount > 0
    conn.commit()
    cursor.close()
    conn.close()
    return sucesso