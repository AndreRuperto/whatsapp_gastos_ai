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
    """Estabelece conexão com o banco de dados."""
    return psycopg2.connect(DATABASE_URL)

def salvar_fatura(descricao, valor, categoria, meio_pagamento, parcelas):
    """
    Registra uma compra parcelada na tabela 'fatura_cartao'.
    """
    conn = conectar_bd()
    cursor = conn.cursor()

    data_compra = datetime.now().strftime("%Y-%m-%d")  # Pega a data atual da compra
    datas_fatura = calcular_datas_fatura(data_compra, parcelas)  # Calcula as datas das parcelas

    for i, data_fim in enumerate(datas_fatura):
        parcela_numero = f"{i+1}/{parcelas}"
        cursor.execute('''
            INSERT INTO fatura_cartao (descricao, valor, categoria, meio_pagamento, parcela, data_inicio, data_fim)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (descricao, valor/parcelas, categoria, meio_pagamento, parcela_numero, data_compra, data_fim))

    conn.commit()
    cursor.close()
    conn.close()

    print("✅ Fatura registrada com datas corrigidas!")


def salvar_gasto(descricao, valor, categoria, meio_pagamento, parcelas=1):
    """
    Salva um gasto no banco de dados.
    
    Se for débito ou PIX, insere diretamente na tabela 'gastos'.
    Se for crédito, insere na tabela 'fatura_cartao' e NÃO na tabela 'gastos' até o pagamento da fatura.
    """
    conn = conectar_bd()
    cursor = conn.cursor()

    if meio_pagamento in ["pix", "débito"]:
        # Gasto direto, registra na tabela 'gastos'
        cursor.execute('''
            INSERT INTO gastos (descricao, valor, categoria, meio_pagamento, parcelas)
            VALUES (%s, %s, %s, %s, %s)
        ''', (descricao, valor, categoria, meio_pagamento, parcelas))
        logger.info(f"✅ Gasto registrado: {descricao} | R$ {valor:.2f} | {categoria} | {meio_pagamento}")

    elif meio_pagamento == "crédito":
        # Se for crédito, cria as parcelas na tabela 'fatura_cartao'
        data_inicio = datetime.now()
        for parcela in range(1, parcelas + 1):
            data_fim = (data_inicio + timedelta(days=30 * parcela)).strftime("%Y-%m-%d")  # Ajustando para o próximo mês
            cursor.execute('''
                INSERT INTO fatura_cartao (descricao, valor, categoria, meio_pagamento, parcela, data_inicio, data_fim)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (descricao, valor / parcelas, categoria, meio_pagamento, f"{parcela}/{parcelas}", data_inicio, data_fim))
        
        logger.info(f"✅ Compra parcelada registrada! {parcelas}x de R$ {valor/parcelas:.2f}")

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
    Consolida a fatura do cartão e adiciona o valor total na tabela 'gastos'.
    """
    conn = conectar_bd()
    cursor = conn.cursor()

    # Obtém o total da fatura do mês atual
    cursor.execute('''
        SELECT SUM(valor) FROM fatura_cartao 
        WHERE DATE_PART('month', data_fim) = DATE_PART('month', CURRENT_DATE)
        AND DATE_PART('year', data_fim) = DATE_PART('year', CURRENT_DATE)
    ''')
    
    total_fatura = cursor.fetchone()[0]

    if total_fatura:
        cursor.execute('''
            INSERT INTO gastos (descricao, valor, categoria, meio_pagamento, parcelas)
            VALUES (%s, %s, %s, %s, %s)
        ''', ("Fatura do Cartão", total_fatura, "Cartão de Crédito", "crédito", 1))

        # Remove os registros da fatura após o pagamento
        cursor.execute('''
            DELETE FROM fatura_cartao WHERE DATE_PART('month', data_fim) = DATE_PART('month', CURRENT_DATE)''')
        
        logger.info(f"✅ Fatura paga! Total adicionado aos gastos: R$ {total_fatura:.2f}")

    conn.commit()
    cursor.close()
    conn.close()

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

def calcular_datas_fatura(data_compra: str, num_parcelas: int):
    """
    Calcula as datas de vencimento das parcelas do cartão de crédito.

    - O vencimento da primeira parcela será sempre no mês seguinte à data da compra.
    - O dia do vencimento será fixo (exemplo: dia 6).
    - Retorna uma lista de strings no formato 'YYYY-MM-DD'.
    """
    datas_pagamento = []
    data_base = datetime.strptime(data_compra, "%Y-%m-%d")  # Converte a data da compra para datetime

    # Define a primeira data de vencimento para o mês seguinte ao da compra
    primeiro_vencimento = (data_base.replace(day=1) + timedelta(days=32)).replace(day=7)

    for parcela in range(num_parcelas):
        datas_pagamento.append(primeiro_vencimento.strftime("%Y-%m-%d"))
        # Avança para o próximo mês
        primeiro_vencimento = (primeiro_vencimento.replace(day=1) + timedelta(days=32)).replace(day=6)

    return datas_pagamento
