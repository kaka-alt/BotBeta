from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from datetime import datetime
import os
import csv
import logging 
from telegram.constants import ParseMode # Essencial para usar formatação como negrito e emojis

# Importa as funções que interagem com o Google Drive, como upload de fotos e exportação de dados Excel.
from exportar_para_excel import export_data_to_drive, upload_photo_to_drive 

# Importa módulos de suporte para configurações (config), utilidades (utils) e dados globais (globals).
import config 
import utils  
from globals import user_data 

# Configura o logger para este arquivo, útil para acompanhar o que está acontecendo no Render.
logger = logging.getLogger(__name__)

# --- Definição dos Estados da Nossa Conversa ---
# Cada um desses nomes representa um "passo" no fluxo do bot. 
# O 'range()' nos ajuda a dar um número único para cada estado, que é usado pelo ConversationHandler.
# ADICIONADO: TIPO_VISITA
COLABORADOR, COLABORADOR_MANUAL, TIPO_VISITA, ORGAO_PUBLICO_KEYWORD, ORGAO_PUBLICO_PAGINACAO, ORGAO_PUBLICO_MANUAL, \
FIGURA_PUBLICA, CARGO, ASSUNTO_PALAVRA_CHAVE, ASSUNTO_PAGINACAO, ASSUNTO_MANUAL, \
MUNICIPIO, DATA, DATA_MANUAL, FOTO, DEMANDA_ESCOLHA, DEMANDA_DIGITAR, OV, PRO, \
OBSERVACAO_ESCOLHA, OBSERVACAO_DIGITAR, CONFIRMACAO_FINAL = range(22) # AJUSTADO: range(22) para incluir o novo estado


# --- Início do Nosso Registro: Seleção do Colaborador ---
async def iniciar_colaborador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Crio botões dinamicamente com a lista de colaboradores que você definiu em 'config.py'.
    buttons = [InlineKeyboardButton(name, callback_data=f"colaborador_{name}") for name in config.COLABORADORES]
    # Adiciono a opção para digitar manualmente, caso o nome não esteja na lista.
    buttons.append(InlineKeyboardButton("Outro", callback_data="colaborador_outro"))
    # Organizo os botões em um menu de 2 colunas para ficar visualmente melhor.
    keyboard = InlineKeyboardMarkup(utils.build_menu(buttons, n_cols=2))
    # Envio a primeira mensagem, pedindo para o usuário escolher o colaborador.
    await update.message.reply_text(
        "👋 Olá! Vamos começar o registro da ocorrência.\nPor favor, selecione o <b>colaborador</b> na lista ou clique em 'Outro' para digitar manualmente:", 
        reply_markup=keyboard, 
        parse_mode=ParseMode.HTML # Permite usar o negrito (<b>) na mensagem.
    )
    # Sinalizo ao bot que agora estamos no estado de "COLABORADOR", esperando a escolha.
    return COLABORADOR

# Lida com a escolha do colaborador via botão ou a opção "Outro".
async def colaborador_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query # Pego a informação do botão que foi clicado.
    await query.answer() # Importante: indica ao Telegram que a interação foi recebida.
    data = query.data # O texto que estava no 'callback_data' do botão.

    if data == "colaborador_outro":
        # Se o usuário optou por digitar o nome.
        await query.message.reply_text("✍️ Entendido! Por favor, digite o <b>nome completo do colaborador</b>:")
        return COLABORADOR_MANUAL # Passamos para o estado onde esperamos o texto digitado.
    else:
        # Se o usuário escolheu um colaborador da lista.
        colaborador = data.replace("colaborador_", "") # Removo o prefixo para ter só o nome.
        context.user_data['colaborador'] = colaborador # Salvo o nome no contexto da conversa.
        await query.message.edit_text(f"✅ Colaborador selecionado: <b>{colaborador}</b>.", parse_mode=ParseMode.HTML) # Edito a mensagem anterior para confirmar.
        # NOVO: Transição para o estado de TIPO_VISITA
        return await solicitar_tipo_visita(update, context) # Pergunto sobre o tipo de visita.

