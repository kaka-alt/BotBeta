import json
import os
import pandas as pd
from datetime import datetime
import psycopg2 
import urllib.parse
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

# --- FUNÇÕES PARA CONEXÃO COM O BANCO DE DADOS E GOOGLE DRIVE ---

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

def get_drive_service():
    """Autentica com a API do Google Drive usando credenciais JSON."""
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            raise ValueError("GOOGLE_CREDENTIALS_JSON não está configurada nas variáveis de ambiente.")
        
        info = json.loads(creds_json)
        credentials = Credentials.from_info(info, scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=credentials)
        logger.info("Serviço do Google Drive API autenticado com sucesso.")
        return service
    except Exception as e:
        logger.error(f"Erro ao obter serviço do Google Drive: {e}", exc_info=True)
        return None

# --- FUNÇÕES PRINCIPAIS DE EXPORTAÇÃO ---

def export_data_to_drive():
    """
    Exporta dados das tabelas 'registros', 'demandas' e 'ocorrencias_figuras_orgaos' para 
    planilhas Excel em um único arquivo no Google Drive.
    """
    logger.info("Iniciando exportação de dados do PostgreSQL para arquivos Excel (XLSX) no Google Drive.")
    
    drive_service = get_drive_service()
    if not drive_service:
        logger.error("Serviço do Google Drive não disponível, abortando exportação.")
        return

    conn = conectar_banco()
    if conn is None:
        logger.error("Não foi possível conectar ao banco de dados para exportação.")
        return

    excel_path = None # Inicializa para garantir que seja limpo no finally

    try:
        # Consultar dados da tabela 'registros'
        df_registros = pd.read_sql("SELECT * FROM registros ORDER BY id DESC", conn)
        logger.info(f"DataFrame 'registros' carregado. Linhas: {len(df_registros)}.")

        # Consultar dados da tabela 'demandas'
        df_demandas = pd.read_sql("SELECT * FROM demandas ORDER BY id DESC", conn)
        logger.info(f"DataFrame 'demandas' carregado. Linhas: {len(df_demandas)}.")

        # Consultar dados da nova tabela 'ocorrencias_figuras_orgaos'
        df_figuras_orgaos = pd.read_sql("SELECT * FROM ocorrencias_figuras_orgaos ORDER BY id DESC", conn)
        logger.info(f"DataFrame 'ocorrencias_figuras_orgaos' carregado. Linhas: {len(df_figuras_orgaos)}.")
        logger.debug(f"Conteúdo de df_figuras_orgaos (primeiras 5 linhas):\n{df_figuras_orgaos.head()}") 

        # Criar um arquivo Excel com múltiplas planilhas
        excel_file_name = f"Dados_Ocorrencias_Bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        excel_path = os.path.join("/tmp", excel_file_name) 

        with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
            if not df_registros.empty:
                df_registros.to_excel(writer, sheet_name='Ocorrencias Principais', index=False)
                logger.info("Planilha 'Ocorrencias Principais' adicionada ao Excel.")
            else:
                logger.warning("DataFrame de 'Ocorrencias Principais' vazio. Planilha não será criada ou estará vazia.")
            
            if not df_figuras_orgaos.empty:
                df_figuras_orgaos.to_excel(writer, sheet_name='Figuras e Orgaos', index=False)
                logger.info("Planilha 'Figuras e Orgaos' adicionada ao Excel.")
            else:
                logger.warning("DataFrame de 'Figuras e Orgaos' vazio. Planilha não será criada ou estará vazia.")

            if not df_demandas.empty:
                df_demandas.to_excel(writer, sheet_name='Demandas', index=False)
                logger.info("Planilha 'Demandas' adicionada ao Excel.")
            else:
                logger.warning("DataFrame de 'Demandas' vazio. Planilha não será criada ou estará vazia.")

        logger.info(f"Arquivo Excel temporário '{excel_file_name}' criado em {excel_path}.")

        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        if not folder_id:
            raise ValueError("GOOGLE_DRIVE_FOLDER_ID não está configurada nas variáveis de ambiente.")

        file_metadata = {
            'name': excel_file_name,
            'parents': [folder_id],
            'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        media = MediaFileUpload(excel_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', resumable=True)

        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        logger.info(f"Arquivo '{excel_file_name}' exportado para o Google Drive. ID: {file.get('id')}")
        logger.info("Exportação de arquivos Excel (XLSX) do PostgreSQL para o Drive concluída com sucesso.")

    except Exception as e:
        logger.error(f"Erro durante a exportação para o Google Drive: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
        # Limpa o arquivo temporário
        if excel_path and os.path.exists(excel_path):
            os.remove(excel_path)
            logger.info(f"Arquivo temporário '{excel_path}' removido.")


# --- FUNÇÃO AUXILIAR PARA UPLOAD DE FOTO ---

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
