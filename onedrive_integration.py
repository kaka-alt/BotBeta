import pandas as pd
import os
from msal import ConfidentialClientApplication
import requests
import logging
from sqlalchemy import create_engine

# Configuração de logging para este módulo
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Carregar credenciais do Azure AD (usando variáveis de ambiente)
CLIENT_ID = os.getenv("MS_CLIENT_ID")
CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
TENANT_ID = os.getenv("MS_TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/Files.ReadWrite"]

# Configurações do banco de dados (também via variáveis de ambiente)
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT")
PGDATABASE = os.getenv("PGDATABASE")

# Inicializa o aplicativo MSAL para obter tokens
msal_app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

def get_db_engine():
    """
    Cria e retorna um objeto SQLAlchemy Engine para conexão com o PostgreSQL.
    """
    if not all([PGUSER, PGPASSWORD, PGHOST, PGPORT, PGDATABASE]):
        logger.error("Credenciais do banco de dados incompletas nas variáveis de ambiente.")
        return None
    try:
        engine = create_engine(f'postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}')
        logger.info("Engine do banco de dados criada com sucesso.")
        return engine
    except Exception as e:
        logger.error(f"Erro ao criar engine do banco de dados: {e}")
        return None

def get_access_token():
    """
    Obtém o token de acesso do Microsoft Graph usando as credenciais do aplicativo.
    """
    try:
        logger.info("Tentando adquirir token de acesso...")
        token_response = msal_app.acquire_token_for_client(scopes=SCOPES)
        if "error" in token_response:
            logger.error(f"Erro ao obter o token: {token_response.get('error_description', 'Descrição não disponível')}")
            return None
        access_token = token_response['access_token']
        logger.info(f"Token de acesso obtido com sucesso (início: {access_token[:20]}...)")
        return access_token
    except Exception as e:
        logger.error(f"Exceção ao obter o token: {e}")
        return None

def upload_to_onedrive(file_path, file_name, onedrive_folder="Git"):
    """
    Envia um arquivo para uma pasta específica no OneDrive.
    """
    access_token = get_access_token()
    if not access_token:
        logger.error("Não foi possível obter o token de acesso para upload.")
        return False

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/octet-stream'
    }

    upload_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{onedrive_folder}/{file_name}:/content"

    try:
        with open(file_path, 'rb') as f:
            logger.info(f"Iniciando upload de '{file_name}' para '{onedrive_folder}' no OneDrive...")
            response = requests.put(upload_url, headers=headers, data=f)
        response.raise_for_status()
        logger.info(f"Arquivo '{file_name}' enviado com sucesso para o OneDrive. Status: {response.status_code}")
        return True
    except FileNotFoundError:
        logger.error(f"Erro: Arquivo local '{file_path}' não encontrado para upload.")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de rede ou API ao enviar '{file_name}' para o OneDrive: {e}")
        if e.response is not None:
            logger.error(f"Resposta de erro do OneDrive: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado durante o upload de '{file_name}': {e}")
        return False

def fetch_and_export_data(table_name, output_filename, onedrive_folder="Git"):
    """
    Busca dados de uma tabela do PostgreSQL, exporta para Excel e envia para o OneDrive.
    """
    engine = get_db_engine()
    if not engine:
        return False

    file_path = f"/tmp/{output_filename}"

    try:
        logger.info(f"Buscando dados da tabela '{table_name}'...")
        df = pd.read_sql(f"SELECT * FROM {table_name}", engine)
        logger.info(f"Dados da tabela '{table_name}' lidos. Total de {len(df)} registros.")

        if df.empty:
            logger.warning(f"A tabela '{table_name}' está vazia. Nenhum arquivo será gerado.")
            return False

        logger.info(f"Exportando dados para Excel: {file_path}")
        df.to_excel(file_path, index=False)
        logger.info(f"Arquivo Excel '{output_filename}' criado localmente.")

        success = upload_to_onedrive(file_path, output_filename, onedrive_folder)

        # Limpa o arquivo temporário após o upload
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Arquivo temporário '{file_path}' removido.")

        return success

    except Exception as e:
        logger.error(f"Erro geral ao processar a tabela '{table_name}': {e}")
        return False