# Lida com a entrada manual do nome do colaborador.
async def colaborador_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip() # Pego o texto digitado.
    context.user_data['colaborador'] = nome # Salvo o nome.
    await update.message.reply_text(f"✅ Colaborador registrado: <b>{nome}</b>.", parse_mode=ParseMode.HTML)
    # NOVO: Transição para o estado de TIPO_VISITA
    return await solicitar_tipo_visita(update, context) # Pergunto sobre o tipo de visita.


# --- NOVO: Etapa: Tipo de Visita ---
async def solicitar_tipo_visita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        InlineKeyboardButton("🔄 Reativa", callback_data="tipo_visita_reativa"),
        InlineKeyboardButton(" proactive Proativa", callback_data="tipo_visita_proativa"),
    ]
    keyboard = InlineKeyboardMarkup.from_row(buttons)

    # Verifica se a chamada veio de uma mensagem ou de um botão para responder corretamente.
    if update.message:
        await update.message.reply_text("🤝 Excelente! Agora, por favor, selecione o <b>tipo da visita</b> realizada:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.message.reply_text("🤝 Excelente! Agora, por favor, selecione o <b>tipo da visita</b> realizada:", reply_markup=keyboard, parse_mode=ParseMode.HTML)

    return TIPO_VISITA # Move para o novo estado

async def tipo_visita_escolha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    tipo_visita = data.replace("tipo_visita_", "") # Remove o prefixo para obter o tipo.
    context.user_data['tipo_visita'] = tipo_visita.capitalize() # Salva o tipo (capitalizado).

    await query.message.edit_text(f"✅ Tipo de visita selecionado: <b>{tipo_visita.capitalize()}</b>.", parse_mode=ParseMode.HTML)
    await query.message.reply_text("🏠 Perfeito! Agora, digite uma <b>palavra-chave</b> para buscar o <b>órgão público</b> (ex: 'prefeitura' ou 'saúde'):", parse_mode=ParseMode.HTML)
    return ORGAO_PUBLICO_KEYWORD # Continua o fluxo para o próximo passo.

# --- FIM NOVO: Etapa: Tipo de Visita ---


# --- Etapa: Órgão Público ---
# Inicia a busca por órgão público com uma palavra-chave.
async def buscar_orgao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.lower() # Pego a palavra-chave e padronizo para minúsculas.
    orgaos = utils.ler_orgaos_csv() # Leio a lista de órgãos do seu CSV através de 'utils.py'.
    resultados = [o for o in orgaos if keyword in o.lower()] # Filtro os resultados.
    context.user_data['orgaos_busca'] = resultados # Guardo os resultados para a paginação.
    context.user_data['orgao_pagina'] = 0 # Começo na primeira página.

    if not resultados:
        # Se não encontramos nada.
        await update.message.reply_text("❗ Não encontramos nenhum órgão com essa palavra-chave. Por favor, digite <b>manualmente o nome completo do órgão público</b>:", parse_mode=ParseMode.HTML)
        return ORGAO_PUBLICO_MANUAL # Pedimos para o usuário digitar.

    # Se encontramos resultados, mostramos os botões de paginação.
    buttons, pagina_atual = utils.botoes_pagina(resultados, 0, prefix="orgao_")
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        f"🔎 Encontrei <b>{len(resultados)} resultados</b> para '<i>{keyword}</i>'. Selecione abaixo ou navegue nas opções:", 
        reply_markup=keyboard, 
        parse_mode=ParseMode.HTML
    )
    return ORGAO_PUBLICO_PAGINACAO # Passamos para o estado de paginação.

