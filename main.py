import logging
import os
from dotenv import load_dotenv

from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)

# --- IMPORTAÇÕES ESSENCIAIS PARA O SEU FLUXO ---
import handlers 
from exportar_para_excel import export_data_to_drive 
# --- FIM DAS IMPORTAÇÕES ESSENCIAIS ---

from fastapi import FastAPI, Request
import uvicorn

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
application = None 

# --- Flag para notificar o primeiro usuário após a inicialização ---
bot_just_started = False 

# --- Funções do Bot do Telegram ---
async def cancelar(update: Update, context):
    """Cancela a operação atual do usuário e limpa os dados da conversa."""
    await update.message.reply_text("🚫 Operação cancelada. Se precisar, inicie um novo registro com /iniciar.")
    context.user_data.clear()
    return ConversationHandler.END

async def start(update: Update, context):
    """Comando /start para iniciar a interação com o bot."""
    await update.message.reply_text("👋 Olá! Bem-vindo(a) ao bot de registro de ocorrências. Use /iniciar para começar a registrar uma nova ocorrência.")

async def salvar_onedrive_telegram(update: Update, context):
    """
    Comando /salvar_onedrive: aciona a exportação das tabelas 'registros' e 'demandas' para o Google Drive.
    """
    logger.info(f"Comando /salvar_onedrive recebido de {update.effective_user.id}")
    await update.message.reply_text("⏳ Iniciando a exportação dos dados para o Google Drive. Isso pode levar um momento...")

    try:
        export_data_to_drive() 
        await update.message.reply_text("✅ Dados salvos no Google Drive com sucesso!")
    except Exception as e:
        logging.error(f"Erro ao salvar dados no Google Drive via Telegram: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ocorreu um erro ao salvar os dados no Google Drive: {e}")

