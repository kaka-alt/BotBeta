import json
import os
import pandas as pd
from telegram import InlineKeyboardButton
from datetime import datetime
from config import *
from globals import user_data
import psycopg2 
import urllib.parse
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account



logger = logging.getLogger(__name__)

# Funções utilitárias para o bot

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

# Lista de Órgãos Públicos
def ler_orgaos_csv():
    # Adicionado tratamento para arquivo inexistente
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

# Lista Assuntos
def ler_assuntos_csv():
    # Adicionado tratamento para arquivo inexistente
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

# --- FUNÇÕES PARA POSTGRESQL ---
def conectar_banco():
    """Conecta ao banco de dados PostgreSQL."""
    try:
        url = os.environ.get("DATABASE_PUBLIC_URL")
        if not url:
            raise ValueError("DATABASE_PUBLIC_URL não está configurada nas variáveis de ambiente.")
        
        parsed_url = urllib.parse.urlparse(url)

        dbname = parsed_url.path[1:] 
        user = parsed_url.username
        password = parsed_url.password
        host = parsed_url.hostname
        port = parsed_url.port

        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        logger.info("Conexão com o banco de dados PostgreSQL estabelecida com sucesso.")
        return conn
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {e}", exc_info=True)
        return None

def salvar_no_banco(data: dict):
    conn = conectar_banco()
    if conn is None:
        logger.error("Não foi possível conectar ao banco.")
        return

    try:
        cursor = conn.cursor()

        data_registro = datetime.strptime(data['data'], '%Y-%m-%d').date()

        figuras_orgaos = data.get('figuras_orgaos', [])
        if figuras_orgaos:
            categoria = figuras_orgaos[0].get('orgao_publico', "NÃO INFORMADO")
        else:
            categoria = "NÃO INFORMADO"

        participante = f"{categoria} - {data.get('municipio', 'N/A')}"
        cliente = ""
        if figuras_orgaos:
            cliente = f"{figuras_orgaos[0].get('figura_publica', 'N/A')} - {figuras_orgaos[0].get('cargo', 'N/A')}"
        assunto = data.get('assunto', 'NÃO INFORMADO')
        tipo_atendimento = data.get('tipo_atendimento')
        municipio = data.get('municipio')
        colaborador = data.get('colaborador')
        atendimento = data.get('tipo_visita')

        cursor.execute("""
            INSERT INTO planilha_registros (
                data, categoria, participante, cliente, assunto, tipo_atendimento, municipio, colaborador, atendimento
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data_registro, categoria, participante, cliente,
            assunto, tipo_atendimento, municipio, colaborador, atendimento
        ))

        conn.commit()
        logger.info(f"Registro salvo: {data_registro}, {categoria}, {participante}")

    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao salvar na tabela planilha_registros: {e}", exc_info=True)
    finally:
        cursor.close()
        conn.close()



def salvar_demandas_no_banco(dados_gerais: dict, demandas: list[dict]):
    conn = conectar_banco()
    if conn is None:
        logger.error("Não foi possível conectar ao banco para salvar demandas.")
        return

    try:
        cursor = conn.cursor()

        data_str = dados_gerais.get('data')
        if not data_str:
            logger.error("Campo 'data' não informado em dados_gerais.")
            return
        data = datetime.strptime(data_str, '%Y-%m-%d').date()

        municipio = dados_gerais.get('municipio')
        colaborador = dados_gerais.get('colaborador')
        atendimento = dados_gerais.get('tipo_visita')
        tipo_atendimento = dados_gerais.get('tipo_atendimento')

        figuras_orgaos = dados_gerais.get('figuras_orgaos', [])
        categoria = figuras_orgaos[0].get('orgao_publico') if figuras_orgaos else "NÃO INFORMADO"
        participante = f"{categoria} - {municipio}"
        cliente = f"{figuras_orgaos[0].get('figura_publica')} - {figuras_orgaos[0].get('cargo')}" if figuras_orgaos else ""
        assunto = dados_gerais.get('assunto')

        for d in demandas:
            cursor.execute("""
                INSERT INTO planilha_demandas (
                    data, municipio, colaborador, categoria, participante, cliente,
                    assunto, tipo_atendimento, atendimento, demanda, ov, pro, observacao
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data, municipio, colaborador, categoria, participante, cliente,
                assunto, tipo_atendimento, atendimento,
                d.get("demanda"), d.get("ov"), d.get("pro"), d.get("observacao")
            ))

        conn.commit()
        logger.info(f"{len(demandas)} demandas salvas com sucesso.")

    except Exception as e:
        conn.rollback()
        logger.error("Erro ao salvar demandas no banco:", exc_info=True)
    finally:
        cursor.close()
        conn.close()