# Lida com a navegação na lista de órgãos públicos e a seleção.
async def orgao_paginacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    pagina_atual = context.user_data.get("orgao_pagina", 0)
    resultados = context.user_data.get("orgaos_busca", [])

    if data == "orgao_proximo":
        # Avança para a próxima página de resultados.
        pagina_atual += 1
        context.user_data["orgao_pagina"] = pagina_atual
        botoes, _ = utils.botoes_pagina(resultados, pagina_atual, prefix="orgao_")
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(botoes)) # Atualizo os botões na mesma mensagem.
        return ORGAO_PUBLICO_PAGINACAO # Continuamos na paginação.

    elif data == "orgao_voltar":
        # Volta para a página anterior.
        pagina_atual = max(0, pagina_atual - 1) # Evita páginas negativas.
        context.user_data["orgao_pagina"] = pagina_atual
        botoes, _ = utils.botoes_pagina(resultados, pagina_atual, prefix="orgao_")
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(botoes))
        return ORGAO_PUBLICO_PAGINACAO 

    elif data == "orgao_inserir_manual":
        # Opção para digitar o órgão manualmente.
        await query.message.reply_text("✍️ Certo. Por favor, digite <b>manualmente o nome completo do órgão público</b>:", parse_mode=ParseMode.HTML)
        return ORGAO_PUBLICO_MANUAL # Passamos para o estado de digitação manual.

    elif data == "orgao_refazer_busca":
        # Opção para uma nova busca.
        await query.message.reply_text("🔄 Ok, vamos refazer a busca. Digite uma nova <b>palavra-chave</b> para o órgão público:", parse_mode=ParseMode.HTML)
        return ORGAO_PUBLICO_KEYWORD # Voltamos para a busca por palavra-chave.
    
    else:
        # Quando um órgão é selecionado da lista.
        orgao_selecionado = data.replace("orgao_", "")
        context.user_data["orgao_publico"] = orgao_selecionado # Salvo o órgão.
        await query.message.edit_text(f"✅ Órgão selecionado: <b>{orgao_selecionado}</b>.", parse_mode=ParseMode.HTML)
        await query.message.reply_text("🧑‍💼 Excelente! Agora, digite o <b>nome completo da figura pública</b> (a pessoa de contato) relacionada a este órgão:", parse_mode=ParseMode.HTML)
        return FIGURA_PUBLICA # Seguimos para a figura pública.
    
# Lida com a entrada manual do nome do órgão público.
async def orgao_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()
    context.user_data['orgao_publico'] = nome
    utils.salvar_orgao(nome)  # Salvo o novo órgão no seu CSV de órgãos (via 'utils.py').
    await update.message.reply_text(f"✅ Órgão público registrado manualmente: <b>{nome}</b>.", parse_mode=ParseMode.HTML)
    await update.message.reply_text("🧑‍💼 Excelente! Agora, digite o <b>nome completo da figura pública</b> (a pessoa de contato) relacionada a este órgão:", parse_mode=ParseMode.HTML)
    return FIGURA_PUBLICA 


# --- Etapa: Figura Pública ---
async def figura_publica_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    figura_publica = update.message.text.strip()
    context.user_data['figura_publica'] = figura_publica
    await update.message.reply_text(f"✅ Figura pública registrada: <b>{figura_publica}</b>.", parse_mode=ParseMode.HTML)
    await update.message.reply_text("💼 E qual é o <b>Cargo</b> dessa figura pública?", parse_mode=ParseMode.HTML)
    return CARGO 


# --- Etapa: Cargo ---
async def cargo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargo = update.message.text.strip()
    context.user_data['cargo'] = cargo
    await update.message.reply_text(f"✅ Cargo registrado: <b>{cargo}</b>.", parse_mode=ParseMode.HTML)
    await update.message.reply_text("✉️ Por favor, digite uma <b>palavra-chave</b> para buscar o <b>assunto</b> da ocorrência:", parse_mode=ParseMode.HTML)
    return ASSUNTO_PALAVRA_CHAVE 


# --- Etapa: Assunto ---
# Inicia a busca por assunto com uma palavra-chave.
async def buscar_assunto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    palavra_chave = update.message.text.lower()
    assuntos = utils.ler_assuntos_csv() # Leio a lista de assuntos do seu CSV.
    resultados = [a for a in assuntos if palavra_chave in a.lower()]
    context.user_data['assuntos_busca'] = resultados
    context.user_data['assunto_pagina'] = 0

    if not resultados:
        # Se nenhum assunto for encontrado.
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
    context.user_data['municipio'] = update.message.text.strip()
    await update.message.reply_text(f"✅ Município registrado: <b>{context.user_data['municipio']}</b>.", parse_mode=ParseMode.HTML)
    return await solicitar_data(update, context) # Chama a função que pede a data.


