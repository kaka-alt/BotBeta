import os
import json
import logging
import pandas as pd
from datetime import datetime
from io import BytesIO
import pickle
from googleapiclient.discovery import build
import base64
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
import io

# Importação CORRETA para credenciais de conta de serviço
from google.oauth2.service_account import Credentials 
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

# Importar a função de conexão com o banco de dados do utils.py
from utils import conectar_banco # Importa a função conectar_banco

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Variáveis de Ambiente para Google Drive (lidas do ambiente do Render) ---
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_DRIVE_PHOTOS_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_PHOTOS_FOLDER_ID")


if not GOOGLE_CREDENTIALS_JSON:
    logger.error("GOOGLE_CREDENTIALS_JSON não definida. As funções do Drive não poderão ser usadas.")
if not GOOGLE_DRIVE_FOLDER_ID:
    logger.warning("GOOGLE_DRIVE_FOLDER_ID não definida. Arquivos Excel serão salvos na raiz do Drive.")
if not GOOGLE_DRIVE_PHOTOS_FOLDER_ID:
    logger.warning("GOOGLE_DRIVE_PHOTOS_FOLDER_ID não definida. Fotos serão salvas na pasta principal de Excel ou na raiz do Drive.")


# --- Funções Auxiliares para Google Drive ---

def get_drive_service():
    try:
        token_b64 = os.environ.get('TOKEN_PICKLE_B64')
        if not token_b64:
            raise ValueError("Variável de ambiente TOKEN_PICKLE_B64 não configurada.")

        token_bytes = base64.b64decode(token_b64)
        creds = pickle.loads(token_bytes)

        service = build('drive', 'v3', credentials=creds)
        logger.info("Serviço do Google Drive autenticado via variável ambiente TOKEN_PICKLE_B64.")
        return service
    except Exception as e:
        logger.error(f"Erro ao carregar credenciais do token via variável ambiente: {e}", exc_info=True)
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

def ler_excel_drive_em_memoria(service, file_id):
    """Baixa o Excel do Google Drive em memória e retorna o DataFrame."""
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

    # Prepara upload sem sobrescrever metadados (nome, permissões, etc.)
    media = MediaIoBaseUpload(
        excel_bytes,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        resumable=True
    )

    # Atualiza apenas o conteúdo do arquivo existente no Google Drive
    updated_file = service.files().update(
        fileId=file_id,
        media_body=media
        # ⚠️ NÃO incluir 'body=file_metadata' aqui!
    ).execute()

    logger.info(f"✅ Arquivo Excel atualizado com sucesso no Drive (ID: {updated_file.get('id')}).")


# --- FUNÇÃO ATUALIZADA PARA UPLOAD DE EXCEL (XLSX) ---
from googleapiclient.http import MediaIoBaseDownload

def _upload_or_update_excel(service, filename: str, df_novo: pd.DataFrame, folder_id: str = None):
    logger.info("Iniciando processo de atualização da planilha REUNIAO_PP.xlsx...")
    service = get_drive_service()
    file_id = "11xRCRDXkP1h-x70vMK7DubBwh8KvriAn"  # seu ID fixo do Drive

    # Conectar ao banco
    conn = conectar_banco()
    if conn is None:
        logger.error("Não foi possível conectar ao banco de dados.")
        return

    try:
        # 1. Lê os dados do banco
        df_novo = pd.read_sql("SELECT * FROM planilha_registros ORDER BY id DESC", conn)
        logger.info(f"Lendo {len(df_novo)} registros da nova tabela.")

        # 2. Formatar colunas
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
        df_formatado["Item Type"] = ""
        df_formatado["Path"] = ""
        df_formatado["ATENDIMENTO"] = df_novo["ATENDIMENTO"]

        # 3. Lê a planilha atual do Drive
        df_existente = ler_excel_drive_em_memoria(service, file_id)
        logger.info(f"Arquivo existente lido com {len(df_existente)} registros.")

        # 4. Concatena
        df_final = pd.concat([df_existente, df_formatado], ignore_index=True)
        logger.info(f"Arquivo final com {len(df_final)} registros (após concatenação).")

        # 5. Salva de volta no Drive
        salvar_excel_drive_em_memoria(service, file_id, df_final)

    except Exception as e:
        logger.error(f"Erro ao atualizar planilha: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

async def upload_photo_to_drive(file_bytes: bytes, filename: str) -> str | None:
    """
    Faz o upload de uma foto para o Google Drive na pasta de fotos específica.
    Retorna o ID do arquivo no Drive.
    """
    try:
        service = get_drive_service()
        
        target_folder_id = GOOGLE_DRIVE_PHOTOS_FOLDER_ID if GOOGLE_DRIVE_PHOTOS_FOLDER_ID else GOOGLE_DRIVE_FOLDER_ID
        
        file_metadata = {
            'name': filename,
            'mimeType': 'image/jpeg' 
        }
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

def export_data_to_drive():
    conn = None  # Inicializa com None
    try:
        service = get_drive_service()
        folder_id = GOOGLE_DRIVE_FOLDER_ID

        conn = conectar_banco()
        if conn is None:
            return

        df = pd.read_sql("SELECT * FROM planilha_registros ORDER BY id DESC", conn)
        logger.info(f"Lendo {len(df)} registros da nova tabela.")

        _upload_or_update_excel(service, "REUNIAO_PP.xlsx", df, folder_id)

    except Exception as e:
        logger.error(f"Erro ao exportar planilha_registros para Excel: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()