# --- FUNÇÕES PARA GOOGLE DRIVE ---
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

from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from io import BytesIO

def export_data_to_drive():
    logger.info("Iniciando exportação incremental para planilha 'REUNIAO_PP.xlsx'")
    service = get_drive_service()
    if not service:
        logger.error("Serviço do Google Drive não disponível.")
        return

    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    spreadsheet_name = "REUNIAO_PP.xlsx"

    try:
        # 1. Buscar o arquivo no Google Drive
        query = f"name='{spreadsheet_name}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        if not files:
            raise FileNotFoundError(f"Arquivo '{spreadsheet_name}' não encontrado na pasta do Drive.")

        file_id = files[0]["id"]
        logger.info(f"Arquivo encontrado no Drive com ID: {file_id}")

        # 2. Baixar conteúdo da planilha
        request = service.files().get_media(fileId=file_id)
        fh = BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)

        df_existente = pd.read_excel(fh, engine='openpyxl')
        logger.info(f"Planilha atual carregada. Linhas existentes: {len(df_existente)}")

        # 3. Ler novos dados do banco
        conn = conectar_banco()
        if conn is None:
            raise Exception("Falha ao conectar ao banco.")
        df_novo = pd.read_sql("SELECT * FROM planilha_registros ORDER BY id ASC", conn)
        logger.info(f"Novos registros lidos do banco: {len(df_novo)}")

        # 4. Padronizar colunas e criar df_formatado
        df_novo.columns = [col.upper().strip() for col in df_novo.columns]
        df_formatado = pd.DataFrame()

        df_formatado["DATA"] = df_novo["DATA"]
        df_formatado["CATEGORIA"] = df_novo["CATEGORIA"]
        df_formatado["PARTICIPANTE"] = df_novo["CATEGORIA"] + " - " + df_novo["MUNICIPIO"]
        df_formatado["CLIENTE"] = df_novo["CLIENTE"]
        df_formatado["ASSUNTO"] = df_novo["ASSUNTO"]
        df_formatado["TIPO ATENDIMENTO"] = df_novo["TIPO_ATENDIMENTO"]
        df_formatado["MUNICIPIO"] = df_novo["MUNICIPIO"]
        df_formatado["COLABORADOR"] = df_novo["COLABORADOR"]
        df_formatado["Item Type"] = ""  # Valor vazio
        df_formatado["Path"] = ""       # Valor vazio
        df_formatado["ATENDIMENTO"] = df_novo["ATENDIMENTO"]

        logger.info("Pré-visualização dos dados novos formatados:")
        logger.info(df_formatado.head())

        # 5. Concatenar com dados existentes
        df_final = pd.concat([df_existente, df_formatado], ignore_index=True)
        logger.info(f"Total final de linhas na planilha: {len(df_final)}")

        # 6. Salvar e atualizar no Drive
        excel_buffer = BytesIO()
        df_final.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        media_body = MediaIoBaseUpload(excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            resumable=True
        )

        service.files().update(fileId=file_id, media_body=media_body).execute()
        logger.info(f"Planilha '{spreadsheet_name}' atualizada com sucesso no Drive.")

    except Exception as e:
        logger.error(f"Erro ao exportar dados para planilha do Drive: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()


def export_demandas_to_drive():
    logger.info("Iniciando exportação incremental para planilha 'DEMANDAS_PP.xlsx'")
    service = get_drive_service()
    if not service:
        logger.error("Serviço do Google Drive não disponível.")
        return

    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    spreadsheet_name = "DEMANDAS_PP.xlsx"

    try:
        # 1. Buscar o arquivo no Google Drive
        query = f"name='{spreadsheet_name}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        if not files:
            raise FileNotFoundError(f"Arquivo '{spreadsheet_name}' não encontrado na pasta do Drive.")

        file_id = files[0]["id"]
        logger.info(f"Arquivo encontrado no Drive com ID: {file_id}")

        # 2. Baixar conteúdo da planilha
        request = service.files().get_media(fileId=file_id)
        fh = BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)

        df_existente = pd.read_excel(fh, engine='openpyxl')
        logger.info(f"Planilha atual carregada. Linhas existentes: {len(df_existente)}")

        # 3. Ler novos dados da tabela de demandas
        conn = conectar_banco()
        if conn is None:
            raise Exception("Falha ao conectar ao banco.")
        df_novo = pd.read_sql("SELECT * FROM planilha_demandas ORDER BY id ASC", conn)
        logger.info(f"Novos registros lidos da tabela planilha_demandas: {len(df_novo)}")

        # 4. Padronizar colunas
        df_novo.columns = [col.upper().strip() for col in df_novo.columns]
        df_formatado = pd.DataFrame()

        df_formatado["DATA"] = df_novo["DATA"]
        df_formatado["MUNICIPIO"] = df_novo["MUNICIPIO"]
        df_formatado["COLABORADOR"] = df_novo["COLABORADOR"]
        df_formatado["CATEGORIA"] = df_novo["CATEGORIA"]
        df_formatado["PARTICIPANTE"] = df_novo["PARTICIPANTE"]
        df_formatado["CLIENTE"] = df_novo["CLIENTE"]
        df_formatado["ASSUNTO"] = df_novo["ASSUNTO"]
        df_formatado["TIPO ATENDIMENTO"] = df_novo["TIPO_ATENDIMENTO"]
        df_formatado["ATENDIMENTO"] = df_novo["ATENDIMENTO"]
        df_formatado["DEMANDA"] = df_novo["DEMANDA"]
        df_formatado["OV"] = df_novo["OV"]
        df_formatado["PRO"] = df_novo["PRO"]
        df_formatado["OBSERVACAO"] = df_novo["OBSERVACAO"]

        logger.info("Pré-visualização dos dados formatados de demandas:")
        logger.info(df_formatado.head())

        # 5. Concatenar
        df_final = pd.concat([df_existente, df_formatado], ignore_index=True)
        logger.info(f"Total final de linhas na planilha: {len(df_final)}")

        # 6. Salvar no Drive
        excel_buffer = BytesIO()
        df_final.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        media_body = MediaIoBaseUpload(
            excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            resumable=True
        )

        service.files().update(fileId=file_id, media_body=media_body).execute()
        logger.info(f"Planilha '{spreadsheet_name}' atualizada com sucesso no Drive.")

    except Exception as e:
        logger.error(f"Erro ao exportar dados para planilha de demandas: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()



# Função auxiliar para upload de foto (usada por handlers.py)
async def upload_photo_to_drive(photo_bytes: bytes, filename: str):
    """
    Faz o upload de bytes de uma foto para o Google Drive.
    Retorna o ID do arquivo no Drive ou None em caso de erro.
    """
    drive_service = get_drive_service()
    if not drive_service:
        return None

    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        logger.error("GOOGLE_DRIVE_FOLDER_ID não configurada para upload de foto.")
        return None

    temp_filepath = os.path.join("/tmp", filename)
    try:
        with open(temp_filepath, "wb") as f:
            f.write(photo_bytes)

        file_metadata = {
            'name': filename,
            'parents': [folder_id],
            'mimeType': 'image/jpeg' 
        }
        media = MediaFileUpload(temp_filepath, mimetype='image/jpeg', resumable=True)

        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        logger.error(f"Erro ao fazer upload da foto para o Google Drive: {e}", exc_info=True)
        return None
    finally:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
