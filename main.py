import os
import logging
from dotenv import load_dotenv

from fastapi import FastAPI, Request
import uvicorn

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

import handlers
from exportar_para_excel import export_data_to_drive

# Carregar variáveis do .env (rail.env)
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, 'rail.env')
load_dotenv(dotenv_path=dotenv_path)

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Instância do FastAPI
app = FastAPI()

# Variáveis globais
application = None
bot_just_started = False


# Handlers do Telegram

async def start(update: Update, context):
    await update.message.reply_text(
        "👋 Olá! Bem-vindo(a) ao bot de registro de ocorrências.\n"
        "Use /iniciar para começar a registrar uma nova ocorrência."
    )


async def cancelar(update: Update, context):
    await update.message.reply_text(
        "🚫 Operação cancelada. Se precisar, inicie um novo registro com /iniciar."
    )
    context.user_data.clear()
    return ConversationHandler.END


async def salvar_onedrive_telegram(update: Update, context):
    logger.info(f"Comando /salvar_onedrive recebido de {update.effective_user.id}")
    await update.message.reply_text(
        "⏳ Iniciando a exportação dos dados para o Google Drive. Isso pode levar um momento..."
    )
    try:
        export_data_to_drive()
        await update.message.reply_text("✅ Dados salvos no Google Drive com sucesso!")
    except Exception as e:
        logger.error(f"Erro ao salvar dados no Google Drive via Telegram: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ocorreu um erro ao salvar os dados: {e}")


async def set_webhook_command(update: Update, context):
    logger.info("Comando /setwebhook recebido.")
    render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    logger.info(f"Valor de RENDER_EXTERNAL_HOSTNAME: '{render_hostname}'")

    if not render_hostname:
        error_msg = (
            "❌ Erro: Variável de ambiente RENDER_EXTERNAL_HOSTNAME não configurada "
            "ou vazia. Não foi possível definir o webhook."
        )
        await update.message.reply_text(error_msg)
        logger.error(error_msg)
        return

    full_webhook_url = f"https://{render_hostname}/webhook"
    logger.info(f"Tentando configurar webhook para URL: {full_webhook_url}")

    try:
        await application.bot.set_webhook(url=full_webhook_url)
        success_msg = f"✅ Webhook configurado com sucesso para: <code>{full_webhook_url}</code>"
        await update.message.reply_text(success_msg, parse_mode="HTML")
        logger.info(success_msg)
    except Exception as e:
        error_msg = f"❌ Falha ao configurar o webhook: {e}"
        await update.message.reply_text(error_msg)
        logger.error(error_msg, exc_info=True)


# Endpoint para receber updates do Telegram via webhook
@app.post("/webhook")
async def telegram_webhook_receiver(request: Request):
    logger.info("Requisição POST recebida no endpoint /webhook.")
    try:
        request_json = await request.json()
        logger.debug(f"JSON recebido no webhook: {request_json}")

        global application, bot_just_started
        if application is None:
            logger.error("Erro: Instância 'application' do bot não inicializada no webhook.")
            return {"status": "error", "message": "Bot application not initialized"}, 500

        update = Update.de_json(request_json, application.bot)
        logger.info(f"Update do Telegram processado: {update.update_id}")

        if bot_just_started:
            try:
                await application.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        "👋 Olá! Eu acabei de acordar e estou pronto para processar sua solicitação. "
                        "Por favor, aguarde a resposta ao seu comando."
                    ),
                )
                logger.info(f"Notificação de 'bot acordado' enviada para usuário {update.effective_chat.id}.")
                bot_just_started = False
            except Exception as e:
                logger.error(
                    f"Erro ao enviar notificação de 'bot acordado' para usuário: {e}", exc_info=True
                )

        await application.process_update(update)
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Erro ao processar webhook do Telegram: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500


