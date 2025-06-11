import json
import os
import pandas as pd
from telegram import InlineKeyboardButton
from datetime import datetime
from config import *
from globals import user_data
import psycopg2 
import urllib.parse
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

# Funções utilitárias para o bot

def build_menu(buttons, n_cols, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if footer_buttons:
        menu.append(footer_buttons)
    return menu

def botoes_pagina(lista, pagina, prefix="", por_pagina=5):
    inicio = pagina * por_pagina
    fim = inicio + por_pagina
    sublista = lista[inicio:fim]

    buttons = [
        [InlineKeyboardButton(text=item, callback_data=f"{prefix}{item}")]
        for item in sublista
    ]

    buttons.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data=f"{prefix}voltar"),
        InlineKeyboardButton("➡️ Próximo", callback_data=f"{prefix}proximo"),
    ])
    buttons.append([
        InlineKeyboardButton("📝 Inserir manualmente", callback_data=f"{prefix}inserir_manual"),
        InlineKeyboardButton("🔄 Refazer busca", callback_data=f"{prefix}refazer_busca"),
    ])

    return buttons, pagina

# Lista de Órgãos Públicos
def ler_orgaos_csv():
    # Adicionado tratamento para arquivo inexistente
    if not os.path.exists(CSV_ORGAOS):
        logger.warning(f"CSV de órgãos não encontrado em {CSV_ORGAOS}. Criando um DataFrame vazio.")
        return pd.DataFrame(columns=['nome'])
    df = pd.read_csv(CSV_ORGAOS)
    return df['nome'].dropna().tolist()

def salvar_orgao(novo_orgao: str):
    caminho_orgaos = CSV_ORGAOS

    os.makedirs(os.path.dirname(caminho_orgaos), exist_ok=True)

    novo_orgao = novo_orgao.strip()

    orgaos_existentes = set()
    if os.path.exists(caminho_orgaos):
        with open(caminho_orgaos, mode='r', encoding='utf-8') as f:
            orgaos_existentes = {linha.strip() for linha in f.readlines()}

    if novo_orgao and novo_orgao not in orgaos_existentes:
        with open(caminho_orgaos, mode='a', newline='', encoding='utf-8') as f:
            f.write(f"{novo_orgao}\n")

# Lista Assuntos
def ler_assuntos_csv():
    # Adicionado tratamento para arquivo inexistente
    if not os.path.exists(CSV_ASSUNTOS):
        logger.warning(f"CSV de assuntos não encontrado em {CSV_ASSUNTOS}. Criando um DataFrame vazio.")
        return pd.DataFrame(columns=['assunto'])
    df = pd.read_csv(CSV_ASSUNTOS)
    return df['assunto'].dropna().tolist()

def salvar_assunto(novo_assunto: str):
    caminho_assuntos = CSV_ASSUNTOS

    os.makedirs(os.path.dirname(caminho_assuntos), exist_ok=True)

    novo_assunto = novo_assunto.strip()

    assuntos_existentes = set()
    if os.path.exists(caminho_assuntos):
        with open(caminho_assuntos, mode='r', encoding='utf-8') as f:
            assuntos_existentes = {linha.strip() for linha in f.readlines()}

    if novo_assunto and novo_assunto not in assuntos_existentes:
        with open(caminho_assuntos, mode='a', newline='', encoding='utf-8') as f:
            f.write(f"{novo_assunto}\n")

# --- FUNÇÕES PARA POSTGRESQL ---
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