# --- Etapa: Data da Ocorrência ---
# Pergunta ao usuário como ele quer informar a data (atual ou manual).
async def solicitar_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        InlineKeyboardButton("📅 Usar data/hora atual", callback_data="data_hoje"),
        InlineKeyboardButton("✏️ Digitar data manualmente", callback_data="data_manual"),
    ]
    keyboard = InlineKeyboardMarkup.from_row(buttons)

    # Verifica se a chamada veio de uma mensagem ou de um botão para responder corretamente.
    if update.message: 
        await update.message.reply_text("🗓️ Por favor, selecione uma opção para a <b>data da ocorrência</b>:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.callback_query: 
        await update.callback_query.message.reply_text("🗓️ Por favor, selecione uma opção para a <b>data da ocorrência</b>:", reply_markup=keyboard, parse_mode=ParseMode.HTML)

    return DATA 

# Lida com a entrada da data (escolha de botão ou digitação manual).
async def data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: # Se a entrada veio de um clique de botão.
        query = update.callback_query
        await query.answer()

        if query.data == "data_hoje":
            dt = datetime.now()
            context.user_data['data'] = dt.strftime("%Y-%m-%d") # Salva a data formatada.
            await query.message.edit_text(f"✅ Data registrada: <b>{dt.strftime('%Y/%m/%d %H:%M')}</b>.", parse_mode=ParseMode.HTML) # Confirma com data e hora.
            await query.message.reply_text("📷 Perfeito! Agora, por favor, envie a <b>foto</b> da ocorrência:", parse_mode=ParseMode.HTML)
            return FOTO 

        elif query.data == "data_manual":
            await query.message.edit_text("✍️ Entendido. Por favor, digite a data no formato <b>AAAA/MM/DD</b> (ex: 2025/06/04):", parse_mode=ParseMode.HTML)
            return DATA_MANUAL 

    else: # Se a entrada veio de uma mensagem de texto (digitação manual).
        texto = update.message.text.strip()
        try:
            # Tenta converter o texto para o formato de data.
            dt = datetime.strptime(texto, "%Y/%m/%d")
            context.user_data['data'] = dt.strftime("%Y-%m-%d")
            await update.message.reply_text(f"✅ Data registrada: <b>{dt.strftime('%Y/%m/%d')}</b>.", parse_mode=ParseMode.HTML)
            await update.message.reply_text("📷 Perfeito! Agora, por favor, envie a <b>foto</b> da ocorrência:", parse_mode=ParseMode.HTML)
            return FOTO 
        except ValueError:
            # Se o formato estiver incorreto.
            await update.message.reply_text("❗ Formato inválido. Por favor, digite a data no formato <b>AAAA/MM/DD</b> (ex: 2025/06/04):", parse_mode=ParseMode.HTML)
            return DATA_MANUAL 


# --- Etapa: Foto da Ocorrência ---
async def foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        # Se o que foi enviado não é uma foto.
        await update.message.reply_text("❗ Isso não parece uma foto. Por favor, envie uma <b>foto válida</b> da ocorrência.", parse_mode=ParseMode.HTML)
        return FOTO # Pedimos novamente a foto.

    photo = update.message.photo[-1] # Pego a foto de maior resolução.
    telegram_file = await context.bot.get_file(photo.file_id) # Obtenho o objeto de arquivo do Telegram.
    photo_bytes = await telegram_file.download_as_bytearray() # Baixo a foto para a memória.

    # Gero um nome de arquivo único para o Google Drive, usando o ID do usuário e um timestamp.
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    user_id = update.effective_user.id
    filename = f"foto_{user_id}_{timestamp}.jpg" 

    logger.info(f"Tentando fazer upload da foto {filename} para o Google Drive.")
    # Dou um feedback imediato para o usuário, avisando que o upload está em andamento.
    await update.message.reply_text("⏳ Enviando a foto para o Google Drive... Por favor, aguarde, isso pode levar alguns segundos.", parse_mode=ParseMode.HTML) 
    # Chamo a função de upload para o Google Drive.
    drive_file_id = await upload_photo_to_drive(bytes(photo_bytes), filename) 
    
    if drive_file_id:
        # Se o upload foi um sucesso.
        context.user_data["foto"] = drive_file_id # Salvo o ID do arquivo no Google Drive.
        logger.info(f"Foto salva no Google Drive. ID: {drive_file_id}")
        await update.message.reply_text("✅ Foto recebida e enviada para o Google Drive com sucesso!")
    else:
        # Se houve um erro no upload.
        context.user_data["foto"] = "Erro no upload" # Indico a falha.
        logger.error("Falha ao enviar foto para o Google Drive.")
        await update.message.reply_text("❌ Ocorreu um erro ao enviar a foto para o Google Drive. Por favor, tente novamente.", parse_mode=ParseMode.HTML)
        return FOTO # Permaneço no estado de foto para o usuário tentar de novo.

    context.user_data["demandas"] = [] # Inicializo a lista de demandas para esta ocorrência.

    # Botões para perguntar se o usuário quer adicionar demandas.
    buttons = [
        [InlineKeyboardButton("➕ Adicionar demanda", callback_data="add_demanda")],
        [InlineKeyboardButton("⏭️ Pular demandas", callback_data="fim_demandas")], 
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text("📝 Quer adicionar uma <b>demanda</b> relacionada a esta ocorrência?", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return DEMANDA_ESCOLHA 

# --- Etapa: Demanda ---
# Lida com a escolha de adicionar demandas ou finalizar.
async def demanda(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_demanda":
        # Se o usuário quer adicionar uma demanda.
        await query.edit_message_text("✍️ Certo. Por favor, digite o <b>texto completo da demanda</b>:", parse_mode=ParseMode.HTML)
        return DEMANDA_DIGITAR 

    elif data == "fim_demandas":
        # Se o usuário quer finalizar as demandas.
        await query.edit_message_text("✅ Ok, finalizando as demandas. Vamos para o <b>resumo</b> da ocorrência.", parse_mode=ParseMode.HTML)
        return await resumo(update, context) # Chamo a função de resumo.

    elif data == "pular_demanda": # Este é um callback_data alternativo, caso você use.
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
    await update.message.reply_text("🔢 E qual o <b>número do PRO</b> (Projeto) relacionado (se não tiver, digite 'N/A')?", parse_mode=ParseMode.HTML)
    return PRO 

# Recebe o número do PRO.
async def pro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nova_demanda"]["pro"] = update.message.text

    # Botões para decidir sobre adicionar observação.
    keyboard = [
        [InlineKeyboardButton("➕ Adicionar observação", callback_data="add_obs")],
        [InlineKeyboardButton("⏭️ Pular observação", callback_data="skip_obs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
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
        context.user_data["nova_demanda"]["observacao"] = "" # Se pulou, a observação fica vazia.
        return await salvar_demanda(update, context) # Salva a demanda.

# Recebe o texto da observação digitada.
async def observacao_digitar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nova_demanda"]["observacao"] = update.message.text
    return await salvar_demanda(update, context) # Salva a demanda.

# Salva a demanda atual no dicionário principal de demandas do usuário.
async def salvar_demanda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    demanda = context.user_data.pop("nova_demanda", None) # Pego e removo a demanda temporária.
    if demanda:
        context.user_data.setdefault("demandas", []).append(demanda) # Adiciono à lista de demandas.

    # Botões para adicionar outra demanda ou finalizar.
    buttons = [
        [InlineKeyboardButton("➕ Adicionar outra demanda", callback_data="add_demanda")],
        [InlineKeyboardButton("✅ Finalizar demandas", callback_data="fim_demandas")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    # Responde ou edita a mensagem com feedback.
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
# Mostra um resumo de todos os dados coletados antes da confirmação final.
async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Determino onde o bot deve responder (se é uma query de botão ou uma mensagem normal).
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message_target = query.message
    elif update.message: 
        message_target = update.message
    else:
        logger.error("A função 'resumo' foi chamada sem um 'update.message' ou 'update.callback_query' válido.")
        return ConversationHandler.END 

    dados = context.user_data # Pego todos os dados coletados do usuário para o resumo.

    # Formato a informação da foto (mostro o ID do Drive para referência).
    foto_info = dados.get('foto', 'N/A')
    if foto_info != 'N/A' and foto_info != 'Erro no upload':
        foto_display = f"ID no Drive: <code>{foto_info}</code>"
    else:
        foto_display = foto_info

    # Construo o texto do resumo com emojis e formatação HTML para destacar.
    resumo_texto = (
        f"✨ <b>Resumo da Ocorrência:</b> ✨\n\n"
        f"👤 <b>Colaborador:</b> {dados.get('colaborador', 'N/A')}\n"
        f"🤝 <b>Tipo de Visita:</b> {dados.get('tipo_visita', 'N/A')}\n" # ADICIONADO: Tipo de Visita
        f"🏢 <b>Órgão Público:</b> {dados.get('orgao_publico', 'N/A')}\n"
        f"🧑‍💼 <b>Figura Pública:</b> {dados.get('figura_publica', 'N/A')}\n"
        f"💼 <b>Cargo:</b> {dados.get('cargo', 'N/A')}\n"
        f"📌 <b>Assunto:</b> {dados.get('assunto', 'N/A')}\n"
        f"🌍 <b>Município:</b> {dados.get('municipio', 'N/A')}\n"
        f"📅 <b>Data:</b> {dados.get('data', 'N/A')}\n"
        f"📷 <b>Foto:</b> {foto_display}\n\n"
        f"📝 <b>Demandas Registradas:</b>\n"
    )

    demandas = dados.get("demandas", [])
    if demandas:
        # Listo cada demanda com seus detalhes.
        for i, d in enumerate(demandas, 1):
            resumo_texto += (
                f"<b>{i}. Demanda:</b> {d.get('texto', 'N/A')}\n"
                f"   • OV: {d.get('ov', 'N/A')} | PRO: {d.get('pro', 'N/A')}\n"
                f"   • Obs: {d.get('observacao', 'N/A')}\n"
            )
    else:
        resumo_texto += "<i>Nenhuma demanda adicional registrada.</i>\n" # Mensagem se não houver demandas.

    # Botões para confirmar o salvamento ou cancelar tudo.
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
        # Salvo os dados no PostgreSQL (usando a função do 'utils.py').
        utils.salvar_no_banco(context.user_data) 
        # Aciono a exportação dos dados do PostgreSQL para arquivos Excel no Google Drive.
        export_data_to_drive() 
        await query.edit_message_text(
            "🎉 Dados salvos com sucesso no banco de dados e nos arquivos Excel do Google Drive! Muito obrigado pelo seu registro.", 
            parse_mode=ParseMode.HTML
        )
        context.user_data.clear() # Limpo todos os dados da conversa do usuário.
        return ConversationHandler.END # Encerro a conversa.

    elif data == "cancelar_resumo":
        await query.edit_message_text(
            "🚫 Operação cancelada no resumo. Os dados não foram salvos. Use /iniciar para começar novamente.", 
            parse_mode=ParseMode.HTML
        )
        context.user_data.clear() # Limpo os dados.
        return ConversationHandler.END 
    
# --- Função de Fallback para Cancelar ---
# Esta função é importante! Ela é usada como um "botão de pânico" no ConversationHandler.
# Se o usuário digitar /cancelar a qualquer momento, esta função será chamada para encerrar a conversa.
async def cancelar_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Operação cancelada. Use /iniciar para reiniciar o registro.")
    context.user_data.clear()
    return ConversationHandler.END

