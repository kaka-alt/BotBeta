import json
import os
import pandas as pd
from telegram import InlineKeyboardButton
from datetime import datetime
from config import *
from globals import user_data
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload
from io import BytesIO

logger = logging.getLogger(__name__)

# --- FUNÇÕES UTILITÁRIAS ---

def build_menu(buttons, n_cols, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if footer_buttons:
        menu.append(footer_buttons)
    return menu

def botoes_pagina(lista, pagina, prefix="", por_pagina=5):
    inicio = pagina * por_pagina
    fim = inicio + por_pagina
    sublista = lista[inicio:fim]

    buttons = [
        [InlineKeyboardButton(text=item, callback_data=f"{prefix}{item}")]
        for item in sublista
    ]

    buttons.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data=f"{prefix}voltar"),
        InlineKeyboardButton("➡️ Próximo", callback_data=f"{prefix}proximo"),
    ])
    buttons.append([
        InlineKeyboardButton("📝 Inserir manualmente", callback_data=f"{prefix}inserir_manual"),
        InlineKeyboardButton("🔄 Refazer busca", callback_data=f"{prefix}refazer_busca"),
    ])

    return buttons, pagina

# --- LISTAS CSV (sem alteração) ---

def ler_orgaos_csv():
    if not os.path.exists(CSV_ORGAOS):
        logger.warning(f"CSV de órgãos não encontrado em {CSV_ORGAOS}. Criando um DataFrame vazio.")
        return pd.DataFrame(columns=['nome'])
    df = pd.read_csv(CSV_ORGAOS)
    return df['nome'].dropna().tolist()

def salvar_orgao(novo_orgao: str):
    caminho_orgaos = CSV_ORGAOS
    os.makedirs(os.path.dirname(caminho_orgaos), exist_ok=True)
    novo_orgao = novo_orgao.strip()
    orgaos_existentes = set()
    if os.path.exists(caminho_orgaos):
        with open(caminho_orgaos, mode='r', encoding='utf-8') as f:
            orgaos_existentes = {linha.strip() for linha in f.readlines()}
    if novo_orgao and novo_orgao not in orgaos_existentes:
        with open(caminho_orgaos, mode='a', newline='', encoding='utf-8') as f:
            f.write(f"{novo_orgao}\n")

def ler_assuntos_csv():
    if not os.path.exists(CSV_ASSUNTOS):
        logger.warning(f"CSV de assuntos não encontrado em {CSV_ASSUNTOS}. Criando um DataFrame vazio.")
        return pd.DataFrame(columns=['assunto'])
    df = pd.read_csv(CSV_ASSUNTOS)
    return df['assunto'].dropna().tolist()

def salvar_assunto(novo_assunto: str):
    caminho_assuntos = CSV_ASSUNTOS
    os.makedirs(os.path.dirname(caminho_assuntos), exist_ok=True)
    novo_assunto = novo_assunto.strip()
    assuntos_existentes = set()
    if os.path.exists(caminho_assuntos):
        with open(caminho_assuntos, mode='r', encoding='utf-8') as f:
            assuntos_existentes = {linha.strip() for linha in f.readlines()}
    if novo_assunto and novo_assunto not in assuntos_existentes:
        with open(caminho_assuntos, mode='a', newline='', encoding='utf-8') as f:
            f.write(f"{novo_assunto}\n")

# --- GOOGLE DRIVE SERVICE AUTH ---

def get_drive_service():
    """Autentica com a API do Google Drive usando credenciais JSON."""
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            raise ValueError("GOOGLE_CREDENTIALS_JSON não está configurada nas variáveis de ambiente.")
        info = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=credentials)
        logger.info("Serviço do Google Drive autenticado com sucesso.")
        return service
    except Exception as e:
        logger.error(f"Erro ao obter serviço do Google Drive: {e}", exc_info=True)
        return None

# --- EXPORTAR REUNIÕES PARA PLANILHA NO DRIVE ---

