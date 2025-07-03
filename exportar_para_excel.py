import os
import json
import logging
import pandas as pd
from datetime import datetime
from io import BytesIO
import base64
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Variáveis de Ambiente para Google Drive ---
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_DRIVE_PHOTOS_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_PHOTOS_FOLDER_ID")

if not GOOGLE_CREDENTIALS_JSON:
    logger.error("GOOGLE_CREDENTIALS_JSON não definida. As funções do Drive não poderão ser usadas.")
if not GOOGLE_DRIVE_FOLDER_ID:
    logger.warning("GOOGLE_DRIVE_FOLDER_ID não definida. Arquivos Excel serão salvos na raiz do Drive.")
if not GOOGLE_DRIVE_PHOTOS_FOLDER_ID:
    logger.warning("GOOGLE_DRIVE_PHOTOS_FOLDER_ID não definida. Fotos serão salvas na pasta principal ou raiz do Drive.")

# --- Funções Google Drive ---

def get_drive_service():
    try:
        # Carrega credenciais do JSON armazenado em variável de ambiente (string JSON)
        info = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(
            info,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=creds)
        logger.info("Serviço do Google Drive autenticado via GOOGLE_CREDENTIALS_JSON.")
        return service
    except Exception as e:
        logger.error(f"Erro ao carregar credenciais do Google Drive: {e}", exc_info=True)
        raise

def _get_file_id_by_name(service, filename: str, folder_id: str = None) -> str | None:
    query = f"name='{filename}' and trashed=false"
    if folder_id:
        query += f" and '{folder_id}' in parents"
    try:
        results = service.files().list(q=query, fields='files(id)').execute()
        files = results.get('files', [])
        if files:
            logger.info(f"Arquivo '{filename}' encontrado no Drive com ID: {files[0]['id']}.")
            return files[0]['id']
        logger.info(f"Arquivo '{filename}' não encontrado no Drive.")
        return None
    except HttpError as error:
        logger.error(f"Erro ao buscar arquivo '{filename}' no Google Drive: {error}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar arquivo '{filename}': {e}", exc_info=True)
        return None

def ler_excel_drive_em_memoria(service, file_id):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    logger.info("Arquivo Excel carregado da memória com sucesso.")
    return pd.read_excel(fh)

def salvar_excel_drive_em_memoria(service, file_id, df_final):
    from pandas import ExcelWriter
    excel_bytes = io.BytesIO()
    with ExcelWriter(excel_bytes, engine="xlsxwriter") as writer:
        df_final.to_excel(writer, index=False, sheet_name="REUNIOES")
    excel_bytes.seek(0)

    media = MediaIoBaseUpload(
        excel_bytes,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        resumable=True
    )

    updated_file = service.files().update(
        fileId=file_id,
        media_body=media
    ).execute()

    logger.info(f"✅ Arquivo Excel atualizado com sucesso no Drive (ID: {updated_file.get('id')}).")

def upload_photo_to_drive(file_bytes: bytes, filename: str) -> str | None:
    try:
        service = get_drive_service()
        target_folder_id = GOOGLE_DRIVE_PHOTOS_FOLDER_ID if GOOGLE_DRIVE_PHOTOS_FOLDER_ID else GOOGLE_DRIVE_FOLDER_ID
        file_metadata = {'name': filename, 'mimeType': 'image/jpeg'}
        if target_folder_id:
            file_metadata['parents'] = [target_folder_id]

        media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype='image/jpeg', resumable=True)
        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        file_id = uploaded_file.get('id')
        logger.info(f"Foto '{filename}' enviada para o Google Drive (pasta: {target_folder_id}) com ID: {file_id}")
        return file_id
    except HttpError as error:
        logger.error(f"Erro HTTP ao fazer upload da foto para o Drive: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao fazer upload da foto para o Drive: {e}", exc_info=True)
        return None

def _upload_or_update_excel(service, filename: str, df_novo: pd.DataFrame, folder_id: str = None):
    logger.info(f"Iniciando atualização da planilha '{filename}' no Drive...")

    file_id = _get_file_id_by_name(service, filename, folder_id)
    if not file_id:
        logger.error(f"Arquivo '{filename}' não encontrado no Drive. Impossível atualizar.")
        return

    try:
        df_existente = ler_excel_drive_em_memoria(service, file_id)
        logger.info(f"Planilha existente possui {len(df_existente)} registros.")

        df_final = pd.concat([df_existente, df_novo], ignore_index=True)
        logger.info(f"Planilha final com {len(df_final)} registros após concatenação.")

        salvar_excel_drive_em_memoria(service, file_id, df_final)

    except Exception as e:
        logger.error(f"Erro ao atualizar planilha '{filename}': {e}", exc_info=True)

# Função para exportar DataFrame direto para Drive sem banco
def exportar_dataframe_para_drive(df: pd.DataFrame, filename: str, folder_id: str = None):
    try:
        service = get_drive_service()
        _upload_or_update_excel(service, filename, df, folder_id)
    except Exception as e:
        logger.error(f"Erro ao exportar dataframe para '{filename}': {e}", exc_info=True)
