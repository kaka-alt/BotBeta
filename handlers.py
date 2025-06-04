from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from datetime import datetime
import os
import csv
import logging # Adicionar import de logging
# Importe sua função de upload de fotos do exportar_para_excel.py
from exportar_para_excel import export_data_to_drive, upload_photo_to_drive 
# Importe seus outros módulos auxiliares
import config
import utils
from telegram.constants import ParseMode
from globals import user_data # Se você usa um arquivo globals.py para user_data

# Configuração de logging para handlers.py
logger = logging.getLogger(__name__)

# --- Definição dos Estados (CRÍTICO: Certifique-se de que estes estados estão definidos) ---
# Exemplo de como os estados podem ser definidos em handlers.py
# O número deve ser ajustado conforme a quantidade real de estados que você tem.
COLABORADOR, COLABORADOR_MANUAL, ORGAO_PUBLICO_KEYWORD, ORGAO_PUBLICO_PAGINACAO, ORGAO_PUBLICO_MANUAL, \
FIGURA_PUBLICA, CARGO, ASSUNTO_PALAVRA_CHAVE, ASSUNTO_PAGINACAO, ASSUNTO_MANUAL, \
MUNICIPIO, DATA, DATA_MANUAL, FOTO, DEMANDA_ESCOLHA, DEMANDA_DIGITAR, OV, PRO, \
OBSERVACAO_ESCOLHA, OBSERVACAO_DIGITAR, CONFIRMACAO_FINAL = range(21) 
# Se você tiver mais estados, ajuste o número do range.


# --- Início: Colaborador ---
async def iniciar_colaborador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [InlineKeyboardButton(name, callback_data=f"colaborador_{name}") for name in config.COLABORADORES]
    buttons.append(InlineKeyboardButton("Outro", callback_data="colaborador_outro"))
    keyboard = InlineKeyboardMarkup(utils.build_menu(buttons, n_cols=2))
    await update.message.reply_text("👨‍💼 Selecione o colaborador ou clique em Outro para digitar manualmente:", reply_markup=keyboard)
    return 'COLABORADOR' # Retorna o estado COLABORADOR

# Cria botoes para a paginação de colaboradores
async def colaborador_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "colaborador_outro":
        await query.message.reply_text("👨‍💼 Digite o nome do colaborador:")
        return 'COLABORADOR_MANUAL' # Retorna o estado COLABORADOR_MANUAL
    else:
        colaborador = data.replace("colaborador_", "")
        context.user_data['colaborador'] = colaborador
        await query.message.reply_text(f"Colaborador selecionado: {colaborador}")
        await query.message.reply_text("🏠 Agora, digite uma palavra-chave para buscar o órgão público:")
        return 'ORGAO_PUBLICO_KEYWORD' # Retorna o estado ORGAO_PUBLICO_KEYWORD

#função chamada quando o usuário digita manualmente o colaborador
async def colaborador_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()
    context.user_data['colaborador'] = nome
    await update.message.reply_text(f"Nome do colaborador registrado: {nome}")
    await update.message.reply_text("🏠 Agora, digite uma palavra-chave para buscar o órgão público:")
    return 'ORGAO_PUBLICO_KEYWORD' # Retorna o estado ORGAO_PUBLICO_KEYWORD


# --- Órgão público ---
async def buscar_orgao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.lower()
    orgaos = utils.ler_orgaos_csv()
    resultados = [o for o in orgaos if keyword in o.lower()]
    context.user_data['orgaos_busca'] = resultados
    context.user_data['orgao_pagina'] = 0

    if not resultados:
        await update.message.reply_text("❗ Nenhum órgão encontrado. Digite manualmente o nome do órgão público:")
        return 'ORGAO_PUBLICO_MANUAL' # Retorna o estado ORGAO_PUBLICO_MANUAL

    buttons, pagina_atual = utils.botoes_pagina(resultados, 0, prefix="orgao_")
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(f"Resultados encontrados : {len(resultados)}", reply_markup=keyboard)
    return 'ORGAO_PUBLICO_PAGINACAO' # Retorna o estado ORGAO_PUBLICO_PAGINACAO

