📚 README.md - Bot Financeiro via WhatsApp

Um projeto completo e funcional de um Assistente Financeiro Inteligente via WhatsApp, desenvolvido com FastAPI, PostgreSQL e integração oficial com a WhatsApp Cloud API. Automatize a gestão dos seus gastos, controle faturas, receba cotações de moedas e configure lembretes personalizados — tudo através de mensagens no WhatsApp.

Deploy feito com Railway, com banco de dados e servidor integrados na nuvem.

🔧 Tecnologias Utilizadas

Tecnologia

Função

FastAPI

Backend moderno, assíncrono e com rotas elegantes

PostgreSQL

Armazenamento dos dados financeiros, faturas, lembretes e salários

Railway

Infraestrutura em nuvem para API + banco de dados

WhatsApp Cloud API

Integração direta com o WhatsApp Oficial (via Meta)

APScheduler

Agendamento de mensagens com suporte a expressões CRON

httpx / requests

Requisições externas para APIs e chamadas assíncronas

dotenv

Gerenciamento de variáveis sensíveis via .env

📁 Estrutura de Pastas

.
├── backend
│   ├── main.py                  # Arquivo principal com as rotas da API (Webhook)
│   ├── services
│   │   ├── whatsapp_service.py  # Envio de mensagens e conexão com a API do WhatsApp
│   │   ├── cotacao_service.py   # Consome a AwesomeAPI para cotações de moedas
│   │   ├── gastos_service.py    # Processa, classifica e registra gastos e faturas
│   │   ├── scheduler.py         # Gerenciador de lembretes com cron
│   │   └── db_init.py           # Criação automática das tabelas no PostgreSQL
├── .env                         # Variáveis de ambiente como token e banco

💬 Funcionalidades Disponíveis via WhatsApp

🔹 Registro Inteligente de Gastos

Reconhece mensagens como mercado 120 pix, uber 40 crédito, tv 600 crédito 10x

Divide em:

Descrição (ex: "tv")

Valor (float)

Meio de pagamento (pix, débito, crédito)

Parcelas (1x, 10x etc)

🔹 Controle de Fatura de Cartão

Parcelas armazenadas individualmente na tabela fatura_cartao

Comando especial fatura paga! converte as parcelas do mês em gastos reais

🔹 Cotações de Moedas

Comando cotação → retorna cotações de USD, EUR, BTC, ETH, GBP

Comando cotação usd ou cotação btc → consulta moeda específica

🔹 Agendamento de Lembretes por CRON

Sintaxe no estilo:

lembrete: "revisar projeto"
cron: 0 8 * * 1-5

Executa lembretes com precisão usando o APScheduler

Mensagens personalizadas enviadas automaticamente no horário definido

🔹 Ajuda com Expressões CRON

Envie tabela de cron para receber exemplos explicativos

🔹 Consulta de Gasto Mensal

Comando total gasto no mês? → mostra o valor consolidado do mês atual

🗃️ Estrutura do Banco de Dados (PostgreSQL)

As tabelas são criadas automaticamente com db_init.py, mas podem ser visualizadas via Railway UI ou ferramentas SQL:

