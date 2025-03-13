const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const dotenv = require('dotenv');
const path = require('path');

dotenv.config(); // Carrega variáveis de ambiente do arquivo .env

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public'))); // Servir arquivos estáticos

const WHATSAPP_NUMBER = process.env.WHATSAPP_NUMBER || "556191178999";

const client = new Client({
    authStrategy: new LocalAuth({
        clientId: process.env.SESSION_NAME || "whatsapp_session"
    }),
    puppeteer: {
        headless: true, // Executar sem interface gráfica (necessário no Railway)
        args: [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--single-process",
            "--disable-gpu"
        ]
    }
});

// Variável para armazenar o QR Code temporariamente
let qrCodeData = "";

// Enviar o QR Code para o frontend (mas não exibir no terminal)
client.on('qr', (qr) => {
    qrCodeData = qr; // Armazena o QR Code para exibição no frontend
});

// Servir QR Code via API para exibição no frontend
app.get('/qrcode', (req, res) => {
    res.json({ qr: qrCodeData });
});

client.on('ready', () => {
    console.log('✅ Bot conectado com sucesso!');
});

client.on('message', async msg => {
    console.log(`📩 Mensagem recebida: ${msg.body} de ${msg.from}`);

    try {
        console.log("🔄 Enviando para API FastAPI...");
        const response = await fetch("whatsapp-fast-api.up.railway.app/webhook", {
            method: "POST", //http://127.0.0.1:8000/webhook
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: `Body=${encodeURIComponent(msg.body)}&From=whatsapp:${msg.from}`
        });

        const json = await response.json();
        console.log("📡 Resposta da API:", json);

        // **Aqui está a parte que estava faltando**
        if (json.resposta) {
            await client.sendMessage(msg.from, json.resposta);
            console.log("✅ Resposta enviada ao usuário!");
        }

    } catch (error) {
        console.error("❌ Erro ao processar mensagem:", error);
    }
});

// Inicia o WhatsApp Web.js
client.initialize();

// Rota para envio de mensagens
app.post('/send', async (req, res) => {
    const { number, message } = req.body;

    if (!number || !message) {
        return res.status(400).json({ error: 'Número e mensagem são obrigatórios!' });
    }

    const formattedNumber = `${number}@c.us`; // Garante que está mandando para o usuário correto

    try {
        await client.sendMessage(formattedNumber, message);
        res.json({ success: true, message: `Mensagem enviada para ${number}` });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Servir a página index.html
app.get("/", (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Iniciar o servidor Express
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🚀 API rodando em http://localhost:${PORT}`);
});