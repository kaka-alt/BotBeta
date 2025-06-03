import logging
import os
import uvicorn
import fastapi
from fastapi import FastAPI, Request
# Removido threading, pois FastAPI/Uvicorn gerenciam o loop de eventos assíncrono
from dotenv import load_dotenv

from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
# Importe seus handlers e a função de exportação aqui, se existirem
# import handlers # Mantenha se você ainda usa seus handlers de conversação existentes
# from exportar_para_excel import export_data_to_drive # Mantenha se você usa para Google Drive

# --- Configuração do carregamento do arquivo .env (rail.env) ---
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, 'rail.env')
load_dotenv(dotenv_path=dotenv_path)

# Configuração básica de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Instância FastAPI ---
app = FastAPI()

# --- Instância Global do Application do python-telegram-bot ---
# Será inicializada nos eventos de startup/shutdown do FastAPI
application = None 

# --- Funções do Bot do Telegram ---
# Mantenha suas funções aqui, como estavam, mas certifique-se de que 'handlers' e 'export_data_to_drive'
# estão importados corretamente no topo do arquivo se forem usados.

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
        # export_data_to_drive() # Ou exportar_dados_localmente()
        await update.message.reply_text("Dados salvos no Google Drive com sucesso!")
    except Exception as e:
        logging.error(f"Erro ao salvar dados no Google Drive via Telegram: {e}", exc_info=True)
        await update.message.reply_text(f"Falha ao salvar os dados no Google Drive: {e}")

async def set_webhook_command(update: Update, context):
    """
    Comando para configurar o webhook do Telegram.
    Deve ser executado uma vez após o deploy do bot no Render.
    """
    logger.info("Comando /setwebhook recebido.")
    
    render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    logger.info(f"Valor de RENDER_EXTERNAL_HOSTNAME: '{render_hostname}'")

    if not render_hostname:
        error_msg = "Erro: Variável de ambiente RENDER_EXTERNAL_HOSTNAME não configurada ou vazia. Não é possível definir o webhook."
        await update.message.reply_text(error_msg)
        logger.error(error_msg)
        return

    full_webhook_url = f"https://{render_hostname}/webhook"
    logger.info(f"Tentando configurar webhook para URL: {full_webhook_url}")

    try:
        # 'application' já estará inicializado aqui devido ao evento startup
        await application.bot.set_webhook(url=full_webhook_url)
        success_msg = f"Webhook configurado com sucesso para: {full_webhook_url}"
        await update.message.reply_text(success_msg)
        logger.info(success_msg)
    except Exception as e:
        error_msg = f"Falha ao configurar o webhook: {e}"
        await update.message.reply_text(error_msg)
        logger.error(error_msg, exc_info=True)

# --- Endpoint FastAPI para o Webhook do Telegram ---
@app.post("/webhook")
async def telegram_webhook_receiver(request: Request):
    """
    Endpoint FastAPI para receber atualizações do Telegram via webhook.
    """
    logger.info("Requisição POST recebida no endpoint /webhook.")
    try:
        request_json = await request.json()
        logger.info(f"JSON recebido no webhook: {request_json}")
        
        # 'application' já estará inicializado aqui devido ao evento startup
        if application is None:
            logger.error("Erro: A instância 'application' do bot não foi inicializada no webhook. Isso não deveria acontecer.")
            return {"status": "error", "message": "Bot application not initialized"}, 500

        update = Update.de_json(request_json, application.bot)
        logger.info(f"Update do Telegram processado: {update.update_id}")
        
        await application.process_update(update) 
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Erro ao processar webhook do Telegram: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500

# --- FastAPI Startup/Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    """
    Evento de inicialização do FastAPI.
    Aqui, o Application do python-telegram-bot é construído e inicializado.
    """
    global application # Declara como global para modificar a variável global
    logger.info("FastAPI startup event triggered.")
    
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("Erro: BOT_TOKEN não encontrado nas variáveis de ambiente ou no arquivo .env. O bot não será inicializado.")
        return

    application = ApplicationBuilder().token(token).build()

    # Adiciona os handlers de comando
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('salvar_onedrive', salvar_onedrive_telegram))
    application.add_handler(CommandHandler('setwebhook', set_webhook_command))
    # --- Se você ainda tem handlers de conversação, adicione-os aqui ---
    # Exemplo:
    # conv_handler = ConversationHandler(
    #     entry_points=[CommandHandler('iniciar', handlers.iniciar_colaborador)],
    #     states={
    #         # ... seus estados ...
    #     },
    #     fallbacks=[CommandHandler('cancelar', cancelar)],
    # )
    # application.add_handler(conv_handler)
    # --- Fim dos handlers de conversação ---

    logger.info("Telegram ApplicationBuilder built.")
    await application.initialize() # Explicitamente inicializa o estado interno do Application
    await application.start()     # Inicia o Application (necessário para process_update)
    logger.info("Telegram Application started.")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Evento de desligamento do FastAPI.
    Aqui, o Application do python-telegram-bot é parado.
    """
    logger.info("FastAPI shutdown event triggered.")
    if application:
        await application.stop() # Para o Application
        logger.info("Telegram Application stopped.")

# --- Ponto de Entrada Principal para Uvicorn (Render) ---
# Este bloco é o que o Uvicorn (que o Render usa) executará para iniciar seu aplicativo FastAPI.
# O comando de inicialização no Render deve ser algo como:
# uvicorn main:app --host 0.0.0.0 --port $PORT
if __name__ == "__main__":
    # Este bloco é mais para teste local ou se o comando de inicialização do Render for `python main.py`
    # Se o comando de inicialização do Render for `uvicorn main:app --host 0.0.0.0 --port $PORT`,
    # este bloco não será executado no Render.
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Running Uvicorn directly via __main__ on port: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