CREATE TABLE gastos (
  id SERIAL PRIMARY KEY,
  descricao TEXT,
  valor REAL,
  categoria TEXT,
  meio_pagamento TEXT,
  parcelas INT DEFAULT 1,
  data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fatura_cartao (
  id SERIAL PRIMARY KEY,
  descricao TEXT,
  valor REAL,
  categoria TEXT,
  meio_pagamento TEXT,
  parcela TEXT,
  data_inicio TIMESTAMP,
  data_fim DATE
);

CREATE TABLE lembretes (
  id SERIAL PRIMARY KEY,
  telefone TEXT,
  mensagem TEXT,
  cron TEXT
);

CREATE TABLE salario (
  id SERIAL PRIMARY KEY,
  valor REAL,
  data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

🌐 Integração com a API Oficial do WhatsApp (Cloud API)

Requisitos:

Conta no Facebook for Developers

Criar um App do tipo Empresa

Ativar o WhatsApp na seção de Produtos

Configurar o webhook com URL + token de verificação

Adicionar seu número como tester (modo desenvolvimento)

Payload Recebido:

{
  "entry": [
    {
      "changes": [
        {
          "value": {
            "messages": [
              {
                "from": "555199999999",
                "text": { "body": "cotação" },
                "timestamp": "1711417455"
              }
            ]
          }
        }
      ]
    }
  ]
}

🚀 Deploy no Railway (Backend + Banco)

Clonar este repositório e conectar ao Railway

Criar banco PostgreSQL pelo Railway UI

Adicionar .env com:

DATABASE_URL=postgresql://...
VERIFY_TOKEN=seu_token
WHATSAPP_NUMBER=seu_numero

O Railway gera a URL pública da sua API: https://nome-do-app.up.railway.app

Conectar essa URL ao webhook da Meta

📌 Exemplos de Comandos via WhatsApp

lanche 25 pix
uber 40 crédito
fatura paga!
cotação
cotação btc
lembrete: beber água
cron: 30 14 * * *
tabela de cron
total gasto no mês?

🧠 Lógica e Segurança

log_tempos() compara tempo do WhatsApp vs. tempo de resposta do servidor

Todas as rotas protegidas contra erro de payload

.env com variáveis sensíveis (jamais subir no repositório público)

Database com relações claras e normalizadas

💬 Funcionalidades via WhatsApp (Checklist)

✅ Registro de Gastos com descrição, valor, forma de pagamento e categoria inferida

✅ Parcelamento de compras no cartão de crédito (armazenadas com datas de início e fim)

✅ Cálculo automático da fatura atual com comando fatura paga!

✅ Cotação de moedas principais (USD, EUR, BTC etc.) via API externa

✅ Cotação específica com comando cotação USD, cotação BTC etc.

✅ Agendamento de lembretes com expressões CRON no estilo:

lembrete: "revisar projeto"
cron: 0 8 * * 1-5

✅ Envio automático dos lembretes na hora agendada via WhatsApp

✅ Consulta do total de gastos no mês com comando total gasto no mês?

✅ Ajuda com exemplos de CRON via tabela de cron

✅ Logs com tempo de resposta e timestamp de recebimento da mensagem

✅ Fallback para mensagens não reconhecidas com sugestão de formato correto

✅ Armazenamento persistente em PostgreSQL via Railway


✅ Próximos Passos

🔲 Interface web (Streamlit ou Dash) para visualização dos gastos e lembretes

🔲 Exportação de relatórios mensais (em CSV, Excel ou PDF)

🔲 Implementar suporte multiusuário (gastos e lembretes por telefone)

🔲 Adicionar autenticação de usuários com tokens temporários

🔲 Criar um painel de controle administrativo (via browser)

🔲 Melhorar a categorização automática com IA (embeddings + classificação)

🔲 Adicionar suporte a voz (com transcrição de áudios)

🔲 Criar versão PWA ou integração com Telegram

🔲 Deploy automatizado com CI/CD no GitHub Actions

🔲 Monitoramento de logs e uptime com alertas automáticos

✅ Próximos Passos

🔲 Interface web (Streamlit ou Dash) para visualização dos gastos e lembretes

🔲 Exportação de relatórios mensais (em CSV, Excel ou PDF)

🔲 Implementar suporte multiusuário (gastos e lembretes por telefone)

🔲 Adicionar autenticação de usuários com tokens temporários

🔲 Criar um painel de controle administrativo (via browser)

🔲 Melhorar a categorização automática com IA (embeddings + classificação)

🔲 Adicionar suporte a voz (com transcrição de áudios)

🔲 Criar versão PWA ou integração com Telegram

🔲 Deploy automatizado com CI/CD no GitHub Actions

🔲 Monitoramento de logs e uptime com alertas automáticos