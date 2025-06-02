import pandas as pd
from sqlalchemy import create_engine
import os
import logging
import psycopg2
import urllib.parse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload # Importar MediaFileUpload
from dotenv import load_dotenv

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente do arquivo .env (se existir)
load_dotenv()

# Definição direta da variável DATABASE_PUBLIC_URL (OU use variável de ambiente)
# No Railway, esta variável será injetada automaticamente.
DATABASE_PUBLIC_URL_DIRETA = os.environ.get("DATABASE_PUBLIC_URL")
if not DATABASE_PUBLIC_URL_DIRETA:
    logger.error("Variável de ambiente DATABASE_PUBLIC_URL não encontrada. O aplicativo pode não funcionar corretamente.")
    # Não usamos exit(1) aqui para permitir que o bot inicie, mas com um aviso.
    # Em produção, você pode querer um comportamento mais rigoroso.

def conectar_banco():
    """Conecta ao banco de dados PostgreSQL."""
    try:
        url_str = DATABASE_PUBLIC_URL_DIRETA
        if not url_str:
            logger.error("URL do banco de dados não definida. Não é possível conectar.")
            return None

        parsed_url = urllib.parse.urlparse(url_str)
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

def salvar_no_google_drive(filename: str, filepath: str):
    """Salva um arquivo no Google Drive."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        logger.error("Variável de ambiente GOOGLE_CREDENTIALS_JSON não encontrada. Não é possível salvar no Google Drive.")
        return

    try:
        # eval() é usado para converter a string JSON em um dicionário Python.
        # Tenha certeza de que GOOGLE_CREDENTIALS_JSON contém JSON válido.
        creds_info = eval(creds_json)
        creds = Credentials.from_authorized_user_info(info=creds_info, scopes=['https://www.googleapis.com/auth/drive.file'])

        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': filename}
        
        # Opcional: Se quiser salvar em uma pasta específica, adicione o ID da pasta.
        # Exemplo: file_metadata['parents'] = ['ID_DA_SUA_PASTA_NO_DRIVE']

        # --- CORREÇÃO AQUI: Usar MediaFileUpload ---
        # Determinar o mimetype com base na extensão do arquivo
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' # Para .xlsx
        if filename.endswith('.csv'):
            mimetype = 'text/csv'
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            mimetype = 'image/jpeg'
        elif filename.endswith('.png'):
            mimetype = 'image/png'
        # Adicione mais mimetypes conforme necessário

        media = MediaFileUpload(filepath, mimetype=mimetype) # Criar o objeto MediaFileUpload

        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        
        logger.info(f"Arquivo '{filename}' salvo no Google Drive com ID: '{file.get('id')}'")
    except HttpError as error:
        logger.error(f"Ocorreu um erro ao salvar no Google Drive: {error}")
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar arquivo no Google Drive: {e}", exc_info=True)
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Arquivo local temporário '{filepath}' removido.")

def exportar_dados_localmente():
    """Exporta dados do banco de dados para arquivos Excel locais e salva no Google Drive."""
    conn = conectar_banco()
    if conn is None:
        logger.error("Não foi possível conectar ao banco de dados para exportar dados.")
        return

    try:
        logger.info("Conectado ao banco de dados para exportação.")

        # Exportar tabelas usando pandas com a conexão psycopg2
        df_registros = pd.read_sql("SELECT * FROM registros", conn)
        df_demandas = pd.read_sql("SELECT * FROM demandas", conn)

        # Salvar os arquivos localmente (temporariamente no diretório /tmp do Railway)
        local_path = "/tmp"
        os.makedirs(local_path, exist_ok=True)
        registros_filename = "registros.xlsx"
        demandas_filename = "demandas.xlsx"
        registros_filepath = os.path.join(local_path, registros_filename)
        demandas_filepath = os.path.join(local_path, demandas_filename)

        df_registros.to_excel(registros_filepath, index=False)
        logger.info(f"Dados de registros salvos localmente em: {registros_filepath}")
        df_demandas.to_excel(demandas_filepath, index=False)
        logger.info(f"Dados de demandas salvos localmente em: {demandas_filepath}")

        # Salvar no Google Drive
        salvar_no_google_drive(registros_filename, registros_filepath)
        salvar_no_google_drive(demandas_filename, demandas_filepath)

    except Exception as e:
        logger.error(f"Erro ao exportar dados e salvar no Google Drive: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
            logger.info("Conexão com o banco de dados fechada após exportação.")

if __name__ == '__main__':
    # Este bloco só será executado se você rodar exportar_para_excel.py diretamente
    # No contexto do Railway, ele será importado e suas funções chamadas.
    logger.info("Executando exportar_para_excel.py diretamente.")
    exportar_dados_localmente()
