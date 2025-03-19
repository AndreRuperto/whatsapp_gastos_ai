const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const dotenv = require('dotenv');
const path = require('path');
const puppeteer = require('puppeteer-core');

dotenv.config(); // Carrega variáveis de ambiente do arquivo .env

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public'))); // Servir arquivos estáticos
const PORT = process.env.PORT;
const chromePath = process.env.CHROME_PATH;

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        executablePath: chromePath,
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

// Variável para armazenar o QR Code temporariamente
let qrCodeData = "";

// Evento de QR Code - Armazena o QR Code para exibição no frontend
client.on('qr', (qr) => {
    qrCodeData = qr;
});

// **Rota para servir o QR Code**
app.get('/qrcode', (req, res) => {
    if (qrCodeData) {
        res.json({ qr: qrCodeData });
    } else {
        res.status(404).json({ error: "QR Code ainda não gerado." });
    }
});

client.on('ready', () => {
    console.log('✅ Bot conectado com sucesso!');
});

client.on('message', async msg => {
    console.log(`📩 Mensagem recebida: ${msg.body} de ${msg.from}`);

    try {
        console.log("🔄 Enviando para API FastAPI...");
        const response = await fetch("https://whatsapp-fast-api.up.railway.app/webhook", {
            method: "POST", //http://127.0.0.1:8000/webhook
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: `Body=${encodeURIComponent(msg.body)}&From=whatsapp:${msg.from}`
        });

        console.log("📡 Resposta enviada para API FastAPI com sucesso!");
        
    } catch (error) {
        console.error("❌ Erro ao processar mensagem:", error);
    }
});

// Inicia o WhatsApp Web.js
client.initialize();

// **Rota para envio de mensagens**
app.post('/send', async (req, res) => {
    let { number, message } = req.body;

    if (!number || !message) {
        console.log("⚠️ Body inválido:", req.body);
        return res.status(400).json({ error: 'Número e mensagem são obrigatórios!' });
    }

    // Garante que `@c.us` não seja adicionado duas vezes
    if (!number.endsWith("@c.us")) {
        number = `${number}@c.us`;
    }
    
    try {
        await client.sendMessage(number, message);
        res.json({ success: true, message: `✅ Mensagem enviada para ${number}` });
    } catch (error) {
        console.error("❌ Erro ao enviar mensagem:", error);
        res.status(500).json({ error: error.message });
    }
});

// **Rota para servir a página index.html**
app.get("/", (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// **Iniciar o servidor Express**
app.listen(PORT, '0.0.0.0', () => {
    console.log(`🚀 API rodando na porta ${PORT}`);
});
