import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from backend.services.token_service import validar_token
import altair as alt

load_dotenv()

st.set_page_config(page_title="Dashboard Financeiro", layout="wide")
st.title("📊 Dashboard de Gastos - WhatsApp AI")
st.markdown("---")

query_params = st.query_params
phone = query_params.get("phone")
token = query_params.get("token")

resultado = validar_token(phone, token)
if not resultado:
    st.error("🔒 Link inválido ou expirado. Solicite um novo link.")
    st.stop()

schema, expira_em = resultado

fuso_brasilia = pytz.timezone("America/Sao_Paulo")
agora = datetime.now(fuso_brasilia)
expira_em = expira_em.astimezone(fuso_brasilia)

minutos_restantes = int((expira_em - agora).total_seconds() // 60)
expira_formatado = expira_em.strftime("%H:%M")

if minutos_restantes <= 0:
    st.error("❌ Este link já expirou. Por favor, solicite um novo.")
    st.stop()
elif minutos_restantes <= 5:
    st.warning(f"⚠️ Seu link expira em {minutos_restantes} minutos (às {expira_formatado}). Salve os dados se necessário.")
else:
    st.info(f"🔐 Link válido até às {expira_formatado} (horário de Brasília).")

DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
query = f"SELECT descricao, valor, categoria, meio_pagamento, data, tipo FROM {schema}.gastos ORDER BY data DESC"
df = pd.read_sql(query, conn)
df["data"] = pd.to_datetime(df["data"])
df.set_index("data", inplace=True)

cur = conn.cursor()
cur.execute(f"SELECT valor FROM {schema}.salario ORDER BY data DESC LIMIT 1")
salario = cur.fetchone()
salario = salario[0] if salario else 0

cur.execute(f"SELECT valor FROM {schema}.limite_cartao ORDER BY data DESC LIMIT 1")
limite = cur.fetchone()
limite = limite[0] if limite else 0

cur.execute(f"SELECT SUM(valor) FROM {schema}.gastos WHERE meio_pagamento = 'crédito' AND data >= date_trunc('month', CURRENT_DATE)")
fatura = cur.fetchone()
fatura = fatura[0] if fatura and fatura[0] else 0

cur.close()

st.markdown("### 📌 Visão Geral Financeira")
k1, k2, k3 = st.columns(3)
k1.metric("💵 Salário Atual", f"R$ {salario:,.2f}".replace(",", ".").replace(".", ",", 1))
k2.metric("💳 Fatura do Cartão", f"R$ {fatura:,.2f}".replace(",", ".").replace(".", ",", 1))
k3.metric("📈 Limite do Cartão", f"R$ {limite:,.2f}".replace(",", ".").replace(".", ",", 1))

abas = st.tabs(["📋 Visão Geral", "📂 Categorias", "💳 Pagamentos", "📅 Resumos", "🏆 Top Categorias", "🔮 Previsões", "🔔 Alertas", "📆 Calendário", "📊 Mês a Mês"])

with abas[0]:
    st.subheader("💰 Últimos Gastos Registrados")
    st.dataframe(df.reset_index())

with abas[1]:
    st.subheader("📈 Gastos por Categoria")
    chart_data_cat = df.groupby("categoria")["valor"].sum().reset_index()
    st.bar_chart(chart_data_cat, x="categoria", y="valor")

with abas[2]:
    st.subheader("💳 Gastos por Meio de Pagamento")
    df_pagamento = df.groupby("meio_pagamento")["valor"].sum().reset_index()
    tipo_grafico = st.radio("Tipo de Gráfico", ["Barras", "Pizza"], horizontal=True)
    if tipo_grafico == "Barras":
        st.bar_chart(df_pagamento.set_index("meio_pagamento"))
    else:
        chart = alt.Chart(df_pagamento).mark_arc().encode(
            theta=alt.Theta("valor", type="quantitative"),
            color=alt.Color("meio_pagamento", type="nominal"),
            tooltip=["meio_pagamento", "valor"]
        )
        st.altair_chart(chart, use_container_width=True)

with abas[3]:
    st.subheader("🗓️ Resumos por Período")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Gastos por Dia da Semana")
        df["dia_semana"] = df.index.day_name(locale="pt_BR")
        st.bar_chart(df.groupby("dia_semana")["valor"].sum())

    with col2:
        st.markdown("### Tendência Mensal (Cash Flow)")
        df_mensal = df.resample("M")["valor"].sum()
        st.line_chart(df_mensal)

with abas[4]:
    st.subheader("🏆 Top Categorias do Mês")
    hoje = datetime.now().replace(day=1)
    df_mes = df[df.index >= hoje]
    top_categorias = df_mes.groupby("categoria")["valor"].sum().nlargest(3).reset_index()
    st.write(top_categorias)

with abas[5]:
    st.subheader("🔮 Previsões Financeiras")
    st.info("Aqui poderiam ser exibidas previsões usando modelos estatísticos ou de Machine Learning, indicando tendências futuras com base no comportamento financeiro passado.")

with abas[6]:
    st.subheader("🔔 Alertas e Insights")
    if fatura >= 0.8 * limite:
        st.warning("⚠️ Sua fatura atingiu 80% ou mais do seu limite de crédito!")
    media_gastos = df["valor"].mean()
    gastos_acima_media = df[df["valor"] > media_gastos]
    if not gastos_acima_media.empty:
        st.warning("⚠️ Alguns gastos recentes estão acima da média. Considere revisar suas despesas.")

with abas[7]:
    st.subheader("📆 Calendário Interativo")
    st.write("Calendário com os dias de maiores gastos poderia ser exibido aqui.")

with abas[8]:
    st.subheader("📊 Comparação Mês a Mês")
    df_mes_a_mes = df.resample('M')['valor'].sum().reset_index()
    st.bar_chart(df_mes_a_mes.set_index("data"))

# 📥 Download CSV
df.reset_index().to_csv("gastos.csv", index=False)
with open("gastos.csv", "rb") as f:
    st.download_button(label="📥 Baixar CSV", data=f, file_name="gastos.csv", mime="text/csv")

conn.close()