#Função que controla as paginas de órgãos públicos
async def orgao_paginacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    pagina_atual = context.user_data.get("orgao_pagina", 0)
    resultados = context.user_data.get("orgaos_busca", [])

    if data == "orgao_proximo":
        pagina_atual += 1
        context.user_data["orgao_pagina"] = pagina_atual
        botoes, _ = utils.botoes_pagina(resultados, pagina_atual, prefix="orgao_")
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(botoes))
        return 'ORGAO_PUBLICO_PAGINACAO' # Retorna o estado ORGAO_PUBLICO_PAGINACAO

    elif data == "orgao_voltar":
        pagina_atual = max(0, pagina_atual - 1)
        context.user_data["orgao_pagina"] = pagina_atual
        botoes, _ = utils.botoes_pagina(resultados, pagina_atual, prefix="orgao_")
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(botoes))
        return 'ORGAO_PUBLICO_PAGINACAO' # Retorna o estado ORGAO_PUBLICO_PAGINACAO

    elif data == "orgao_inserir_manual":
        await query.message.reply_text("✍️ Digite manualmente o nome do órgão público:")
        return 'ORGAO_PUBLICO_MANUAL' # Retorna o estado ORGAO_PUBLICO_MANUAL

    elif data == "orgao_refazer_busca":
        await query.message.reply_text("🔎 Digite uma nova palavra-chave para buscar o órgão:")
        return 'ORGAO_PUBLICO_KEYWORD' # Retorna o estado ORGAO_PUBLICO_KEYWORD

    else:
        orgao_selecionado = data.replace("orgao_", "")
        context.user_data["orgao_publico"] = orgao_selecionado
        await query.message.reply_text(f"🏢 Órgão selecionado: {orgao_selecionado}")
        await query.message.reply_text("🧥 Digite o nome da figura pública:")
        return 'FIGURA_PUBLICA' # Retorna o estado FIGURA_PUBLICA

# Função chamada quando o usuário digita manualmente o órgão público
async def orgao_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()
    context.user_data['orgao_publico'] = nome
    utils.salvar_orgao(nome)  
    await update.message.reply_text(f"✔️ Órgão público registrado manualmente: {nome}")
    await update.message.reply_text("🧥 Digite o nome da figura pública:")
    return 'FIGURA_PUBLICA' # Retorna o estado FIGURA_PUBLICA


# --- Figura pública ---
async def figura_publica_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    figura_publica = update.message.text.strip()
    context.user_data['figura_publica'] = figura_publica
    await update.message.reply_text(f"✔️ Figura pública registrada: {figura_publica}.")
    await update.message.reply_text("🧥 Digite o Cargo:")
    return 'CARGO' # Retorna o estado CARGO


# --- Cargo ---
async def cargo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargo = update.message.text.strip()
    context.user_data['cargo'] = cargo
    await update.message.reply_text(f"✔️ Cargo registrado: {cargo}")
    await update.message.reply_text("✉️ Digite o Assunto:")
    return 'ASSUNTO_PALAVRA_CHAVE' # Retorna o estado ASSUNTO_PALAVRA_CHAVE


# --- Assunto ---
async def buscar_assunto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    palavra_chave = update.message.text.lower()
    assuntos = utils.ler_assuntos_csv()
    resultados = [a for a in assuntos if palavra_chave in a.lower()]
    context.user_data['assuntos_busca'] = resultados
    context.user_data['assunto_pagina'] = 0

    if not resultados:
        await update.message.reply_text("❗ Nenhum assunto encontrado. Digite manualmente o assunto:")
        return 'ASSUNTO_MANUAL' # Retorna o estado ASSUNTO_MANUAL

    buttons, pagina_atual = utils.botoes_pagina(resultados, 0, prefix="assunto_")
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(f"Resultados encontrados (página {pagina_atual + 1}):", reply_markup=keyboard)
    return 'ASSUNTO_PAGINACAO' # Retorna o estado ASSUNTO_PAGINACAO

