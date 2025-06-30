from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from datetime import datetime
import os
import csv
import logging 
from telegram.constants import ParseMode 
from google.oauth2.service_account import Credentials



# Importa as funções que interagem com o Google Drive, como upload de fotos e exportação de dados Excel.
from exportar_para_excel import export_data_to_drive, upload_photo_to_drive 

# Importa módulos de suporte para configurações (config), utilidades (utils) e dados globais (globals).
import config 
import utils  
from globals import user_data 

# Configura o logger para este arquivo, útil para acompanhar o que está acontecendo no Render.
logger = logging.getLogger(__name__)

# --- Definição dos Estados da Nossa Conversa ---
# Ajustei o range() para incluir os novos estados para o loop de figuras/órgãos
COLABORADOR, COLABORADOR_MANUAL, TIPO_VISITA, \
ORGAO_FIGURA_CARGO_ESCOLHA, ORGAO_PUBLICO_FOR_FIGURA_KEYWORD, ORGAO_PUBLICO_FOR_FIGURA_PAGINACAO, ORGAO_PUBLICO_FOR_FIGURA_MANUAL, \
FIGURA_PUBLICA_FOR_FIGURA, CARGO_FOR_FIGURA, MAIS_FIGURAS_ORGAOS, \
ASSUNTO_INICIAL_ESCOLHA, ASSUNTO_PALAVRA_CHAVE, ASSUNTO_PAGINACAO, ASSUNTO_MANUAL, \
MUNICIPIO, DATA, DATA_MANUAL, FOTO, DEMANDA_ESCOLHA, DEMANDA_DIGITAR, OV, PRO, \
OBSERVACAO_ESCOLHA, OBSERVACAO_DIGITAR, CONFIRMACAO_FINAL, TIPO_ATENDIMENTO = range(26) # AJUSTADO: range(26) para os novos estados


# --- Início do Nosso Registro: Seleção do Colaborador ---
async def iniciar_colaborador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [InlineKeyboardButton(name, callback_data=f"colaborador_{name}") for name in config.COLABORADORES]
    buttons.append(InlineKeyboardButton("Outro", callback_data="colaborador_outro"))
    keyboard = InlineKeyboardMarkup(utils.build_menu(buttons, n_cols=2))
    await update.message.reply_text(
        "👋 Olá! Vamos começar o registro da ocorrência.\nPor favor, selecione o <b>colaborador</b> na lista ou clique em 'Outro' para digitar manualmente:", 
        reply_markup=keyboard, 
        parse_mode=ParseMode.HTML 
    )
    return COLABORADOR

# Lida com a escolha do colaborador via botão ou a opção "Outro".
async def colaborador_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query 
    await query.answer() 
    data = query.data 

    if data == "colaborador_outro":
        await query.message.reply_text("✍️ Entendido! Por favor, digite o <b>nome completo do colaborador</b>:")
        return COLABORADOR_MANUAL 
    else:
        colaborador = data.replace("colaborador_", "") 
        context.user_data['colaborador'] = colaborador 
        await query.message.edit_text(f"✅ Colaborador selecionado: <b>{colaborador}</b>.", parse_mode=ParseMode.HTML) 
        # Transição para o estado de TIPO_VISITA
        return await solicitar_tipo_visita(update, context) 

# Lida com a entrada manual do nome do colaborador.
async def colaborador_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip() 
    context.user_data['colaborador'] = nome 
    await update.message.reply_text(f"✅ Colaborador registrado: <b>{nome}</b>.", parse_mode=ParseMode.HTML)
    # Transição para o estado de TIPO_VISITA
    return await solicitar_tipo_visita(update, context) 


