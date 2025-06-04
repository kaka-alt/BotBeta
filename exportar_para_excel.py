import os
import json
import logging
import pandas as pd
from datetime import datetime
from io import BytesIO

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Variáveis de Ambiente para Google Drive (lidas do ambiente do Render) ---
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")
# Pasta principal para CSVs (já existente)
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
# NOVO: Pasta específica para fotos
GOOGLE_DRIVE_PHOTOS_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_PHOTOS_FOLDER_ID")


if not GOOGLE_CREDENTIALS_JSON:
    logger.error("GOOGLE_CREDENTIALS_JSON não definida. As funções do Drive não poderão ser usadas.")
if not GOOGLE_DRIVE_FOLDER_ID:
    logger.warning("GOOGLE_DRIVE_FOLDER_ID não definida. CSVs serão salvos na raiz do Drive.")
if not GOOGLE_DRIVE_PHOTOS_FOLDER_ID:
    logger.warning("GOOGLE_DRIVE_PHOTOS_FOLDER_ID não definida. Fotos serão salvas na pasta principal de CSVs ou na raiz do Drive.")


# --- Funções Auxiliares para Google Drive ---

def get_drive_service():
    """
    Autentica e retorna o objeto de serviço do Google Drive API.
    Lê as credenciais da variável de ambiente GOOGLE_CREDENTIALS_JSON.
    """
    if not GOOGLE_CREDENTIALS_JSON:
        raise ValueError("GOOGLE_CREDENTIALS_JSON não configurado. Não é possível autenticar no Google Drive.")
    
    try:
        creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_authorized_user_info(info=creds_info, scopes=['https://www.googleapis.com/auth/drive']) 
        service = build('drive', 'v3', credentials=creds)
        logger.info("Serviço do Google Drive API autenticado com sucesso.")
        return service
    except Exception as e:
        logger.error(f"Erro ao autenticar no Google Drive: {e}", exc_info=True)
        raise

def _get_file_id_by_name(service, filename: str, folder_id: str = None) -> str | None:
    """
    Busca o ID de um arquivo pelo nome em uma pasta específica do Google Drive.
    Retorna o ID do arquivo se encontrado, caso contrário, retorna None.
    """
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

def _download_file_content(service, file_id: str) -> str:
    """
    Baixa o conteúdo de um arquivo do Google Drive e o retorna como uma string UTF-8.
    """
    try:
        response = service.files().get_media(fileId=file_id).execute()
        logger.info(f"Conteúdo do arquivo {file_id} baixado com sucesso.")
        return response.decode('utf-8')
    except HttpError as error:
        logger.error(f"Erro ao baixar conteúdo do arquivo {file_id}: {error}")
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao baixar conteúdo do arquivo {file_id}: {e}", exc_info=True)
        raise

def _upload_or_update_csv(service, filename: str, df: pd.DataFrame, folder_id: str = None):
    """
    Cria um novo arquivo CSV no Google Drive ou sobrescreve um existente
    com o conteúdo do DataFrame fornecido.
    """
    file_id = _get_file_id_by_name(service, filename, folder_id)
    
    csv_content_bytes = df.to_csv(index=False, encoding='utf-8').encode('utf-8')
    
    media_body = MediaIoBaseUpload(BytesIO(csv_content_bytes),
                                   mimetype='text/csv',
                                   resumable=True)

    if file_id:
        try:
            service.files().update(fileId=file_id, media_body=media_body).execute()
            logger.info(f"Arquivo CSV '{filename}' atualizado no Google Drive (ID: {file_id}).")
        except HttpError as error:
            logger.error(f"Erro ao atualizar arquivo CSV '{filename}' (ID: {file_id}): {error}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao atualizar arquivo CSV '{filename}' (ID: {file_id}): {e}", exc_info=True)
            raise
    else:
        file_metadata = {'name': filename, 'mimeType': 'text/csv'}
        if folder_id:
            file_metadata['parents'] = [folder_id]
        try:
            file = service.files().create(body=file_metadata, media_body=media_body, fields='id').execute()
            logger.info(f"Arquivo CSV '{filename}' criado no Google Drive com ID: '{file.get('id')}'")
        except HttpError as error:
            logger.error(f"Erro ao criar arquivo CSV '{filename}': {error}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao criar arquivo CSV '{filename}': {e}", exc_info=True)
            raise

# --- Função para upload de fotos (AGORA USANDO GOOGLE_DRIVE_PHOTOS_FOLDER_ID) ---
async def upload_photo_to_drive(file_bytes: bytes, filename: str) -> str | None:
    """
    Faz o upload de uma foto para o Google Drive na pasta de fotos específica.
    Retorna o ID do arquivo no Drive.
    """
    try:
        service = get_drive_service()
        
        # Usa a pasta específica para fotos, ou a pasta principal se não definida
        target_folder_id = GOOGLE_DRIVE_PHOTOS_FOLDER_ID if GOOGLE_DRIVE_PHOTOS_FOLDER_ID else GOOGLE_DRIVE_FOLDER_ID
        
        file_metadata = {
            'name': filename,
            'mimeType': 'image/jpeg' # Ou 'image/png' dependendo do formato da foto
        }
        if target_folder_id:
            file_metadata['parents'] = [target_folder_id] # Define a pasta de destino

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

# --- Sua função export_data_to_drive existente ---
def export_data_to_drive():
    """
    Esta é a sua função existente para exportar dados para CSVs no Google Drive.
    Mantenha sua lógica original aqui.
    """
    logger.info("Executando a função export_data_to_drive (lógica de CSV).")
    try:
        service = get_drive_service()
        # Para CSVs, ainda usa a pasta principal GOOGLE_DRIVE_FOLDER_ID
        folder_id_csv = GOOGLE_DRIVE_FOLDER_ID 
        
        # --- Sua lógica original de exportação de CSVs para o Drive aqui ---
        # Exemplo:
        # data_registros = {'coluna1': ['valor1'], 'coluna2': ['valor2']}
        # df_registros = pd.DataFrame(data_registros)
        # _upload_or_update_csv(service, "registros.csv", df_registros, folder_id_csv)

        # data_demandas = {'colunaA': ['valorA'], 'colunaB': ['valorB']}
        # df_demandas = pd.DataFrame(data_demandas)
        # _upload_or_update_csv(service, "demandas.csv", df_demandas, folder_id_csv)
        
        logger.info("Lógica de exportação de CSVs para o Drive concluída.")
    except Exception as e:
        logger.error(f"Erro na função export_data_to_drive: {e}", exc_info=True)
        raise