# Função que controla as páginas de assuntos
async def assunto_paginacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    pagina_atual = context.user_data.get("assunto_pagina", 0)
    resultados = context.user_data.get("assuntos_busca", [])

    if data == "assunto_proximo":
        pagina_atual += 1
        context.user_data["assunto_pagina"] = pagina_atual
        botoes, _ = utils.botoes_pagina(resultados, pagina_atual, prefix="assunto_")
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(botoes))
        return 'ASSUNTO_PAGINACAO' # Retorna o estado ASSUNTO_PAGINACAO

    elif data == "assunto_voltar":
        pagina_atual = max(0, pagina_atual - 1)
        context.user_data["assunto_pagina"] = pagina_atual
        botoes, _ = utils.botoes_pagina(resultados, pagina_atual, prefix="assunto_")
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(botoes))
        return 'ASSUNTO_PAGINACAO' # Retorna o estado ASSUNTO_PAGINACAO

    elif data == "assunto_inserir_manual":
        await query.message.reply_text("✍️ Digite manualmente o nome do assunto:")
        return 'ASSUNTO_MANUAL'  # Retorna o estado ASSUNTO_MANUAL

    elif data == "assunto_refazer_busca":
        await query.message.reply_text("🔎 Digite uma nova palavra-chave para buscar o assunto:")
        return 'ASSUNTO_PALAVRA_CHAVE' # Retorna o estado ASSUNTO_PALAVRA_CHAVE

    else:
        assunto_selecionado = data.replace("assunto_", "")
        context.user_data["assunto"] = assunto_selecionado
        await query.message.reply_text(f"📌 Assunto selecionado: {assunto_selecionado}")
        await query.message.reply_text("🏙️ Digite o município:")
        return 'MUNICIPIO' # Retorna o estado MUNICIPIO

async def assunto_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assunto = update.message.text.strip()
    context.user_data['assunto'] = assunto
    utils.salvar_assunto(assunto) 
    await update.message.reply_text(f"✔️ Assunto registrado: {assunto}")
    await update.message.reply_text("🏙️ Digite o município:")
    return 'MUNICIPIO' # Retorna o estado MUNICIPIO


# --- Município ---
async def municipio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['municipio'] = update.message.text.strip()
    return await solicitar_data(update, context)


