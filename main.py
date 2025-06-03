import logging
import os
import threading
from dotenv import load_dotenv

from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
import handlers # Mantenha se você ainda usa seus handlers de conversação existentes

from fastapi import FastAPI, Request
import uvicorn

# --- Configuração do carregamento do arquivo .env (rail.env) ---
# Este bloco garante que as variáveis de ambiente sejam carregadas corretamente
# quando você roda o script localmente. No Render, elas já serão injetadas.
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, 'rail.env') # Assumindo rail.env ou .env na raiz
load_dotenv(dotenv_path=dotenv_path)

# Importa a função principal de exportação do seu arquivo exportar_para_excel.py
# Certifique-se de que o caminho e o nome da função estão corretos.
from exportar_para_excel import export_data_to_drive # Se você renomeou para export_data_to_drive
# Ou from exportar_para_excel import exportar_dados_localmente # Se você manteve o nome original

# Configuração básica de logging para ver as mensagens no console/logs do Render
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Instância FastAPI ---
app = FastAPI()

# --- Instância Global do Application do python-telegram-bot ---
# Precisamos que esta instância seja acessível tanto pelo webhook FastAPI quanto pelos handlers do bot.
application = None 

# --- Funções do Bot do Telegram ---
async def cancelar(update: Update, context):
    """Cancela a operação atual do usuário e limpa os dados da conversa."""
    await update.message.reply_text("Operação cancelada pelo usuário.")
    context.user_data.clear()
    return ConversationHandler.END

async def start(update: Update, context):
    """Comando /start para iniciar a interação com o bot."""
    await update.message.reply_text("Olá! Use /iniciar para começar o registro de uma ocorrência.")

async def salvar_onedrive_telegram(update: Update, context):
    """
    Comando /salvar_onedrive: aciona a exportação das tabelas 'registros' e 'demandas' para o Google Drive.
    (O nome do comando ainda é OneDrive, mas a funcionalidade é Google Drive)
    """
    logger.info(f"Comando /salvar_onedrive recebido de {update.effective_user.id}")
    await update.message.reply_text("Iniciando a exportação dos dados para o Google Drive. Isso pode levar um momento...")

    try:
        # Chama a função principal de backup do exportar_para_excel.py
        # Essa função se encarrega de ler do banco, gerar Excel e enviar para o Google Drive.
        # Use o nome da função que você tem no seu exportar_para_excel.py
        export_data_to_drive() # Ou exportar_dados_localmente()
        await update.message.reply_text("Dados salvos no Google Drive com sucesso!")
    except Exception as e:
        logging.error(f"Erro ao salvar dados no Google Drive via Telegram: {e}", exc_info=True)
        await update.message.reply_text(f"Falha ao salvar os dados no Google Drive: {e}")

async def set_webhook_command(update: Update, context):
    """
    Comando para configurar o webhook do Telegram.
    Deve ser executado uma vez após o deploy do bot no Render.
    """
    # Render injeta o hostname público do seu serviço na variável de ambiente RENDER_EXTERNAL_HOSTNAME
    render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if not render_hostname:
        await update.message.reply_text("Erro: Variável de ambiente RENDER_EXTERNAL_HOSTNAME não configurada. Não é possível definir o webhook.")
        logger.error("RENDER_EXTERNAL_HOSTNAME não configurado. Não é possível definir o webhook.")
        return

    # Constrói a URL completa do webhook para o endpoint FastAPI
    # O Render fornece HTTPS automaticamente para seus domínios.
    full_webhook_url = f"https://{render_hostname}/webhook"

    try:
        # Define o webhook no Telegram
        await application.bot.set_webhook(url=full_webhook_url)
        await update.message.reply_text(f"Webhook configurado com sucesso para: {full_webhook_url}")
        logger.info(f"Webhook configurado para: {full_webhook_url}")
    except Exception as e:
        await update.message.reply_text(f"Falha ao configurar o webhook: {e}")
        logger.error(f"Falha ao configurar o webhook: {e}", exc_info=True)

# --- Endpoint FastAPI para o Webhook do Telegram ---
@app.post("/webhook")
async def telegram_webhook_receiver(request: Request):
    """
    Endpoint FastAPI para receber atualizações do Telegram via webhook.
    """
    try:
        request_json = await request.json()
        # Cria um objeto Update a partir do JSON recebido
        update = Update.de_json(request_json, application.bot)
        # Processa a atualização usando o application do python-telegram-bot
        await application.process_update(update) 
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Erro ao processar webhook do Telegram: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500

# --- Função para iniciar o servidor FastAPI ---
def iniciar_fastapi():
    """
    Função para iniciar o servidor FastAPI em uma thread separada.
    Ele escutará na porta definida pela variável de ambiente PORT do Render.
    """
    port = int(os.getenv("PORT", 8000)) # Render injeta a variável de ambiente PORT
    logger.info(f"Iniciando FastAPI na porta: {port}")
    # O uvicorn.run bloqueia o thread em que é executado.
    # Por isso, ele é iniciado em uma thread separada para não bloquear o main.
    uvicorn.run(app, host="0.0.0.0", port=port)

# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    # Inicializa a instância global do Application do python-telegram-bot
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("Erro: BOT_TOKEN não encontrado nas variáveis de ambiente ou no arquivo .env.")
        logger.error("Certifique-se de que a variável BOT_TOKEN está configurada.")
        exit(1) # Sai se o token não for encontrado

    application = ApplicationBuilder().token(token).build()

    # Adiciona os handlers de comando
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('salvar_onedrive', salvar_onedrive_telegram)) # Mantenha se ainda usa
    application.add_handler(CommandHandler('setwebhook', set_webhook_command)) # NOVO: Comando para definir o webhook

    # --- Se você ainda tem handlers de conversação, adicione-os aqui ---
    # Exemplo:
    # conv_handler = ConversationHandler(
    #     entry_points=[CommandHandler('iniciar', handlers.iniciar_colaborador)],
    #     states={
    #         # ... seus estados (igual acima) ...
    #     },
    #     fallbacks=[CommandHandler('cancelar', cancelar)],
    # )
    # application.add_handler(conv_handler)
    # --- Fim dos handlers de conversação ---

    # Inicia o servidor FastAPI em uma thread separada em segundo plano.
    # `daemon=True` garante que a thread do FastAPI será encerrada se o programa principal (bot) terminar.
    threading.Thread(target=iniciar_fastapi, daemon=True).start()

    logger.info("Bot Telegram configurado para receber webhooks via FastAPI.")
    logger.info("Após o deploy no Render, execute o comando /setwebhook no Telegram para configurar o webhook.")
    logger.info("O serviço Render será ativado por requisições HTTP do webhook.")

    # O thread principal simplesmente espera, permitindo que a thread FastAPI e o bot funcionem.
    # Para garantir que o processo não termine imediatamente em alguns ambientes,
    # você pode adicionar um loop simples ou um sleep longo, mas para Render com FastAPI daemon,
    # o uvicorn manterá o processo vivo.
    threading.Event().wait() # Mantém o thread principal vivo indefinidamente