# --- Etapa: Tipo de Visita ---
async def solicitar_tipo_visita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        InlineKeyboardButton("🔄 Reativa", callback_data="tipo_visita_reativo"),
        InlineKeyboardButton("🎯 Proativa", callback_data="tipo_visita_proativo"),
    ]
    keyboard = InlineKeyboardMarkup.from_row(buttons)

    if update.message:
        await update.message.reply_text("🤝 Excelente! Agora, por favor, selecione o <b>tipo da visita</b> realizada:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.message.reply_text("🤝 Excelente! Agora, por favor, selecione o <b>tipo da visita</b> realizada:", reply_markup=keyboard, parse_mode=ParseMode.HTML)

    return TIPO_VISITA 

async def tipo_visita_escolha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    tipo_visita = data.replace("tipo_visita_", "") 
    context.user_data['tipo_visita'] = tipo_visita.upper() 

    await query.message.edit_text(f"✅ Tipo de visita selecionado: <b>{tipo_visita.capitalize()}</b>.", parse_mode=ParseMode.HTML)
    # NOVO FLUXO: Após o tipo de visita, pergunta se quer adicionar figura pública/órgão
    return await solicitar_tipo_atendimento(update, context)

#ATENDIMENTO!!!!
async def solicitar_tipo_atendimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("⚡ PRESENCIAL - EDP", callback_data="tipo_atendimento_presencial - edp")],
        [InlineKeyboardButton("🗺️ PRESENCIAL - EXTERNO", callback_data="tipo_atendimento_presencial - externo")],
        [InlineKeyboardButton("💻 VIRTUAL", callback_data="tipo_atendimento_virtual")],
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    if update.message:
        await update.message.reply_text("🤝 Excelente! Agora, por favor, selecione o <b>tipo de atendimento</b> realizado:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.message.reply_text("🤝 Excelente! Agora, por favor, selecione o <b>tipo de atendimento</b> realizado:", reply_markup=keyboard, parse_mode=ParseMode.HTML)

    return TIPO_ATENDIMENTO

async def tipo_atendimento_escolha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    tipo_atendimento = data.replace("tipo_atendimento_", "")
    context.user_data['tipo_atendimento'] = tipo_atendimento.upper()

    await query.message.edit_text(f"✅ Tipo de atendimento selecionado: <b>{tipo_atendimento.capitalize()}</b>.", parse_mode=ParseMode.HTML)
    # NOVO FLUXO: Após o tipo de atendimento, pergunta se quer adicionar figura pública/órgão
    context.user_data["figuras_orgaos"] = [] # Inicializa a lista de figuras/órgãos
    return await solicitar_figura_orgao_inicial(update, context)



# --- NOVO FLUXO: Múltiplas Figuras Públicas/Órgãos ---

# Pergunta se o usuário quer adicionar uma figura pública e órgão
async def solicitar_figura_orgao_inicial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("➕ Adicionar Figura/Órgão", callback_data="add_figura_orgao")],
        [InlineKeyboardButton("⏭️ Pular Figuras/Órgãos", callback_data="fim_figuras_orgaos")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    # Verifica se a chamada veio de uma mensagem ou de um callback_query
    if update.callback_query:
        await update.callback_query.message.reply_text(
            "🧑‍🤝‍🏢 Deseja adicionar uma <b>Figura Pública</b> e o <b>Órgão</b> relacionado a esta ocorrência?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    elif update.message:
         await update.message.reply_text(
            "🧑‍🤝‍🏢 Deseja adicionar uma <b>Figura Pública</b> e o <b>Órgão</b> relacionado a esta ocorrência?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    return ORGAO_FIGURA_CARGO_ESCOLHA # Novo estado para escolha inicial

# Lida com a escolha inicial de adicionar figura pública/órgão
async def figura_orgao_escolha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_figura_orgao":
        await query.edit_message_text("🏠 Ok! Digite uma <b>palavra-chave</b> para buscar o <b>órgão público</b> desta figura:", parse_mode=ParseMode.HTML)
        return ORGAO_PUBLICO_FOR_FIGURA_KEYWORD # Inicia o sub-fluxo para coletar Figura/Órgão
    elif data == "fim_figuras_orgaos":
        await query.edit_message_text("✅ Ok, finalizando a adição de Figuras e Órgãos.")
        # FLUXO CORRIGIDO: Após finalizar figuras/órgãos, segue para Assunto
        return await solicitar_assunto_inicial(update, context)

# --- Sub-fluxo para coletar Órgão Público (DENTRO do loop de figuras) ---
async def buscar_orgao_for_figura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.lower()
    orgaos = utils.ler_orgaos_csv()
    resultados = [o for o in orgaos if keyword in o.lower()]
    context.user_data['temp_orgaos_busca_for_figura'] = resultados # Usa uma temp var para este sub-fluxo
    context.user_data['temp_orgao_pagina_for_figura'] = 0

    if not resultados:
        await update.message.reply_text("❗ Nenhum órgão encontrado. Digite manualmente o nome do <b>órgão público</b> para esta figura:", parse_mode=ParseMode.HTML)
        return ORGAO_PUBLICO_FOR_FIGURA_MANUAL

    buttons, pagina_atual = utils.botoes_pagina(resultados, 0, prefix="orgao_figura_") # Prefixo diferente
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(f"Resultados encontrados : {len(resultados)}", reply_markup=keyboard)
    return ORGAO_PUBLICO_FOR_FIGURA_PAGINACAO

async def orgao_paginacao_for_figura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    pagina_atual = context.user_data.get("temp_orgao_pagina_for_figura", 0)
    resultados = context.user_data.get("temp_orgaos_busca_for_figura", [])

    if data == "orgao_figura_proximo":
        pagina_atual += 1
        context.user_data["temp_orgao_pagina_for_figura"] = pagina_atual
        botoes, _ = utils.botoes_pagina(resultados, pagina_atual, prefix="orgao_figura_")
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(botoes))
        return ORGAO_PUBLICO_FOR_FIGURA_PAGINACAO

    elif data == "orgao_figura_voltar":
        pagina_atual = max(0, pagina_atual - 1)
        context.user_data["temp_orgao_pagina_for_figura"] = pagina_atual
        botoes, _ = utils.botoes_pagina(resultados, pagina_atual, prefix="orgao_figura_")
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(botoes))
        return ORGAO_PUBLICO_FOR_FIGURA_PAGINACAO

    elif data == "orgao_figura_inserir_manual":
        await query.message.reply_text("✍️ Digite manualmente o nome do <b>órgão público</b> para esta figura:", parse_mode=ParseMode.HTML)
        return ORGAO_PUBLICO_FOR_FIGURA_MANUAL

    elif data == "orgao_figura_refazer_busca":
        await query.message.reply_text("🔎 Digite uma nova palavra-chave para buscar o órgão desta figura:", parse_mode=ParseMode.HTML)
        return ORGAO_PUBLICO_FOR_FIGURA_KEYWORD

    else:
        orgao_selecionado = data.replace("orgao_figura_", "")
        context.user_data["nova_figura_orgao"] = {"orgao_publico": orgao_selecionado} # Inicia o objeto temporário
        await query.message.edit_text(f"🏢 Órgão selecionado: <b>{orgao_selecionado}</b>.", parse_mode=ParseMode.HTML)
        await query.message.reply_text("🧑‍💼 Ótimo! Agora, digite o <b>nome completo da figura pública</b>:", parse_mode=ParseMode.HTML)
        return FIGURA_PUBLICA_FOR_FIGURA # Próximo passo no sub-fluxo

async def orgao_manual_for_figura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()
    context.user_data["nova_figura_orgao"] = {"orgao_publico": nome} # Inicia o objeto temporário
    utils.salvar_orgao(nome)
    await update.message.reply_text(f"✔️ Órgão público registrado manualmente: <b>{nome}</b>.", parse_mode=ParseMode.HTML)
    await update.message.reply_text("🧑‍💼 Ótimo! Agora, digite o <b>nome completo da figura pública</b>:", parse_mode=ParseMode.HTML)
    return FIGURA_PUBLICA_FOR_FIGURA

# Coleta Figura Pública (dentro do loop)
async def figura_publica_input_for_figura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    figura_publica = update.message.text.strip()
    context.user_data["nova_figura_orgao"]["figura_publica"] = figura_publica
    await update.message.reply_text(f"✅ Figura pública registrada: <b>{figura_publica}</b>.", parse_mode=ParseMode.HTML)
    await update.message.reply_text("💼 Qual é o <b>Cargo</b> desta figura pública?", parse_mode=ParseMode.HTML)
    return CARGO_FOR_FIGURA

# Coleta Cargo (dentro do loop)
async def cargo_input_for_figura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargo = update.message.text.strip()
    context.user_data["nova_figura_orgao"]["cargo"] = cargo
    await update.message.reply_text(f"✅ Cargo registrado: <b>{cargo}</b>.", parse_mode=ParseMode.HTML)
    
    # Salva o conjunto completo (órgão, figura, cargo) e pergunta se quer adicionar mais
    return await salvar_figura_orgao_set(update, context)

async def salvar_figura_orgao_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fig_org_set = context.user_data.pop("nova_figura_orgao", None)
    if fig_org_set:
        context.user_data.setdefault("figuras_orgaos", []).append(fig_org_set)

    buttons = [
        [InlineKeyboardButton("➕ Adicionar outra Figura/Órgão", callback_data="add_figura_orgao")],
        [InlineKeyboardButton("✅ Finalizar Figuras/Órgãos", callback_data="fim_figuras_orgaos")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    # Responde à mensagem ou edita a query.
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "✅ Figura/Órgão adicionado(a) com sucesso! Deseja adicionar outro(a)?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else: # Se a chamada veio de um MessageHandler (ex: cargo_input_for_figura)
        await update.message.reply_text(
            "✅ Figura/Órgão adicionado(a) com sucesso! Deseja adicionar outro(a)?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    return ORGAO_FIGURA_CARGO_ESCOLHA # Volta para a escolha inicial do loop

# --- FIM NOVO FLUXO: Múltiplas Figuras Públicas/Órgãos ---


# --- Etapa: Assunto (Menu Inicial e Busca) ---
async def solicitar_assunto_inicial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [InlineKeyboardButton(assunto, callback_data=f"assunto_pre_{assunto}") for assunto in config.PREDEFINED_ASSUNTOS]
    buttons.append(InlineKeyboardButton("Outro (digitar ou buscar)", callback_data="assunto_outro"))
    keyboard = InlineKeyboardMarkup(utils.build_menu(buttons, n_cols=2)) 

    if update.message:
        await update.message.reply_text("✉️ Por favor, selecione o <b>assunto</b> da ocorrência nas opções abaixo:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.message.reply_text("✉️ Por favor, selecione o <b>assunto</b> da ocorrência nas opções abaixo:", reply_markup=keyboard, parse_mode=ParseMode.HTML)

    return ASSUNTO_INICIAL_ESCOLHA # Novo estado para lidar com a escolha inicial

async def assunto_inicial_escolha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "assunto_outro":
        await query.message.edit_text("✍️ Entendido. Por favor, digite uma <b>palavra-chave</b> para buscar ou o <b>assunto completo</b> que deseja registrar:", parse_mode=ParseMode.HTML)
        return ASSUNTO_PALAVRA_CHAVE 
    else:
        assunto_selecionado = data.replace("assunto_pre_", "")
        context.user_data["assunto"] = assunto_selecionado
        await query.message.edit_text(f"✅ Assunto selecionado: <b>{assunto_selecionado}</b>.", parse_mode=ParseMode.HTML)
        await query.message.reply_text("🏙️ Quase lá! Em qual <b>município</b> a ocorrência aconteceu?", parse_mode=ParseMode.HTML)
        return MUNICIPIO 


# --- Etapa: Assunto (Lógica de Busca/Paginação Existente) ---
async def buscar_assunto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    palavra_chave = update.message.text.lower()
    assuntos = utils.ler_assuntos_csv() 
    resultados = [a for a in assuntos if palavra_chave in a.lower()]
    context.user_data['assuntos_busca'] = resultados
    context.user_data['assunto_pagina'] = 0

    if not resultados:
        await update.message.reply_text("❗ Nenhum assunto encontrado com essa palavra-chave. Por favor, digite <b>manualmente o assunto completo</b>:", parse_mode=ParseMode.HTML)
        return ASSUNTO_MANUAL
    
    buttons, pagina_atual = utils.botoes_pagina(resultados, 0, prefix="assunto_")
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(f"🔎 Encontrei <b>{len(resultados)} resultados</b> para '<i>{palavra_chave}</i>'. Selecione abaixo ou navegue nas opções:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return ASSUNTO_PAGINACAO

# Lida com a navegação na lista de assuntos e a seleção.
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
        return ASSUNTO_PAGINACAO

    elif data == "assunto_voltar":
        pagina_atual = max(0, pagina_atual - 1)
        context.user_data["assunto_pagina"] = pagina_atual
        botoes, _ = utils.botoes_pagina(resultados, pagina_atual, prefix="assunto_")
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(botoes))
        return ASSUNTO_PAGINACAO

    elif data == "assunto_inserir_manual":
        await query.message.reply_text("✍️ Certo. Por favor, digite <b>manualmente o assunto completo</b>:", parse_mode=ParseMode.HTML)
        return ASSUNTO_MANUAL

    elif data == "assunto_refazer_busca":
        await query.message.reply_text("🔄 Ok, vamos refazer a busca. Digite uma nova <b>palavra-chave</b> para o assunto:", parse_mode=ParseMode.HTML)
        return ASSUNTO_PALAVRA_CHAVE

    else:
        assunto_selecionado = data.replace("assunto_", "")
        context.user_data["assunto"] = assunto_selecionado
        await query.message.edit_text(f"✅ Assunto selecionado: <b>{assunto_selecionado}</b>.", parse_mode=ParseMode.HTML)
        await query.message.reply_text("🏙️ Quase lá! Em qual <b>município</b> a ocorrência aconteceu?", parse_mode=ParseMode.HTML)
        return MUNICIPIO

# Lida com o assunto digitado manualmente.
async def assunto_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assunto = update.message.text.strip()
    context.user_data['assunto'] = assunto
    utils.salvar_assunto(assunto) 
    await update.message.reply_text(f"✅ Assunto registrado: <b>{assunto}</b>.", parse_mode=ParseMode.HTML)
    await update.message.reply_text("🏙️ Quase lá! Em qual <b>município</b> a ocorrência aconteceu?", parse_mode=ParseMode.HTML)
    return MUNICIPIO


# --- Etapa: Município ---
async def municipio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['municipio'] = update.message.text.strip().upper()
    await update.message.reply_text(f"✅ Município registrado: <b>{context.user_data['municipio']}</b>.", parse_mode=ParseMode.HTML)
    return await solicitar_data(update, context) 


# --- Etapa: Data da Ocorrência ---
async def solicitar_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        InlineKeyboardButton("📅 Usar data/hora atual", callback_data="data_hoje"),
        InlineKeyboardButton("✏️ Digitar data manualmente", callback_data="data_manual"),
    ]
    keyboard = InlineKeyboardMarkup.from_row(buttons)

    if update.message: 
        await update.message.reply_text("🗓️ Por favor, selecione uma opção para a <b>data da ocorrência</b>:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.callback_query: 
        await update.callback_query.message.reply_text("🗓️ Por favor, selecione uma opção para a <b>data da ocorrência</b>:", reply_markup=keyboard, parse_mode=ParseMode.HTML)

    return DATA 

async def data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: 
        query = update.callback_query
        await query.answer()

        if query.data == "data_hoje":
            dt = datetime.now()
            context.user_data['data'] = dt.strftime("%Y-%m-%d") 
            await query.message.edit_text(f"✅ Data registrada: <b>{dt.strftime('%Y/%m/%d %H:%M')}</b>.", parse_mode=ParseMode.HTML)

            # Pula diretamente para a etapa de demanda
            buttons = [
                [InlineKeyboardButton("➕ Adicionar demanda", callback_data="add_demanda")],
                [InlineKeyboardButton("⏭️ Pular demandas", callback_data="fim_demandas")], 
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.reply_text("📝 Quer adicionar uma <b>demanda</b> relacionada a esta ocorrência?", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            return DEMANDA_ESCOLHA

        elif query.data == "data_manual":
            await query.message.edit_text("✍️ Entendido. Por favor, digite a data no formato <b>AAAA/MM/DD</b> (ex: 2025/06/04):", parse_mode=ParseMode.HTML)
            return DATA_MANUAL

    else:  # Usuário digitou manualmente a data
        texto = update.message.text.strip()
        try:
            dt = datetime.strptime(texto, "%Y/%m/%d")
            context.user_data['data'] = dt.strftime("%Y-%m-%d")
            await update.message.reply_text(f"✅ Data registrada: <b>{dt.strftime('%Y/%m/%d')}</b>.", parse_mode=ParseMode.HTML)

            buttons = [
                [InlineKeyboardButton("➕ Adicionar demanda", callback_data="add_demanda")],
                [InlineKeyboardButton("⏭️ Pular demandas", callback_data="fim_demandas")], 
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text("📝 Quer adicionar uma <b>demanda</b> relacionada a esta ocorrência?", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            return DEMANDA_ESCOLHA 
        except ValueError:
            await update.message.reply_text("❗ Formato inválido. Por favor, digite a data no formato <b>AAAA/MM/DD</b> (ex: 2025/06/04):", parse_mode=ParseMode.HTML)
            return DATA_MANUAL


 #--- Etapa: Foto da Ocorrência (DESATIVADA TEMPORARIAMENTE) ---
async def foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
     if not update.message.photo:
         await update.message.reply_text("❗ Isso não parece uma foto. Por favor, envie uma <b>foto válida</b> da ocorrência.", parse_mode=ParseMode.HTML)
         return FOTO

     photo = update.message.photo[-1] 
     telegram_file = await context.bot.get_file(photo.file_id) 
     photo_bytes = await telegram_file.download_as_bytearray() 

     timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
     user_id = update.effective_user.id
     filename = f"foto_{user_id}_{timestamp}.jpg" 

     logger.info(f"Tentando fazer upload da foto {filename} para o Google Drive.")
     await update.message.reply_text("⏳ Enviando a foto para o Google Drive... Por favor, aguarde, isso pode levar alguns segundos.", parse_mode=ParseMode.HTML) 
     drive_file_id = await upload_photo_to_drive(bytes(photo_bytes), filename) 
    
     if drive_file_id:
         context.user_data["foto"] = drive_file_id 
         logger.info(f"Foto salva no Google Drive. ID: {drive_file_id}")
         await update.message.reply_text("✅ Foto recebida e enviada para o Google Drive com sucesso!")
     else:
         context.user_data["foto"] = "Erro no upload" 
         logger.error("Falha ao enviar foto para o Google Drive.")
         await update.message.reply_text("❌ Ocorreu um erro ao enviar a foto para o Google Drive. Por favor, tente novamente.", parse_mode=ParseMode.HTML)
         return FOTO 

     context.user_data["demandas"] = [] 

     buttons = [
         [InlineKeyboardButton("➕ Adicionar demanda", callback_data="add_demanda")],
         [InlineKeyboardButton("⏭️ Pular demandas", callback_data="fim_demandas")], 
     ]
     reply_markup = InlineKeyboardMarkup(buttons)

     await update.message.reply_text("📝 Quer adicionar uma <b>demanda</b> relacionada a esta ocorrência?", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
     return DEMANDA_ESCOLHA 


# --- Etapa: Demanda ---
async def demanda(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_demanda":
        await query.edit_message_text("✍️ Certo. Por favor, digite o <b>texto completo da demanda</b>:", parse_mode=ParseMode.HTML)
        return DEMANDA_DIGITAR 

    elif data == "fim_demandas":
        await query.edit_message_text("✅ Ok, finalizando as demandas. Vamos para o <b>resumo</b> da ocorrência.", parse_mode=ParseMode.HTML)
        return await resumo(update, context) 

    elif data == "pular_demanda": 
        await query.edit_message_text("Você optou por pular as demandas.")
        return await resumo(update, context)


# Recebe o texto principal da demanda.
async def demanda_digitar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nova_demanda"]= {
        "texto": update.message.text
    }
    await update.message.reply_text("🔢 Agora, informe o <b>número do OV</b> (Orçamento de Venda) relacionado a esta demanda (se não tiver, digite 'N/A'):", parse_mode=ParseMode.HTML)
    return OV 

# Recebe o número do OV.
async def ov(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nova_demanda"]["ov"] = update.message.text
    await update.message.reply_text("🔢 E qual o <b>número do PRO</b> (Protocolo) relacionado (se não tiver, digite 'N/A')?", parse_mode=ParseMode.HTML)
    return PRO 

# Recebe o número do PRO.
async def pro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nova_demanda"]["pro"] = update.message.text

    buttons = [
        [InlineKeyboardButton("➕ Adicionar observação", callback_data="add_obs")],
        [InlineKeyboardButton("⏭️ Pular observação", callback_data="skip_obs")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("💬 Deseja adicionar uma <b>observação</b> específica para esta demanda?", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return OBSERVACAO_ESCOLHA 

# Lida com a escolha de adicionar ou pular observação.
async def observacao_escolha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_obs":
        await query.message.reply_text("✍️ Por favor, digite a <b>observação</b> para esta demanda:", parse_mode=ParseMode.HTML)
        return OBSERVACAO_DIGITAR 
    else:
        context.user_data["nova_demanda"]["observacao"] = "" 
        return await salvar_demanda(update, context) 

# Recebe o texto da observação digitada.
async def observacao_digitar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nova_demanda"]["observacao"] = update.message.text
    return await salvar_demanda(update, context) 

# Salva a demanda atual no dicionário principal de demandas do usuário.
async def salvar_demanda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    demanda = context.user_data.pop("nova_demanda", None) 
    if demanda:
        context.user_data.setdefault("demandas", []).append(demanda) 

    buttons = [
        [InlineKeyboardButton("➕ Adicionar outra demanda", callback_data="add_demanda")],
        [InlineKeyboardButton("✅ Finalizar demandas", callback_data="fim_demandas")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "✅ Demanda adicionada com sucesso! Deseja adicionar outra demanda ou <b>finalizar</b>?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else: 
        await update.message.reply_text(
            "✅ Demanda adicionada com sucesso! Deseja adicionar outra demanda ou <b>finalizar</b>?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    return DEMANDA_ESCOLHA 


# --- Etapa: Resumo da Ocorrência ---
async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message_target = query.message
    elif update.message: 
        message_target = update.message
    else:
        logger.error("A função 'resumo' foi chamada sem um 'update.message' ou 'update.callback_query' válido.")
        return ConversationHandler.END 

    dados = context.user_data 

    foto_info = dados.get('foto', 'N/A')
    if foto_info != 'N/A' and foto_info != 'Erro no upload':
        foto_display = f"ID no Drive: <code>{foto_info}</code>"
    else:
        foto_display = foto_info

    resumo_texto = (
        f"✨ <b>Resumo da Ocorrência:</b> ✨\n\n"
        f"👤 <b>Colaborador:</b> {dados.get('colaborador', 'N/A')}\n"
        f"🤝 <b>Tipo de Visita:</b> {dados.get('tipo_visita', 'N/A')}\n" 
        f"📞 <b>Tipo de Atendimento:</b> {dados.get('tipo_atendimento', 'N/A')}\n"
        f"📅 <b>Data:</b> {dados.get('data', 'N/A')}\n" # Move data para cima
        f"🌍 <b>Município:</b> {dados.get('municipio', 'N/A')}\n" # Move município para cima
        f"📌 <b>Assunto:</b> {dados.get('assunto', 'N/A')}\n" # Move assunto para cima
        f"📷 <b>Foto:</b> {foto_display}\n\n"
        f"🧑‍🤝‍🏢 <b>Figuras Públicas e Órgãos Relacionados:</b>\n"
    )

    figuras_orgaos = dados.get("figuras_orgaos", [])
    if figuras_orgaos:
        for i, fo in enumerate(figuras_orgaos, 1):
            resumo_texto += (
                f"<b>{i}. Órgão:</b> {fo.get('orgao_publico', 'N/A')}\n"
                f"   • Figura: {fo.get('figura_publica', 'N/A')}\n"
                f"   • Cargo: {fo.get('cargo', 'N/A')}\n"
            )
    else:
        resumo_texto += "<i>Nenhuma figura pública ou órgão relacionado(a) adicionado(a).</i>\n"
    
    resumo_texto += f"\n📝 <b>Demandas Registradas:</b>\n" # Linha de separação

    demandas = dados.get("demandas", [])
    if demandas:
        for i, d in enumerate(demandas, 1):
            resumo_texto += (
                f"<b>{i}. Demanda:</b> {d.get('texto', 'N/A')}\n"
                f"   • OV: {d.get('ov', 'N/A')} | PRO: {d.get('pro', 'N/A')}\n"
                f"   • Obs: {d.get('observacao', 'N/A')}\n"
            )
    else:
        resumo_texto += "<i>Nenhuma demanda adicional registrada.</i>\n" 

    buttons = [
        [InlineKeyboardButton("✅ Confirmar e Salvar", callback_data="confirmar_salvar")],
        [InlineKeyboardButton("❌ Cancelar Tudo", callback_data="cancelar_resumo")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await message_target.reply_text(
        resumo_texto,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML 
    )

    return CONFIRMACAO_FINAL 


# --- Etapa: Confirmação Final de Salvamento ---
async def confirmacao(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "confirmar_salvar":
        utils.salvar_no_banco(context.user_data) 
        utils.export_data_to_drive()
        utils.salvar_demandas_no_banco(context.user_data, context.user_data.get("demandas", []))
        utils.export_demandas_to_drive(context.user_data.get("demandas", []))
        await query.edit_message_text(
            "🎉 Dados salvos com sucesso no banco de dados e nos arquivos Excel do Google Drive! Muito obrigado pelo seu registro.", 
            parse_mode=ParseMode.HTML
        )
        context.user_data.clear() 
        return ConversationHandler.END 

    elif data == "cancelar_resumo":
        await query.edit_message_text(
            "🚫 Operação cancelada no resumo. Os dados não foram salvos. Use /iniciar para começar novamente.", 
            parse_mode=ParseMode.HTML
        )
        context.user_data.clear() 
        return ConversationHandler.END 
    
# --- Função de Fallback para Cancelar ---
async def cancelar_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Operação cancelada. Use /iniciar para reiniciar o registro.")
    context.user_data.clear()
    return ConversationHandler.END