# --- Data ---
async def solicitar_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        InlineKeyboardButton("📅 Usar data/hora atual", callback_data="data_hoje"),
        InlineKeyboardButton("✏️ Digitar data manualmente", callback_data="data_manual"),
    ]
    keyboard = InlineKeyboardMarkup.from_row(buttons)

    if update.message:
        await update.message.reply_text("Selecione uma opção para a data:", reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.reply_text("Selecione uma opção para a data:", reply_markup=keyboard)

    return 'DATA' # Retorna o estado DATA

async def data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "data_hoje":
            dt = datetime.now()
            context.user_data['data'] = dt.strftime("%Y-%m-%d")
            await query.message.edit_text(f"✔️ Data registrada: {dt.strftime('%Y/%m/%d')}")
            await query.message.reply_text("📷 Por favor, envie a foto:")
            return 'FOTO' # Retorna o estado FOTO

        elif query.data == "data_manual":
            await query.message.edit_text("Digite a data no formato AAAA/MM/DD:")
            return 'DATA_MANUAL' # Retorna o estado DATA_MANUAL

    else: # Se a entrada for um texto (data manual)
        texto = update.message.text.strip()
        try:
            dt = datetime.strptime(texto, "%Y/%m/%d")
            context.user_data['data'] = dt.strftime("%Y-%m-%d")
            await update.message.reply_text("✔️ Data registrada com sucesso.")
            await update.message.reply_text("📷 Por favor, envie a foto:")
            return FOTO # Retorna o estado FOTO
        except ValueError:
            await update.message.reply_text("❗ Formato inválido. Digite a data no formato AAAA/MM/DD:") # Corrigido para AAAA/MM/DD
            return 'DATA_MANUAL' # Retorna o estado DATA_MANUAL


# --- Foto ---
async def foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❗ Por favor, envie uma foto válida.")
        return 'FOTO' # Retorna o estado FOTO

    photo = update.message.photo[-1] # Pega a maior resolução da foto
    
    # Obtém o objeto File do Telegram
    telegram_file = await context.bot.get_file(photo.file_id)

    # Baixa o conteúdo da foto em bytes
    # Usaremos download_as_bytearray() para obter os bytes diretamente na memória
    photo_bytes = await telegram_file.download_as_bytearray()

    # Gera um nome de arquivo único para a foto no Drive
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Para o nome da foto, podemos usar o ID do usuário + timestamp para garantir unicidade
    user_id = update.effective_user.id
    filename = f"foto_{user_id}_{timestamp}.jpg" # Assumindo JPG, Telegram converte para JPG/PNG

    # --- NOVO: Faz o upload da foto para o Google Drive ---
    logger.info(f"Tentando fazer upload da foto {filename} para o Google Drive.")
    drive_file_id = await upload_photo_to_drive(bytes(photo_bytes), filename) # Converte bytearray para bytes
    
    if drive_file_id:
        context.user_data["foto"] = drive_file_id # Salva o ID do arquivo no Drive
        logger.info(f"Foto salva no Google Drive. ID: {drive_file_id}")
        await update.message.reply_text("✔️ Foto recebida e enviada para o Google Drive.")
    else:
        context.user_data["foto"] = "Erro no upload" # Indica falha no upload
        logger.error("Falha ao enviar foto para o Google Drive.")
        await update.message.reply_text("❗ Ocorreu um erro ao enviar a foto para o Google Drive. Por favor, tente novamente.")
        return 'FOTO' # Permanece no estado FOTO para nova tentativa

    context.user_data["demandas"] = [] # Inicializa a lista de demandas

    # Botões para próxima etapa
    buttons = [
        [InlineKeyboardButton("➕ Adicionar demanda", callback_data="add_demanda")],
        [InlineKeyboardButton("❌ Não adicionar demanda", callback_data="fim_demandas")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text("Quer adicionar uma demanda?", reply_markup=reply_markup)
    return 'DEMANDA_ESCOLHA' # Retorna o estado DEMANDA_ESCOLHA

# --- Demanda ---
async def demanda(update, context):
    query = update.callback_query
    await query.answer()
    
    data = query.data

    if data == "add_demanda":
        await query.edit_message_text("Por favor, digite a demanda:")
        return 'DEMANDA_DIGITAR' # Retorna o estado DEMANDA_DIGITAR

    elif data == "fim_demandas":
        await query.edit_message_text("Finalizando demandas. Vamos para o resumo...")
        return await resumo(update, context) # Chama resumo e retorna seu estado

    elif data == "pular_demanda": # Este callback_data não estava sendo usado antes, mas se for, aqui está a lógica
        await query.edit_message_text("Você optou por pular as demandas.")
        return await resumo(update, context) # Chama resumo e retorna seu estado


# Receber texto da demanda
async def demanda_digitar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nova_demanda"]= {
        "texto": update.message.text
    }
    await update.message.reply_text("Informe o número do OV:")
    return 'OV'  # Retorna o estado OV

# Receber OV
async def ov(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nova_demanda"]["ov"] = update.message.text
    await update.message.reply_text("Informe o número do PRO:")
    return 'PRO'  # Retorna o estado PRO

# Receber PRO
async def pro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nova_demanda"]["pro"] = update.message.text

    keyboard = [
        [InlineKeyboardButton("Adicionar observação", callback_data="add_obs")],
        [InlineKeyboardButton("Pular", callback_data="skip_obs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Deseja adicionar uma observação?", reply_markup=reply_markup)
    return 'OBSERVACAO_ESCOLHA'  # Retorna o estado OBSERVACAO_ESCOLHA

# Escolha de observação
async def observacao_escolha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_obs":
        await query.message.reply_text("Digite a observação:")
        return 'OBSERVACAO_DIGITAR'  # Retorna o estado OBSERVACAO_DIGITAR
    else:
        context.user_data["nova_demanda"]["observacao"] = ""
        return await salvar_demanda(update, context)

# Digitação da observação
async def observacao_digitar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nova_demanda"]["observacao"] = update.message.text
    return await salvar_demanda(update, context)

# Salvar a demanda no dicionário principal
async def salvar_demanda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    demanda = context.user_data.pop("nova_demanda", None)
    if demanda:
        context.user_data.setdefault("demandas", []).append(demanda)

    buttons = [
        [InlineKeyboardButton("➕ Adicionar outra demanda", callback_data="add_demanda")],
        [InlineKeyboardButton("✅ Finalizar", callback_data="fim_demandas")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "✅ Demanda adicionada com sucesso! Deseja adicionar outra?",
            reply_markup=reply_markup
        )
    else: # Se a chamada vier de um MessageHandler (ex: observacao_digitar)
        await update.message.reply_text(
            "✅ Demanda adicionada com sucesso! Deseja adicionar outra?",
            reply_markup=reply_markup
        )
    return 'DEMANDA_ESCOLHA'  # Retorna o estado DEMANDA_ESCOLHA


# Lidar com escolha de mais demandas
async def mais_demandas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add_demanda":
        await query.message.reply_text("Digite a próxima demanda:")
        return 'DEMANDA_DIGITAR'  # Retorna o estado DEMANDA_DIGITAR
    else:
        return await resumo(update, context) # Chama resumo e retorna seu estado
    

async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verifica se a chamada veio de um CallbackQuery ou Message (para resposta)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message_to_edit = query.message
    elif update.message: # Se for chamado de um MessageHandler
        message_to_edit = update.message
    else:
        logger.error("Resumo chamado sem update.message ou update.callback_query")
        return ConversationHandler.END # Ou um estado de erro

    dados = context.user_data

    # A foto agora é o ID do Drive, não o caminho local.
    # Você pode construir um link para visualização se quiser, mas por enquanto, apenas o ID.
    foto_info = dados.get('foto', 'N/A')
    if foto_info != 'N/A' and foto_info != 'Erro no upload':
        # Se quiser um link direto para o Google Drive, precisaria de permissões mais abertas
        # ou um link de compartilhamento específico. Por enquanto, apenas o ID.
        foto_display = f"ID no Drive: <code>{foto_info}</code>"
    else:
        foto_display = foto_info

    resumo_texto = (
        f"<b>Resumo dos dados coletados:</b>\n"
        f"👤 <b>Colaborador:</b> {dados.get('colaborador', 'N/A')}\n"
        f"🏢 <b>Órgão Público:</b> {dados.get('orgao_publico', 'N/A')}\n"
        f"🧑‍💼 <b>Figura Pública:</b> {dados.get('figura_publica', 'N/A')}\n"
        f"💼 <b>Cargo:</b> {dados.get('cargo', 'N/A')}\n"
        f"📌 <b>Assunto:</b> {dados.get('assunto', 'N/A')}\n"
        f"🌍 <b>Município:</b> {dados.get('municipio', 'N/A')}\n"
        f"📅 <b>Data:</b> {dados.get('data', 'N/A')}\n"
        f"📷 <b>Foto:</b> {foto_display}\n\n" # Atualizado para mostrar o ID do Drive
        f"<b>Demandas:</b>\n"
    )

    demandas = dados.get("demandas", [])
    if demandas:
        for i, d in enumerate(demandas, 1):
            resumo_texto += (
                f"{i}. {d.get('texto', '')}\n"
                f"   OV: {d.get('ov', '')} | PRO: {d.get('pro', '')}\n"
                f"   Obs: {d.get('observacao', '')}\n"
            )
    else:
        resumo_texto += "Nenhuma demanda registrada.\n"

    buttons = [
        [InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_salvar")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_resumo")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await message_to_edit.reply_text( # Usar reply_text em vez de edit_message_text para novas mensagens
        resumo_texto,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

    return CONFIRMACAO_FINAL # Retorna o estado CONFIRMACAO_FINAL


# --- Confirmar ---
async def confirmacao(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "confirmar_salvar":
        utils.salvar_no_banco(context.user_data) # Certifique-se de que esta função salva o ID da foto no Drive
        export_data_to_drive() # Esta função deve lidar com os CSVs
        await query.edit_message_text("✅ Dados salvos com sucesso no banco de dados e Google Drive! Obrigado pelo registro.")
        context.user_data.clear()
        return ConversationHandler.END

    elif data == "cancelar_resumo":
        await query.edit_message_text("❌ Operação cancelada no resumo. Os dados não foram salvos.")
        context.user_data.clear()
        return ConversationHandler.END
    
# --- Cancelar ---
# Esta função 'cancelar' já existe no topo do arquivo, então esta é uma duplicata.
# Certifique-se de que você está usando apenas uma versão da função 'cancelar'
# e que ela é o fallback do ConversationHandler.
# async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("Operação cancelada. Use /iniciar para reiniciar.")
#     context.user_data.clear()
#     return ConversationHandler.END
