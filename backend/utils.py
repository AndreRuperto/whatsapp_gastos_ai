import os
import psycopg2
from backend.services.db_init import conectar_bd
import pytz
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
fuso_brasilia = pytz.timezone("America/Sao_Paulo")

def obter_schema_por_telefone(telefone):
    """
    Consulta a tabela 'usuarios' e retorna o nome do schema com base no telefone.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT schema_user FROM usuarios WHERE telefone = %s AND autorizado = true", (telefone,))
    resultado = cursor.fetchone()
    nome = resultado[0]
    cursor.close()
    conn.close()
    
    return nome

def mensagem_ja_processada(mensagem_id: str) -> bool:
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM mensagens_recebidas WHERE mensagem_id = %s", (mensagem_id,))
    existe = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return existe

def registrar_mensagem_recebida(mensagem_id: str, telefone: str = "", tipo: str = "texto"):
    agora = datetime.now(fuso_brasilia)
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO mensagens_recebidas (mensagem_id, telefone, tipo, data_processamento)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (mensagem_id, telefone, tipo, agora))
    conn.commit()
    cursor.close()
    conn.close()