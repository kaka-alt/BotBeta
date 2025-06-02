import logging
import os
import threading
from dotenv import load_dotenv

from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
import handlers
# A importação abaixo é uma má prática. Preferimos importar funções específicas.
# from handlers import * # Importa todas as funções do handlers.py para serem diretamente acessíveis

from fastapi import FastAPI
import uvicorn

# --- Configuração do carregamento do arquivo .env (rail.env) ---
# Este bloco garante que as variáveis de ambiente sejam carregadas corretamente
# quando você roda o script localmente. No Railway, elas já serão injetadas.
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, 'rail.env')  # Caminho para o seu arquivo de variáveis locais
load_dotenv(dotenv_path=dotenv_path)  # Carrega as variáveis do rail.env

# Importa a função principal de exportação do seu arquivo exportar_para_excel.py
# O nome da função foi corrigido para 'exportar_dados_localmente'.
from exportar_para_excel import exportar_dados_localmente

# Configuração básica de logging para ver as mensagens no console/logs do Railway
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Funções do Bot do Telegram ---
async def cancelar(update, context):
    """Cancela a operação atual do usuário e limpa os dados da conversa."""
    await update.message.reply_text("Operação cancelada pelo usuário.")
    context.user_data.clear()
    return ConversationHandler.END

async def start(update, context):
    """Comando /start para iniciar a interação com o bot."""
    await update.message.reply_text("Olá! Use /iniciar para começar o registro de uma ocorrência.")

def iniciar_fastapi():
    """Função para iniciar o servidor FastAPI em uma thread separada."""
    # O Railway define a porta em uma variável de ambiente 'PORT'.
    # Usamos os.getenv("PORT", 8000) para pegar a porta do Railway ou usar 8000 como padrão localmente.
    port = int(os.getenv("PORT", 8000))
    print(f"Iniciando FastAPI na porta: {port}")
    # uvicorn.run bloqueia a thread, por isso rodamos em uma thread separada
    uvicorn.run(app, host="0.0.0.0", port=port)

def iniciar_bot():
    """Função para configurar e iniciar o bot do Telegram."""
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("Erro: BOT_TOKEN não encontrado nas variáveis de ambiente ou no arquivo .env.")
        print("Certifique-se de que a variável BOT_TOKEN está configurada no Railway ou no rail.env local.")
        return

    application = ApplicationBuilder().token(token).build()

    # Define o fluxo de conversação do bot usando ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('iniciar', handlers.iniciar_colaborador)],
        states={
            # Mapeamento dos estados do bot para as funções handlers correspondentes
            "COLABORADOR": [CallbackQueryHandler(handlers.colaborador_button, pattern="^colaborador_")],
            "COLABORADOR_MANUAL": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.colaborador_manual)],
            "ORGAO_PUBLICO_KEYWORD": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.buscar_orgao)],
            "ORGAO_PUBLICO_PAGINACAO": [CallbackQueryHandler(handlers.orgao_paginacao, pattern="^orgao_")],
            "ORGAO_PUBLICO_MANUAL": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.orgao_manual)],
            "FIGURA_PUBLICA": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.figura_publica_input)],
            "CARGO": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.cargo)],
            "ASSUNTO_PALAVRA_CHAVE": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.buscar_assunto)],
            "ASSUNTO_PAGINACAO": [CallbackQueryHandler(handlers.assunto_paginacao, pattern="^assunto_")],
            "ASSUNTO_MANUAL": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.assunto_manual)],
            "MUNICIPIO": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.municipio)],
            "DATA": [
                CallbackQueryHandler(handlers.data, pattern="^data_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.data),
            ],
            "DATA_MANUAL": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.data)],
            "FOTO": [MessageHandler(filters.PHOTO, handlers.foto)],
            "DEMANDA_ESCOLHA": [CallbackQueryHandler(handlers.demanda, pattern="^(add_demanda|pular_demanda|fim_demandas)$")],
            # Garanta que estas funções (demanda_digitar, ov, pro, observacao_escolha, observacao_digitar)
            # estão definidas no seu arquivo handlers.py e são importadas corretamente.
            "DEMANDA_DIGITAR": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.demanda_digitar)],
            "OV": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.ov)],
            "PRO": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.pro)],
            "OBSERVACAO_ESCOLHA": [CallbackQueryHandler(handlers.observacao_escolha, pattern="^(add_obs|skip_obs)$")],
            "OBSERVACAO_DIGITAR": [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.observacao_digitar)],
            "CONFIRMACAO_FINAL": [CallbackQueryHandler(handlers.confirmacao, pattern="^(confirmar_salvar|cancelar_resumo)$")],
        },
        fallbacks=[CommandHandler('cancelar', cancelar)],  # Permite cancelar a conversa a qualquer momento
    )

    # Adiciona os handlers ao aplicativo do bot
    application.add_handler(CommandHandler('start', start))
    application.add_handler(conv_handler)

    # NOVO HANDLER PARA SALVAR NO ONEDRIVE (ADICIONADO AQUI)
    application.add_handler(CommandHandler('salvar_onedrive', salvar_onedrive_telegram))

    # Inicia o polling do bot para receber e processar atualizações do Telegram
    application.run_polling()

