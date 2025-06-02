from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES = ['https://www.googleapis.com/auth/drive.file']

try:
    flow = InstalledAppFlow.from_client_secrets_file(
        r'C:\\Users\\E712155\\OneDrive - EDP\\DadosBot\\client_secret.json', SCOPES)  
    creds = flow.run_local_server(port=0)

    # Salve as credenciais (token) para usar no Railway
    print(f"Token: {creds.to_json()}")

except FileNotFoundError:
    print(f"Erro: O arquivo client_secret.json não foi encontrado no caminho: "
          r'C:\\Users\\E712155\\OneDrive - EDP\\DadosBot\\client_secret.json')
    print("Certifique-se de que o arquivo existe e o caminho está correto.")
except Exception as e:
    print(f"Ocorreu um erro inesperado: {e}")