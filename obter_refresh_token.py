# get_onedrive_token.py
# Para ser executado LOCALMENTE, APENAS UMA VEZ, para obter o Refresh Token

import os
from dotenv import load_dotenv
from msal import PublicClientApplication
import webbrowser
import json
from urllib.parse import urlparse, parse_qs

# Carrega as variáveis de ambiente do seu .env local (se existir)
load_dotenv()

# --- Configurações do seu aplicativo Azure AD ---
CLIENT_ID = os.getenv("8adf4f4b-32b8-40d2-a154-27cb3ec71e02")
# Para contas pessoais, o 'authority' pode ser "https://login.microsoftonline.com/common"
# Para contas organizacionais, use f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}"
TENANT_ID = os.getenv("bf86fbdb-f8c2-440e-923c-05a60dc2bc9b")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}" if TENANT_ID else "https://login.microsoftonline.com/common"

REDIRECT_URI = "http://localhost:5000" # Deve ser igual ao que você configurou no Azure AD

# Escopos de recurso. 'offline_access' NÃO deve ser incluído aqui.
# O MSAL lida com ele automaticamente para o refresh token.
SCOPES = ["Files.ReadWrite"] 

print(f"CLIENT_ID: {CLIENT_ID}")
print(f"TENANT_ID: {TENANT_ID}")
print(f"AUTHORITY: {AUTHORITY}")
print(f"REDIRECT_URI: {REDIRECT_URI}")
print(f"SCOPES: {SCOPES}")

if not CLIENT_ID:
    print("Erro: CLIENT_ID não encontrado. Certifique-se de que está definido no seu .env local ou como variável de ambiente.")
    exit()

# Inicializa o aplicativo cliente público
# O cache de token aqui é volátil (em memória), mas útil para o fluxo
# pois ele armazena o token de acesso temporariamente.
app = PublicClientApplication(
    CLIENT_ID, authority=AUTHORITY
)

# Tenta adquirir um token de cache existente (útil se você testar várias vezes sem fechar o script)
accounts = app.get_accounts()
if accounts:
    result = app.acquire_token_silent(SCOPES, account=accounts[0])
else:
    result = None

if not result:
    # Inicia o fluxo de código de autorização
    flow = app.initiate_auth_code_flow(SCOPES, redirect_uri=REDIRECT_URI)
    
    print("\n--- PASSO 1: AUTENTICAÇÃO NO NAVEGADOR ---")
    print("Por favor, abra esta URL no seu navegador para autenticar com sua conta Microsoft:")
    print(flow["auth_uri"])
    
    # Tenta abrir automaticamente no navegador
    try:
        webbrowser.open(flow["auth_uri"])
    except webbrowser.Error:
        print("Não foi possível abrir o navegador automaticamente. Por favor, copie e cole a URL acima manualmente.")

    print("\n--- PASSO 2: COPIAR A URL REDIRECIONADA ---")
    auth_response = input(
        "Após o login e consentimento, seu navegador será redirecionado para uma URL que começa com "
        "'http://localhost:5000/?code=...'.\n"
        "--> COPIE A URL COMPLETA DA BARRA DE ENDEREÇOS DO NAVEGADOR E COLE AQUI: "
    )

    # Extrai o código de autorização da URL
    try:
        parsed_url = urlparse(auth_response)
        query_params = parse_qs(parsed_url.query)
        auth_code = query_params['code'][0]
    except KeyError:
        print("Erro: Não foi possível encontrar o 'code' na URL. Verifique se copiou a URL completa após o redirecionamento.")
        exit()
    except Exception as e:
        print(f"Erro ao processar a URL: {e}")
        exit()

    print("\n--- PASSO 3: TROCAR O CÓDIGO POR TOKENS ---")
    # Troca o código de autorização por um token de acesso e refresh token
    result = app.acquire_token_by_auth_code(
        auth_code,
        scopes=SCOPES, # O MSAL aqui entende que precisa do offline_access para o refresh token
        redirect_uri=REDIRECT_URI
    )

if "access_token" in result:
    print("\n--- AUTENTICAÇÃO BEM-SUCEDIDA! ---")
    print(f"Access Token (válido por ~1 hora): {result['access_token']}")
    
    if "refresh_token" in result:
        print("\n------------------------------------------------------------------------------------------------------")
        print(f"--> REFRESH TOKEN (MUITO IMPORTANTE!): {result['refresh_token']}")
        print("------------------------------------------------------------------------------------------------------")
        print("\n--> POR FAVOR, COPIE O REFRESH TOKEN ACIMA E ADICIONE-O COMO UMA VARIÁVEL DE AMBIENTE NO RAILWAY")
        print("    COM O NOME 'ONEDRIVE_REFRESH_TOKEN'.")
        print("    Você precisará também do CLIENT_ID e TENANT_ID no Railway.")
    else:
        print("Aviso: Refresh Token não encontrado. O Access Token pode expirar sem renovação automática.")
        print("Verifique se o escopo 'offline_access' foi concedido no Azure AD (embora não adicionado explicitamente na lista de SCOPES do MSAL).")

elif "error" in result:
    print(f"\n--- ERRO NA AUTENTICAÇÃO ---")
    print(f"Erro: {result.get('error')}")
    print(f"Descrição: {result.get('error_description')}")
    print(f"Detalhes: {result.get('correlation_id')}")
    if "error_codes" in result:
        print(f"Códigos de erro: {result.get('error_codes')}")