# --- Configuração e Endpoint do FastAPI ---
app = FastAPI()

@app.get("/export")
def exportar():
    """
    Endpoint FastAPI que é acionado para iniciar o processo de backup para o Google Drive.
    Este endpoint será chamado por um Cron Job configurado no Railway.
    """
    print("Endpoint /export acionado. Iniciando backup para Google Drive...")
    try:
        # Chama a função principal de backup do exportar_para_excel.py
        # Essa função se encarrega de ler do banco, gerar Excel e enviar para o Google Drive.
        exportar_dados_localmente() # Chamada corrigida
        print("Processo de backup para Google Drive concluído (via endpoint /export).")
        return {"status": "Exportação para Google Drive iniciada com sucesso."}
    except Exception as e:
        print(f"Erro ao iniciar exportação via endpoint: {e}")
        # Loga a exceção completa para facilitar a depuração no Railway
        logging.exception("Erro durante a execução do backup via endpoint /export")
        return {"status": "Erro ao iniciar exportação.", "detalhes": str(e)}, 500

# NOVO HANDLER PARA O COMANDO /SALVAR_ONEDRIVE (ADICIONADO AQUI)
async def salvar_onedrive_telegram(update, context):
    """
    Handler para o comando /salvar_onedrive no Telegram.
    Aciona a exportação das tabelas 'registros' e 'demandas' para o Google Drive.
    (O nome do comando ainda é OneDrive, mas a funcionalidade é Google Drive)
    """
    logging.info(f"Comando /salvar_onedrive recebido de {update.effective_user.id}")
    await update.message.reply_text("Iniciando a exportação dos dados para o Google Drive. Isso pode levar um momento...")

    try:
        # Chama a função principal de backup do exportar_para_excel.py
        # Essa função se encarrega de ler do banco, gerar Excel e enviar para o Google Drive.
        exportar_dados_localmente() # Chamada corrigida
        await update.message.reply_text("Dados salvos no Google Drive com sucesso!")
    except Exception as e:
        logging.error(f"Erro ao salvar dados no Google Drive via Telegram: {e}")
        await update.message.reply_text(f"Falha ao salvar os dados no Google Drive: {e}")


# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    # Inicia o servidor FastAPI em uma thread separada em segundo plano.
    # `daemon=True` garante que a thread do FastAPI será encerrada se o programa principal (bot) terminar.
    threading.Thread(target=iniciar_fastapi, daemon=True).start()

    # Inicia o bot do Telegram na thread principal.
    # run_polling() do python-telegram-bot precisa rodar na thread principal para lidar
    # corretamente com sinais do sistema (como Ctrl+C para encerrar o programa).
    print("Iniciando bot do Telegram...")
    iniciar_bot()