async def set_webhook_command(update: Update, context):
    """
    Comando para configurar o webhook do Telegram.
    Deve ser executado uma vez após o deploy do bot no Render.
    """
    logger.info("Comando /setwebhook recebido.")
    
    render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    logger.info(f"Valor de RENDER_EXTERNAL_HOSTNAME: '{render_hostname}'")

    if not render_hostname:
        error_msg = "❌ Erro: Variável de ambiente RENDER_EXTERNAL_HOSTNAME não configurada ou vazia. Não foi possível definir o webhook."
        await update.message.reply_text(error_msg)
        logger.error(error_msg)
        return

    full_webhook_url = f"https://{render_hostname}/webhook"
    logger.info(f"Tentando configurar webhook para URL: {full_webhook_url}")

    try:
        await application.bot.set_webhook(url=full_webhook_url)
        success_msg = f"✅ Webhook configurado com sucesso para: <code>{full_webhook_url}</code>"
        await update.message.reply_text(success_msg, parse_mode='HTML') 
        logger.info(success_msg)
    except Exception as e:
        error_msg = f"❌ Falha ao configurar o webhook: {e}"
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
        
        global application 
        if application is None:
            logger.error("Erro: A instância 'application' do bot não foi inicializada no webhook. Isso não deveria acontecer.")
            return {"status": "error", "message": "Bot application not initialized"}, 500

        update = Update.de_json(request_json, application.bot)
        logger.info(f"Update do Telegram processado: {update.update_id}")
        
        # --- Lógica para notificar o usuário que acordou o bot ---
        global bot_just_started
        if bot_just_started:
            try:
                await application.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="👋 Olá! Eu acabei de acordar e estou pronto para processar sua solicitação. Por favor, aguarde a resposta ao seu comando."
                )
                logger.info(f"Notificação de 'bot acordado' enviada para o usuário {update.effective_chat.id}.")
                bot_just_started = False 
            except Exception as e:
                logger.error(f"Erro ao enviar notificação de 'bot acordado' para o usuário: {e}", exc_info=True)
        # --- FIM DA LÓGICA DE NOTIFICAÇÃO ---

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
    Aqui, o Application do python-telegram-bot é construído e inicializado,
    e a notificação de inicialização é enviada.
    """
    global application 
    global bot_just_started 
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

    # --- HANDLERS DE CONVERSAÇÃO ---
    if 'handlers' in globals() and hasattr(handlers, 'iniciar_colaborador'):
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('iniciar', handlers.iniciar_colaborador)],
            states={
                handlers.COLABORADOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.colaborador_manual), CallbackQueryHandler(handlers.colaborador_button)],
                handlers.COLABORADOR_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.colaborador_manual)],
                handlers.TIPO_VISITA: [CallbackQueryHandler(handlers.tipo_visita_escolha)], 
                # NOVO ESTADO E HANDLER PARA O MENU INICIAL DE ASSUNTO
                handlers.ASSUNTO_INICIAL_ESCOLHA: [CallbackQueryHandler(handlers.assunto_inicial_escolha)],
                handlers.ORGAO_PUBLICO_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.buscar_orgao)],
                handlers.ORGAO_PUBLICO_PAGINACAO: [CallbackQueryHandler(handlers.orgao_paginacao)],
                handlers.ORGAO_PUBLICO_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.orgao_manual)],
                handlers.FIGURA_PUBLICA: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.figura_publica_input)],
                handlers.CARGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.cargo)],
                # A PARTIR DAQUI, O FLUXO DE ASSUNTO PODE SER ACESSADO PELA ESCOLHA INICIAL OU POR BUSCA
                handlers.ASSUNTO_PALAVRA_CHAVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.buscar_assunto)],
                handlers.ASSUNTO_PAGINACAO: [CallbackQueryHandler(handlers.assunto_paginacao)],
                handlers.ASSUNTO_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.assunto_manual)],
                handlers.MUNICIPIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.municipio)],
                handlers.DATA: [CallbackQueryHandler(handlers.data)],
                handlers.DATA_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.data)],
                handlers.FOTO: [MessageHandler(filters.PHOTO & ~filters.COMMAND, handlers.foto)],
                handlers.DEMANDA_ESCOLHA: [CallbackQueryHandler(handlers.demanda)],
                handlers.DEMANDA_DIGITAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.demanda_digitar)],
                handlers.OV: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.ov)],
                handlers.PRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.pro)],
                handlers.OBSERVACAO_ESCOLHA: [CallbackQueryHandler(handlers.observacao_escolha)],
                handlers.OBSERVACAO_DIGITAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.observacao_digitar)],
                handlers.CONFIRMACAO_FINAL: [CallbackQueryHandler(handlers.confirmacao)],
            },
            fallbacks=[CommandHandler('cancelar', cancelar)], 
        )
        application.add_handler(conv_handler)
        logger.info("Handlers de conversação ativados.")
    else:
        logger.warning("Módulo 'handlers' não importado ou 'iniciar_colaborador' não encontrado. Handlers de conversação NÃO ativados.")
    # --- FIM DOS HANDLERS DE CONVERSAÇÃO ---

    logger.info("Telegram ApplicationBuilder built.")
    await application.initialize() 
    await application.start()     
    logger.info("Telegram Application started.")

    # --- Enviar notificação de inicialização para o ADMIN ---
    admin_telegram_id_str = os.getenv("ADMIN_TELEGRAM_ID")
    if admin_telegram_id_str:
        try:
            admin_telegram_id = int(admin_telegram_id_str)
            await application.bot.send_message(
                chat_id=admin_telegram_id,
                text="🚀 O bot foi iniciado/reiniciado com sucesso no Render! (Notificação para o Admin)"
            )
            logger.info(f"Notificação de inicialização enviada para o admin ID: {admin_telegram_id}")
        except ValueError:
            logger.error(f"ADMIN_TELEGRAM_ID '{admin_telegram_id_str}' não é um ID de usuário válido (deve ser um número inteiro).")
        except Exception as e:
            logger.error(f"Erro ao enviar notificação de inicialização para o admin: {e}", exc_info=True)
    else:
        logger.warning("Variável de ambiente ADMIN_TELEGRAM_ID não definida. Nenhuma notificação de inicialização será enviada para o admin.")
    # --- FIM DA NOTIFICAÇÃO PARA O ADMIN ---

    # Define a flag global para indicar que o bot acabou de iniciar
    bot_just_started = True 
    logger.info("Flag 'bot_just_started' definida como True.")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Evento de desligamento do FastAPI.
    Aqui, o Application do python-telegram-bot é parado.
    """
    logger.info("FastAPI shutdown event triggered.")
    if application:
        await application.stop() 
        logger.info("Telegram Application stopped.")

# --- Ponto de Entrada Principal para Uvicorn (Render) ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Running Uvicorn directly via __main__ on port: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)



@app.get("/ping")
async def ping_endpoint():
    """
    Endpoint simples para monitoramento de disponibilidade.
    Apenas retorna um status "OK" para indicar que o serviço está ativo.
    """
    logger.info("Requisição GET recebida no endpoint /ping. Bot está ativo.")
    return {"status": "OK", "message": "Bot is alive!"}