# Função para construir o ConversationHandler com seus handlers
def build_conversation_handler():
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("iniciar", handlers.iniciar_colaborador)],
        states={
            handlers.COLABORADOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.colaborador_manual),
                CallbackQueryHandler(handlers.colaborador_button),
            ],
            handlers.COLABORADOR_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.colaborador_manual)],
            handlers.TIPO_VISITA: [CallbackQueryHandler(handlers.tipo_visita_escolha)],
            handlers.TIPO_ATENDIMENTO: [CallbackQueryHandler(handlers.tipo_atendimento_escolha)],
            handlers.ORGAO_FIGURA_CARGO_ESCOLHA: [CallbackQueryHandler(handlers.figura_orgao_escolha)],
            handlers.ORGAO_PUBLICO_FOR_FIGURA_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.buscar_orgao_for_figura)],
            handlers.ORGAO_PUBLICO_FOR_FIGURA_PAGINACAO: [CallbackQueryHandler(handlers.orgao_paginacao_for_figura)],
            handlers.ORGAO_PUBLICO_FOR_FIGURA_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.orgao_manual_for_figura)],
            handlers.FIGURA_PUBLICA_FOR_FIGURA: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.figura_publica_input_for_figura)],
            handlers.CARGO_FOR_FIGURA: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.cargo_input_for_figura)],
            handlers.MAIS_FIGURAS_ORGAOS: [CallbackQueryHandler(handlers.salvar_figura_orgao_set)],
            handlers.ASSUNTO_INICIAL_ESCOLHA: [CallbackQueryHandler(handlers.assunto_inicial_escolha)],
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
        fallbacks=[CommandHandler("cancelar", cancelar)],
        allow_reentry=True,
    )
    return conv_handler


# Startup event do FastAPI - inicializa o bot e os handlers
@app.on_event("startup")
async def startup_event():
    global application, bot_just_started

    logger.info("FastAPI startup event triggered.")

    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("Erro: BOT_TOKEN não encontrado nas variáveis de ambiente ou no arquivo .env.")
        return

    application = ApplicationBuilder().token(token).build()

    # Handlers simples
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("salvar_onedrive", salvar_onedrive_telegram))
    application.add_handler(CommandHandler("setwebhook", set_webhook_command))

    # Handler de conversa (se o módulo handlers existir)
    if hasattr(handlers, "iniciar_colaborador"):
        application.add_handler(build_conversation_handler())
        logger.info("Handlers de conversação ativados.")
    else:
        logger.warning("Módulo 'handlers' ou função 'iniciar_colaborador' não encontrado. Handlers de conversação NÃO ativados.")

    await application.initialize()
    await application.start()
    logger.info("Telegram Application iniciado.")

    # Notificar admin (se variável existir)
    admin_telegram_id_str = os.getenv("ADMIN_TELEGRAM_ID")
    if admin_telegram_id_str:
        try:
            admin_telegram_id = int(admin_telegram_id_str)
            await application.bot.send_message(
                chat_id=admin_telegram_id,
                text="🚀 O bot foi iniciado/reiniciado com sucesso! (Notificação para o Admin)",
            )
            logger.info(f"Notificação de inicialização enviada para admin ID: {admin_telegram_id}")
        except Exception as e:
            logger.error(f"Erro ao enviar notificação para admin: {e}", exc_info=True)
    else:
        logger.warning("Variável ADMIN_TELEGRAM_ID não definida. Nenhuma notificação enviada.")

    bot_just_started = True


# Evento de shutdown do FastAPI - para o bot
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("FastAPI shutdown event triggered.")
    if application:
        await application.stop()
        logger.info("Telegram Application parado.")


# Endpoint para verificar se o bot está vivo
@app.get("/ping")
async def ping_endpoint():
    logger.info("Requisição GET recebida no endpoint /ping. Bot está ativo.")
    return {"status": "OK", "message": "Bot is alive!"}


# Execução local com Uvicorn
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Iniciando Uvicorn na porta {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