def exportar_reunioes_para_drive(dados: dict):
    logger.info("Exportando reunião direto para planilha 'REUNIAO_PP.xlsx' (sem banco)")
    service = get_drive_service()
    if not service:
        logger.error("Serviço do Google Drive não disponível.")
        return

    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    spreadsheet_name = "REUNIAO_PP.xlsx"

    try:
        query = f"name='{spreadsheet_name}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        if not files:
            raise FileNotFoundError(f"Arquivo '{spreadsheet_name}' não encontrado.")
        file_id = files[0]["id"]

        request = service.files().get_media(fileId=file_id)
        fh = BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)

        df_existente = pd.read_excel(fh, engine='openpyxl')

        figuras_orgaos = dados.get("figuras_orgaos")
        if figuras_orgaos and len(figuras_orgaos) > 0:
            orgao = figuras_orgaos[0].get("orgao_publico", "NÃO INFORMADO")
            figura_publica = figuras_orgaos[0].get("figura_publica", "")
            cargo = figuras_orgaos[0].get("cargo", "")
        else:
            orgao = "NÃO INFORMADO"
            figura_publica = ""
            cargo = ""

        municipio = dados.get("municipio", "")
        participante = f"{orgao} - {municipio}" if municipio else orgao
        cliente = f"{figura_publica} - {cargo}".strip(" -")

        data_raw = dados.get("data")
        if isinstance(data_raw, (datetime, pd.Timestamp)):
            data_str = data_raw.strftime('%Y-%m-%d')
        else:
            data_str = str(data_raw) if data_raw else ""

        assunto = dados.get("assunto", "").upper()
        tipo_atendimento = dados.get("tipo_atendimento", "")
        colaborador = dados.get("colaborador", "")
        tipo_visita = dados.get("tipo_visita", "")

        nova_linha = {
            "DATA": data_str,
            "CATEGORIA": orgao,
            "PARTICIPANTE": participante,
            "CLIENTE": cliente,
            "ASSUNTO": assunto,
            "TIPO ATENDIMENTO": tipo_atendimento,
            "MUNICIPIO": municipio,
            "COLABORADOR": colaborador,
            "Item Type": "",
            "Path": "",
            "ATENDIMENTO": tipo_visita,
            "TEMA REUNIÃO": assunto
        }

        logger.info(f"Nova linha reunião: {nova_linha}")

        df_novo = pd.DataFrame([nova_linha])
        df_final = pd.concat([df_existente, df_novo], ignore_index=True)

        buffer = BytesIO()
        df_final.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)

        media_body = MediaIoBaseUpload(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        service.files().update(fileId=file_id, media_body=media_body).execute()

        logger.info(f"Planilha '{spreadsheet_name}' atualizada com sucesso no Drive (sem banco).")

    except Exception as e:
        logger.error(f"Erro ao exportar reunião diretamente para planilha: {e}", exc_info=True)

# --- EXPORTAR DEMANDAS PARA PLANILHA NO DRIVE ---

def exportar_demandas_para_drive(dados_gerais: dict, demandas: list[dict]):
    logger.info("Exportando demandas direto para planilha 'DEMANDAS_PP.xlsx' (sem banco)")
    service = get_drive_service()
    if not service:
        logger.error("Serviço do Google Drive não disponível.")
        return

    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    spreadsheet_name = "DEMANDAS_PP.xlsx"

    try:
        query = f"name='{spreadsheet_name}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        if not files:
            raise FileNotFoundError(f"Arquivo '{spreadsheet_name}' não encontrado.")
        file_id = files[0]["id"]

        request = service.files().get_media(fileId=file_id)
        fh = BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)

        df_existente = pd.read_excel(fh, engine='openpyxl')

        novas_linhas = []
        for d in demandas:
            categoria = "NÃO INFORMADO"
            participante = ""
            cliente = ""

            figuras_orgaos = dados_gerais.get('figuras_orgaos')
            if figuras_orgaos and len(figuras_orgaos) > 0:
                categoria = figuras_orgaos[0].get("orgao_publico", categoria)
                participante = f"{categoria} - {dados_gerais.get('municipio', '')}"
                cliente = f"{figuras_orgaos[0].get('figura_publica', '')} - {figuras_orgaos[0].get('cargo', '')}"

            data_raw = dados_gerais.get("data")
            if isinstance(data_raw, (datetime, pd.Timestamp)):
                data_str = data_raw.strftime('%Y-%m-%d')
            else:
                data_str = str(data_raw) if data_raw else ""

            novas_linhas.append({
                "DATA": data_str,
                "MUNICIPIO": dados_gerais.get("municipio", ""),
                "COLABORADOR": dados_gerais.get("colaborador", ""),
                "CATEGORIA": categoria,
                "PARTICIPANTE": participante,
                "CLIENTE": cliente,
                "ASSUNTO": dados_gerais.get("assunto", "").upper(),
                "TIPO ATENDIMENTO": dados_gerais.get("tipo_atendimento", ""),
                "ATENDIMENTO": dados_gerais.get("tipo_visita", ""),
                "DEMANDA": d.get("demanda", ""),
                "OV": d.get("ov", ""),
                "PRO": d.get("pro", ""),
                "OBSERVACAO": d.get("observacao", "")
            })

        logger.info(f"Novas linhas demandas: {novas_linhas}")

        df_novo = pd.DataFrame(novas_linhas)
        df_final = pd.concat([df_existente, df_novo], ignore_index=True)

        buffer = BytesIO()
        df_final.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)

        media_body = MediaIoBaseUpload(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        service.files().update(fileId=file_id, media_body=media_body).execute()

        logger.info(f"Planilha '{spreadsheet_name}' atualizada com sucesso no Drive (sem banco).")

    except Exception as e:
        logger.error(f"Erro ao exportar demandas diretamente para planilha: {e}", exc_info=True)

# --- FUNÇÃO PARA UPLOAD DE FOTO (EM MEMÓRIA) ---

async def upload_photo_to_drive(photo_bytes: bytes, filename: str) -> str | None:
    drive_service = get_drive_service()
    if not drive_service:
        logger.error("Serviço do Google Drive não disponível para upload de foto.")
        return None

    # Usa a pasta específica para fotos, se configurada; senão, pasta padrão
    folder_id = os.environ.get("GOOGLE_DRIVE_PHOTOS_FOLDER_ID") or os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        logger.error("Nenhuma pasta configurada para upload de fotos no Google Drive.")
        return None

    try:
        file_metadata = {
            'name': filename,
            'parents': [folder_id],
            'mimeType': 'image/jpeg'
        }
        media = MediaIoBaseUpload(BytesIO(photo_bytes), mimetype='image/jpeg', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = file.get('id')
        logger.info(f"Foto '{filename}' enviada para o Google Drive (pasta: {folder_id}) com ID: {file_id}")
        return file_id
    except Exception as e:
        logger.error(f"Erro ao fazer upload da foto para o Google Drive: {e}", exc_info=True)
        return None
