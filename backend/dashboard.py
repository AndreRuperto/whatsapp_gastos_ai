import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurar conexão com PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Criar o dashboard no Streamlit
st.title("📊 Dashboard de Gastos - WhatsApp AI")
st.markdown("---")

# Consultar os dados do banco
query = "SELECT descricao, valor, categoria, data FROM gastos ORDER BY data DESC"
df = pd.read_sql(query, conn)

# Exibir a tabela de gastos
st.subheader("💰 Últimos Gastos Registrados")
st.dataframe(df)

# Filtros interativos
categoria = st.selectbox("Filtrar por Categoria", ["Todas"] + list(df["categoria"].unique()))
if categoria != "Todas":
    df = df[df["categoria"] == categoria]

# Gráfico de Gastos por Categoria
st.subheader("📈 Gastos por Categoria")
chart_data = df.groupby("categoria")["valor"].sum().reset_index()
st.bar_chart(chart_data, x="categoria", y="valor")

# Total de gastos no mês
st.subheader("💸 Total Gasto no Mês")
total_gasto = df["valor"].sum()
st.metric(label="Total Gasto", value=f"R$ {total_gasto:.2f}")

# Fechar conexão com o banco
df.to_csv("gastos.csv", index=False)  # Opção para download
cursor.close()
conn.close()

st.download_button(label="📥 Baixar CSV", data=open("gastos.csv", "rb"), file_name="gastos.csv", mime="text/csv")