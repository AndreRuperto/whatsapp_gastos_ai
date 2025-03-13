import streamlit as st
import pandas as pd
import psycopg2
import os
import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Conectar ao banco de dados
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Criar o dashboard no Streamlit
st.title("📊 Dashboard de Gastos - WhatsApp AI")
st.markdown("---")

# Consultar os dados
query = "SELECT descricao, valor, categoria, meio_pagamento, data FROM gastos ORDER BY data DESC"
df = pd.read_sql(query, conn)

# Exibir tabela
st.subheader("💰 Últimos Gastos Registrados")
st.dataframe(df)

# Filtros
categoria = st.selectbox("Filtrar por Categoria", ["Todas"] + list(df["categoria"].unique()))
if categoria != "Todas":
    df = df[df["categoria"] == categoria]

# Gráfico temporal
st.subheader("📅 Gastos ao longo do tempo")
df["data"] = pd.to_datetime(df["data"])
df.set_index("data", inplace=True)
st.line_chart(df["valor"])

# Gráfico de gastos por categoria
st.subheader("📈 Gastos por Categoria")
chart_data = df.groupby("categoria")["valor"].sum().reset_index()
st.bar_chart(chart_data, x="categoria", y="valor")

# Opção de download
df.to_csv("gastos.csv", index=False)
st.download_button(label="📥 Baixar CSV", data=open("gastos.csv", "rb"), file_name="gastos.csv", mime="text/csv")

cursor.close()
conn.close()