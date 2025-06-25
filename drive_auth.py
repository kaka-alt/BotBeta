import os
import pickle
from io import BytesIO
import logging

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def autenticar():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    logger.info("Autenticado com sucesso no Google Drive")
    return creds

def upload_excel_para_drive(nome_arquivo: str, df: pd.DataFrame, pasta_id: str = None):
    creds = autenticar()
    service = build('drive', 'v3', credentials=creds)

    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)

    metadata = {'name': nome_arquivo}
    if pasta_id:
        metadata['parents'] = [pasta_id]

    media = MediaIoBaseUpload(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', resumable=True)

    try:
        arquivo = service.files().create(body=metadata, media_body=media, fields='id').execute()
        logger.info(f"Arquivo '{nome_arquivo}' enviado para o Drive com ID: {arquivo.get('id')}")
        return arquivo.get('id')
    except Exception as e:
        logger.error(f"Erro ao enviar arquivo para o Drive: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    # Teste rápido
    df_teste = pd.DataFrame({'Teste':[1,2,3]})
    upload_excel_para_drive('teste_bot.xlsx', df_teste)
