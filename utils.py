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
import csv

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

# Salvamento de CSV em pasta externa (Função original que não está sendo chamada diretamente no fluxo principal)
def salvar_csv(data: dict):
    logger.info(f"DADOS A SEREM SALVOS (salvar_csv): {data}") # Alterado para logger.info

    ano, semana, _ = datetime.now().isocalendar()
    pasta_data = os.path.join(CAMINHO_BASE, "data")
    pasta_backup = os.path.join(pasta_data, "backup")
    pasta_semanal = os.path.join(pasta_data, "semanal")
    os.makedirs(pasta_semanal, exist_ok=True)
    os.makedirs(pasta_data, exist_ok=True)
    os.makedirs(pasta_backup, exist_ok=True)

    caminho_principal = CSV_REGISTRO
    caminho_semanal = os.path.join(pasta_semanal, f"{ano}-semana-{semana}-registros.csv")
    data_hoje = datetime.now().strftime('%Y-%m-%d')
    caminho_backup = os.path.join(pasta_backup, f"{data_hoje}-backup.csv")

    cabecalho = [
        'colaborador', 'orgao_publico', 'figura_publica', 'cargo',
        'assunto', 'municipio', 'data', 'foto', 'tipo_visita', # ADICIONADO: 'tipo_visita'
        'demanda', 'ov', 'pro', 'observacao'
    ]

    def escrever_linhas_csv(caminho_arquivo):
        arquivo_existe = os.path.isfile(caminho_arquivo)
        with open(caminho_arquivo, mode='a', newline='', encoding='utf-8') as arquivo:
            writer = csv.DictWriter(arquivo, fieldnames=cabecalho)
            if not arquivo_existe:
                writer.writeheader()
            demandas = data.get('demandas')
            if demandas:
                for demanda in demandas:
                    linha = {
                        'colaborador': data.get('colaborador'),
                        'orgao_publico': data.get('orgao_publico'),
                        'figura_publica': data.get('figura_publica'),
                        'cargo': data.get('cargo'),
                        'assunto': data.get('assunto'),
                        'municipio': data.get('municipio'),
                        'data': data.get('data'),
                        'foto': data.get('foto'),
                        'tipo_visita': data.get('tipo_visita'), # ADICIONADO: 'tipo_visita'
                        'demanda': demanda.get('texto'),
                        'ov': demanda.get('ov'),
                        'pro': demanda.get('pro'),
                        'observacao': demanda.get('observacao', '')
                    }
                    writer.writerow(linha)
            else:
                linha = {
                    'colaborador': data.get('colaborador'),
                    'orgao_publico': data.get('orgao_publico'),
                    'figura_publica': data.get('figura_publica'),
                    'cargo': data.get('cargo'),
                    'assunto': data.get('assunto'),
                    'municipio': data.get('municipio'),
                    'data': data.get('data'),
                    'foto': data.get('foto'),
                    'tipo_visita': data.get('tipo_visita'), # ADICIONADO: 'tipo_visita'
                    'demanda': '',
                    'ov': '',
                    'pro': '',
                    'observacao': ''
                }
                writer.writerow(linha)

    escrever_linhas_csv(caminho_principal)
    escrever_linhas_csv(caminho_backup)
    escrever_linhas_csv(caminho_semanal)

# --- FUNÇÕES PARA POSTGRESQL ---
def conectar_banco():
    """Conecta ao banco de dados PostgreSQL."""
    try:
        url = os.environ.get("DATABASE_PUBLIC_URL")
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
        return conn
    except psycopg2.Error as e:
        logger.error(f"Erro ao conectar ao banco de dados: {e}") # Alterado para logger.error
        return None

def salvar_no_banco(data: dict):
    """Salva os dados no banco de dados PostgreSQL."""

    conn = conectar_banco() 
    if conn is None:
        return 

    cursor = conn.cursor() 

    try:
        data_str = data.get('data')
        data_date = datetime.strptime(data_str, '%Y-%m-%d').date() if isinstance(data_str, str) else data_str

        # ADICIONADO: 'tipo_visita' na instrução INSERT
        cursor.execute("""
            INSERT INTO registros (
                colaborador, orgao_publico, figura_publica, cargo,
                assunto, municipio, data, foto, tipo_visita
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get('colaborador'), data.get('orgao_publico'),
            data.get('figura_publica'), data.get('cargo'),
            data.get('assunto'), data.get('municipio'),
            data_date, 
            data.get('foto'),
            data.get('tipo_visita') # ADICIONADO: Campo tipo_visita
        ))

        demandas = data.get('demandas')
        if demandas:
            for demanda in demandas:
                cursor.execute("""
                    INSERT INTO demandas (
                        registro_id, texto, ov, pro, observacao
                    ) VALUES (lastval(), %s, %s, %s, %s)
                """, (
                    demanda.get('texto'), demanda.get('ov'),
                    demanda.get('pro'), demanda.get('observacao')
                ))

        conn.commit() 
        logger.info("Dados salvos no PostgreSQL!") # Alterado para logger.info

    except psycopg2.Error as e:
        conn.rollback() 
        logger.error(f"Erro ao salvar no banco de dados: {e}") # Alterado para logger.error

    finally:
        cursor.close() 
        conn.close() 

