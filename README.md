# 🤖 Bot Financeiro via WhatsApp

Um assistente pessoal para te ajudar a controlar seus **gastos, faturas, cotações de moedas e lembretes** — tudo isso diretamente pelo WhatsApp, com mensagens simples e automações inteligentes.

Este projeto foi desenvolvido com **FastAPI**, **PostgreSQL** e integração oficial com a **WhatsApp Cloud API** (Meta), proporcionando uma experiência prática, segura e totalmente automatizada.

> 🚀 Deploy feito na **nuvem com Railway**, conectando o backend e o banco de dados de forma integrada.

---

## 🔧 Tecnologias Utilizadas

| Tecnologia             | Descrição                                                             |
|------------------------|----------------------------------------------------------------------|
| **FastAPI**            | Backend moderno e assíncrono, com rotas enxutas e desempenho elevado |
| **PostgreSQL**         | Banco de dados relacional para armazenar gastos, lembretes e salários|
| **Railway**            | Plataforma de deploy e hospedagem para o backend + banco             |
| **WhatsApp Cloud API** | Integração oficial com o WhatsApp (Meta)                             |
| **APScheduler**        | Agendador de tarefas com suporte a expressões CRON                   |
| **httpx / requests**   | Consumo de APIs externas com suporte assíncrono                      |
| **dotenv**             | Gerenciamento de variáveis de ambiente de forma segura               |

---

## 📁 Estrutura de Pastas do Projeto

backend/
├── main.py               # Rotas principais da API (Webhook)
├── services/             # Lógica de negócio dividida por contexto
│   ├── whatsapp_service.py  # Comunicação com a API oficial do WhatsApp
│   ├── cotacao_service.py   # Busca cotações em tempo real via AwesomeAPI
│   ├── gastos_service.py    # Processa e armazena os gastos e faturas
│   ├── scheduler.py         # Lógica de agendamento dos lembretes (CRON)
│   └── db_init.py           # Inicializa as tabelas no banco de dados PostgreSQL
├── .env                 # Variáveis sensíveis como token, número e URL do banco

---

## 💬 Funcionalidades Disponíveis via WhatsApp

### 📝 Registro Inteligente de Gastos

Exemplo de mensagem:
```
tv 600 crédito 10x
uber 40 pix
```

O bot entende e armazena:
- Descrição (ex: "tv")
- Valor (float)
- Meio de pagamento (pix, crédito, débito)
- Parcelas (1x, 10x, etc.)

---

### 💳 Controle de Fatura de Cartão

- Armazena parcelas separadamente na tabela `fatura_cartao`
- Comando `fatura paga!` converte todas as parcelas do mês em gastos reais

---

### 💱 Cotações de Moedas

- `cotação` → USD, EUR, BTC, ETH, GBP
- `cotação btc` ou `cotação usd` → específica

---

### ⏰ Agendamento de Lembretes (Estilo CRON)

Mensagem:
```
lembrete: "beber água"
cron: 30 14 * * *
```

Agendamento via APScheduler com envio automático pelo WhatsApp.

---

### 🔎 Consulta de Gasto Mensal

- Comando: `total gasto no mês?`

---

### 📚 Ajuda com CRON

- Comando: `tabela de cron` → envia exemplos prontos

---

## 🗃️ Estrutura do Banco (PostgreSQL)

```sql
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
```

---

## 🌐 Integração com WhatsApp Cloud API

### Requisitos:
- Conta no [Facebook for Developers](https://developers.facebook.com/)
- App do tipo Empresa + WhatsApp ativado
- Webhook configurado com token + URL pública (via Railway)
- Número de telefone adicionado como tester

### Exemplo de Payload:
```json
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
```

---

## 🚀 Deploy no Railway

1. Clone o repositório
2. Crie um banco PostgreSQL na Railway
3. Adicione `.env` com:
```env
DATABASE_URL=postgresql://...
VERIFY_TOKEN=seu_token
WHATSAPP_NUMBER=seu_numero
```
4. Conecte a URL gerada ao webhook da Meta

---

## 📌 Exemplos de Comandos via WhatsApp

```
lanche 25 pix
uber 40 crédito
fatura paga!
cotação
cotação btc
lembrete: beber água cron: 30 14 * * *
tabela de cron
total gasto no mês?
```

---

## 🧠 Lógica e Segurança

- `log_tempos()` compara tempo do WhatsApp e resposta do servidor
- Rotas protegidas contra payloads inválidos
- `.env` nunca exposto no repositório
- Banco de dados estruturado e normalizado

---

## ✅ Checklist de Funcionalidades

- [x] Registro inteligente de gastos
- [x] Parcelamento no cartão com controle de fatura
- [x] Cotação de moedas (geral e específica)
- [x] Lembretes com CRON
- [x] Consulta do total mensal
- [x] Ajuda com exemplos de CRON
- [x] Logs e segurança nas rotas
- [x] Armazenamento persistente em PostgreSQL

---

## 🔮 Próximos Passos

- [ ] Interface web com gráficos e filtros (Streamlit ou Dash)
- [ ] Exportação de relatórios (CSV, Excel, PDF)
- [ ] Suporte multiusuário (gastos e lembretes por telefone)
- [ ] Autenticação com tokens temporários
- [ ] Painel administrativo web
- [ ] IA para categorização inteligente (via embeddings)
- [ ] Suporte a voz (transcrição de áudio)
- [ ] Versão PWA ou integração com Telegram
- [ ] Deploy automatizado com GitHub Actions
- [ ] Monitoramento e alertas automáticos

---

📣 **Contribuições são muito bem-vindas!**  
📬 Dúvidas, sugestões ou melhorias? Envie uma mensagem ou abra uma issue.