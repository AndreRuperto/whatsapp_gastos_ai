import logging
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")

def listar_usuarios_autorizados():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT nome, telefone, data_inclusao FROM usuarios WHERE autorizado = TRUE ORDER BY data_inclusao DESC")
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()

    return resultados

def revogar_autorizacao(telefone: str) -> bool:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET autorizado = FALSE WHERE telefone = %s", (telefone,))
    sucesso = cursor.rowcount > 0
    conn.commit()
    cursor.close()
    conn.close()
    return sucesso
