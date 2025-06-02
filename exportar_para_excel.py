import pandas as pd
from sqlalchemy import create_engine
import os
import logging
import psycopg2
import urllib.parse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente do arquivo .env (se existir)
load_dotenv()

# Definição direta da variável DATABASE_PUBLIC_URL (OU use variável de ambiente)
# No Railway, esta variável será injetada automaticamente.
DATABASE_PUBLIC_URL = os.environ.get("DATABASE_PUBLIC_URL")
if not DATABASE_PUBLIC_URL:
    logger.error("Variável de ambiente DATABASE_PUBLIC_URL não encontrada. O aplicativo pode não funcionar corretamente.")
    # Não usamos exit(1) aqui para permitir que o bot inicie, mas com um aviso.
    # Em produção, você pode querer um comportamento mais rigoroso.


def get_database_connection():
    """Conecta ao banco de dados PostgreSQL."""
    try:
        if not DATABASE_PUBLIC_URL:
            logger.error("URL do banco de dados não definida. Não é possível conectar.")
            return None

        parsed_url = urllib.parse.urlparse(DATABASE_PUBLIC_URL)
        dbname = parsed_url.path[1:]  # Remove a primeira barra
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
        return conn
    except psycopg2.Error as e:
        logger.error(f"Erro ao conectar ao banco de dados: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao conectar ao banco de dados: {e}", exc_info=True)
        return None


def upload_file_to_drive(service, filename: str, filepath: str, folder_id: str = None):
    """
    Faz o upload de um arquivo para o Google Drive.

    Args:
        service: O serviço do Google Drive API.
        filename: O nome do arquivo a ser salvo no Drive.
        filepath: O caminho local do arquivo.
        folder_id: (Opcional) O ID da pasta no Drive para salvar o arquivo.
    """

    # Determinar o mimetype com base na extensão do arquivo
    mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'  # Para .xlsx
    if filename.endswith('.csv'):
        mimetype = 'text/csv'
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        mimetype = 'image/jpeg'
    elif filename.endswith('.png'):
        mimetype = 'image/png'

    file_metadata = {'name': filename}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(filepath, mimetype=mimetype, resumable=True)
    try:
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        logger.info(f"Arquivo '{filename}' salvo no Google Drive com ID: '{file.get('id')}'")
    except HttpError as error:
        logger.error(f"Erro ao salvar o arquivo '{filename}' no Google Drive: {error}")
        raise  # Re-lança a exceção para ser tratada na função chamadora
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar o arquivo '{filename}' no Google Drive: {e}", exc_info=True)
        raise


def update_csv_file(service, file_id: str, filepath: str):
    """Atualiza o conteúdo de um arquivo CSV existente no Google Drive."""

    try:
        # Baixar o conteúdo existente
        response = service.files().get_media(fileId=file_id).execute()
        existing_content = response.decode('utf-8')
    except HttpError as error:
        logger.error(f"Erro ao obter conteúdo existente do arquivo CSV: {error}")
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao obter conteúdo existente do arquivo CSV: {e}", exc_info=True)
        raise

    # Ler o conteúdo novo do arquivo local
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            new_content = f.read()
    except FileNotFoundError:
        logger.error(f"Arquivo local '{filepath}' não encontrado.")
        raise

    # Concatenar o conteúdo existente com o novo
    updated_content = existing_content.strip() + '\n' + new_content.strip()

    # Preparar para atualizar o arquivo
    media = MediaFileUpload(filepath, mimetype='text/csv', resumable=True)

    try:
        # Atualizar o arquivo com o conteúdo concatenado
        service.files().update(
            fileId=file_id,
            media_body=media,
        ).execute()
        logger.info(f"Arquivo CSV atualizado no Google Drive.")
    except HttpError as error:
        logger.error(f"Erro ao atualizar o arquivo CSV no Google Drive: {error}")
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao atualizar o arquivo CSV: {e}", exc_info=True)
        raise


