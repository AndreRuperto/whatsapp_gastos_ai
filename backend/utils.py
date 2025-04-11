import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

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