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

# async def exibir_menu_ajuda(telefone: str):
#     admin_phone = os.getenv("ADMIN_PHONE")

#     if telefone == admin_phone:
#         texto_ajuda = (
#             "🛠️ *Menu de Ajuda - Administrador*\n\n"
#             "📌 *Comandos Gerais:*\n"
#             "• `ajuda` → Mostra este menu\n"
#             "• `total gasto` → Mostra quanto o usuário gastou ante então no mês (não inclui o valor da fatura até ela ser paga)\n"
#             "• `gráficos` → Manda pro usuário um link em que terãos os gráficos\n"
#             "• `fatura paga` → Comunica o assistente dê que a fatura foi paga\n"
#             "• `cotação` → Mostra as principais moedas do dia em R$\n"
#             "• `lista cotação` → Mostra as moedas disponíveis\n"
#             "• `cotação [moeda]` → Mostra uma moeda(X) em específico em R$\n"
#             "• `cotação [moeda]-[moeda]` → Mostra a conversão de uma moeda em outra moeda\n"
#             "• `cep [numero]` → Mostra o endereço a partir do cep\n"
#             "• `lembrete: \"mensagem\"` + `cron: padrão` → Agenda lembrete\n"
#             "• `tabela cron → Mostra exemplos de como montar certos crons\n"
#             "• `lista lembretes` → Lista seus lembretes\n"
#             "• `apagar lembrete [id]` → Apaga um lembrete\n\n"
#             "👑 *Comandos de Admin:*\n"
#             "• `liberar [telefone] [nome]` → Autoriza novo número e cria schema\n"
#             "• `não liberar` → Não autoriza um número e informa a ele que ele foi recusado\n"
#             "• `lista usuarios` → Mostra os usuários que estão autorizados a usar o bot\n"
#             "• `revogar [telefone]` → Revoga o usuário do número escolhido\n"
#             "• (Recebe notificações quando alguém não autorizado envia mensagem)\n"
#         )
#     else:
#         texto_ajuda = (
#             "🤖 *Menu de Ajuda - Assistente Financeiro*\n\n"
#             "📌 *Comandos disponíveis:*\n"
#             "• `ajuda` → Mostra este menu\n"
#             "• `cotação` → Mostra as principais moedas do dia\n"
#             "• `lembrete: \"mensagem\"` + `cron: padrão` → Agenda lembrete\n"
#             "• `lista lembretes` → Lista seus lembretes\n"
#             "• `apagar lembrete [id]` → Apaga um lembrete\n\n"
#             "Exemplo de agendamento:\n"
#             "🕒 `lembrete: \"Pagar conta\"`\n"
#             "`cron: 0 9 * * 1-5` → Todos os dias úteis às 9h"
#         )

#     await enviar_mensagem_whatsapp(telefone, texto_ajuda)