def update_or_create_file(service, filename: str, filepath: str, folder_id: str = None):
    """
    Atualiza um arquivo existente no Google Drive ou cria um novo.

    Args:
        service: O serviço do Google Drive API.
        filename: O nome do arquivo.
        filepath: O caminho local do arquivo.
        folder_id: (Opcional) O ID da pasta no Drive.
    """

    try:
        # 1. Buscar se o arquivo já existe
        query = f"name='{filename}'"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        results = service.files().list(q=query, fields='files(id)').execute()
        files = results.get('files', [])

        if files:  # Se o arquivo existe
            file_id = files[0].get('id')
            if filename.endswith('.csv'):
                update_csv_file(service, file_id, filepath)
            else:
                upload_file_to_drive(service, filename, filepath, folder_id)  # Sobrescreve outros tipos
        else:  # Se o arquivo não existe
            upload_file_to_drive(service, filename, filepath, folder_id)

    except HttpError as error:
        logger.error(f"Erro ao atualizar/criar arquivo '{filename}' no Google Drive: {error}")
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao atualizar/criar arquivo '{filename}' no Google Drive: {e}", exc_info=True)
        raise


def export_data_to_drive():
    """Exporta dados do banco de dados para arquivos e salva no Google Drive."""

    conn = get_database_connection()
    if conn is None:
        logger.error("Não foi possível conectar ao banco de dados para exportar dados.")
        return

    try:
        logger.info("Conectado ao banco de dados para exportação.")

        # Exportar tabelas usando pandas com a conexão psycopg2
        df_registros = pd.read_sql("SELECT * FROM registros", conn)
        df_demandas = pd.read_sql("SELECT * FROM demandas", conn)

        # Salvar os arquivos localmente (temporariamente)
        local_path = "/tmp"  # Use um diretório temporário
        os.makedirs(local_path, exist_ok=True)
        registros_filename = "registros.xlsx"
        demandas_filename = "demandas.xlsx"
        registros_filepath = os.path.join(local_path, registros_filename)
        demandas_filepath = os.path.join(local_path, demandas_filename)

        df_registros.to_excel(registros_filepath, index=False)
        logger.info(f"Dados de registros salvos localmente em: {registros_filepath}")
        df_demandas.to_excel(demandas_filepath, index=False)
        logger.info(f"Dados de demandas salvos localmente em: {demandas_filepath}")

        # Configurar as credenciais do Google Drive
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            logger.error("Variável de ambiente GOOGLE_CREDENTIALS_JSON não encontrada. Não é possível salvar no Google Drive.")
            return

        creds_info = eval(creds_json)
        creds = Credentials.from_authorized_user_info(info=creds_info, scopes=['https://www.googleapis.com/auth/drive.file'])
        service = build('drive', 'v3', credentials=creds)

        # Obter o ID da pasta do Google Drive da variável de ambiente
        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

        # Salvar no Google Drive (atualizar ou criar)
        update_or_create_file(service, registros_filename, registros_filepath, folder_id)
        update_or_create_file(service, demandas_filename, demandas_filepath, folder_id)

    except Exception as e:
        logger.error(f"Erro ao exportar dados e salvar no Google Drive: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
            logger.info("Conexão com o banco de dados fechada após exportação.")

    # Limpar arquivos temporários
    if os.path.exists(registros_filepath):
        os.remove(registros_filepath)
        logger.info(f"Arquivo local temporário '{registros_filepath}' removido.")
    if os.path.exists(demandas_filepath):
        os.remove(demandas_filepath)
        logger.info(f"Arquivo local temporário '{demandas_filepath}' removido.")


if __name__ == '__main__':
    # Este bloco só será executado se você rodar exportar_para_excel.py diretamente
    # No contexto do Railway, ele será importado e suas funções chamadas.
    logger.info("Executando exportar_para_excel.py diretamente.")
    export_data_to_drive()