def salvar_no_banco(data: dict):
    """Salva os dados no banco de dados PostgreSQL, incluindo múltiplas figuras/órgãos."""

    conn = conectar_banco() 
    if conn is None:
        logger.error("Não foi possível conectar ao banco de dados para salvar a ocorrência.")
        return 

    cursor = conn.cursor() 

    try:
        data_str = data.get('data')
        data_date = datetime.strptime(data_str, '%Y-%m-%d').date() if isinstance(data_str, str) else data_str

        cursor.execute("""
            INSERT INTO registros (
                colaborador, tipo_visita, assunto, municipio, data, foto
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id; 
        """, (
            data.get('colaborador'), data.get('tipo_visita'),
            data.get('assunto'), data.get('municipio'),
            data_date, 
            data.get('foto')
        ))
        registro_id = cursor.fetchone()[0] 
        logger.info(f"Ocorrência principal salva. Registro ID: {registro_id}")

        figuras_orgaos = data.get('figuras_orgaos', [])
        if figuras_orgaos:
            for fo_set in figuras_orgaos:
                cursor.execute("""
                    INSERT INTO ocorrencias_figuras_orgaos (
                        registro_id, orgao_publico, figura_publica, cargo
                    ) VALUES (%s, %s, %s, %s)
                """, (
                    registro_id, 
                    fo_set.get('orgao_publico'),
                    fo_set.get('figura_publica'),
                    fo_set.get('cargo')
                ))
            logger.info(f"{len(figuras_orgaos)} figuras/órgãos salvos para o Registro ID: {registro_id}")
        else:
            logger.info(f"Nenhuma figura/órgão para salvar para o Registro ID: {registro_id}")


        demandas = data.get('demandas', [])
        if demandas:
            for demanda in demandas:
                cursor.execute("""
                    INSERT INTO demandas (
                        registro_id, texto, ov, pro, observacao
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    registro_id, 
                    demanda.get('texto'), demanda.get('ov'),
                    demanda.get('pro'), demanda.get('observacao')
                ))
            logger.info(f"{len(demandas)} demandas salvas para o Registro ID: {registro_id}")
        else:
            logger.info(f"Nenhuma demanda para salvar para o Registro ID: {registro_id}")

        conn.commit() 
        logger.info(f"Transação para o Registro ID: {registro_id} concluída no PostgreSQL!")

    except psycopg2.Error as e:
        conn.rollback() 
        logger.error(f"Erro ao salvar no banco de dados para o Registro ID: {registro_id}. Detalhes: {e}", exc_info=True)
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro inesperado ao salvar no banco de dados para o Registro ID: {registro_id}. Detalhes: {e}", exc_info=True)
    finally:
        cursor.close() 
        conn.close() 

# --- FUNÇÕES PARA GOOGLE DRIVE ---
def get_drive_service():
    """Autentica com a API do Google Drive usando credenciais JSON."""
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            raise ValueError("GOOGLE_CREDENTIALS_JSON não está configurada nas variáveis de ambiente.")
        
        info = json.loads(creds_json)
        credentials = Credentials.from_info(info, scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=credentials)
        logger.info("Serviço do Google Drive autenticado com sucesso.")
        return service
    except Exception as e:
        logger.error(f"Erro ao obter serviço do Google Drive: {e}", exc_info=True)
        return None

def export_data_to_drive():
    """
    Exporta dados das tabelas 'registros', 'demandas' e 'ocorrencias_figuras_orgaos' para 
    planilhas Excel no Google Drive.
    """
    logger.info("Iniciando exportação de dados para o Google Drive...")
    drive_service = get_drive_service()
    if not drive_service:
        logger.error("Serviço do Google Drive não disponível, abortando exportação.")
        return

    conn = conectar_banco()
    if conn is None:
        logger.error("Não foi possível conectar ao banco de dados para exportação.")
        return

    excel_path = None 

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
        logger.debug(f"Conteúdo de df_figuras_orgaos:\n{df_figuras_orgaos.head()}") # Mostrar as primeiras linhas para debug

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

    except Exception as e:
        logger.error(f"Erro durante a exportação para o Google Drive: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
        if excel_path and os.path.exists(excel_path):
            os.remove(excel_path)
            logger.info(f"Arquivo temporário '{excel_path}' removido.")

# Função auxiliar para upload de foto (usada por handlers.py)
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
