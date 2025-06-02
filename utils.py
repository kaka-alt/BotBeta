import csv
import os
import pandas as pd
from telegram import InlineKeyboardButton
from datetime import datetime
from config import *
from globals import user_data
import psycopg2  
import urllib.parse

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

    # Adicione paginação e botões extras aqui se quiser
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

    # Garante que a pasta existe
    os.makedirs(os.path.dirname(caminho_orgaos), exist_ok=True)

    # Remove espaços extras e padroniza
    novo_orgao = novo_orgao.strip()

    # Verifica se o órgão já existe
    orgaos_existentes = set()
    if os.path.exists(caminho_orgaos):
        with open(caminho_orgaos, mode='r', encoding='utf-8') as f:
            orgaos_existentes = {linha.strip() for linha in f.readlines()}

    # Se não existe, adiciona
    if novo_orgao and novo_orgao not in orgaos_existentes:
        with open(caminho_orgaos, mode='a', newline='', encoding='utf-8') as f:
            f.write(f"{novo_orgao}\n")


# Lista Assuntos
def ler_assuntos_csv():
    df = pd.read_csv(CSV_ASSUNTOS)
    return df['assunto'].dropna().tolist()


def salvar_assunto(novo_assunto: str):
    caminho_assuntos = CSV_ASSUNTOS

    # Garante que a pasta existe
    os.makedirs(os.path.dirname(caminho_assuntos), exist_ok=True)

    # Remove espaços extras e padroniza
    novo_assunto = novo_assunto.strip()

    # Verifica se o assunto já existe
    assuntos_existentes = set()
    if os.path.exists(caminho_assuntos):
        with open(caminho_assuntos, mode='r', encoding='utf-8') as f:
            assuntos_existentes = {linha.strip() for linha in f.readlines()}

    # Se não existe, adiciona
    if novo_assunto and novo_assunto not in assuntos_existentes:
        with open(caminho_assuntos, mode='a', newline='', encoding='utf-8') as f:
            f.write(f"{novo_assunto}\n")


# Salvamento de CSV em pasta externa

def salvar_csv(data: dict):
    print("DADOS A SEREM SALVOS:", data)

    ano, semana, _ = datetime.now().isocalendar()
    # Garante pastas
    pasta_data = os.path.join(CAMINHO_BASE, "data")
    pasta_backup = os.path.join(pasta_data, "backup")
    pasta_semanal = os.path.join(pasta_data, "semanal")
    os.makedirs(pasta_semanal, exist_ok=True)
    os.makedirs(pasta_data, exist_ok=True)
    os.makedirs(pasta_backup, exist_ok=True)

    # Arquivo principal (fixo)
    caminho_principal = (CSV_REGISTRO)

    caminho_semanal = os.path.join(pasta_semanal, f"{ano}-semana-{semana}-registros.csv")

    # Arquivo de backup diário
    data_hoje = datetime.now().strftime('%Y-%m-%d')
    caminho_backup = os.path.join(pasta_backup, f"{data_hoje}-backup.csv")

    # Cabeçalhos
    cabecalho = [
        'colaborador', 'orgao_publico', 'figura_publica', 'cargo',
        'assunto', 'municipio', 'data', 'foto',
        'demanda', 'ov', 'pro', 'observacao'
    ]

    # Função para escrever nos arquivos
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
                        'demanda': demanda.get('texto'),
                        'ov': demanda.get('ov'),
                        'pro': demanda.get('pro'),
                        'observacao': demanda.get('observacao', '')
                    }
                    writer.writerow(linha)
            else:
                # Escreve uma linha mesmo sem demandas
                linha = {
                    'colaborador': data.get('colaborador'),
                    'orgao_publico': data.get('orgao_publico'),
                    'figura_publica': data.get('figura_publica'),
                    'cargo': data.get('cargo'),
                    'assunto': data.get('assunto'),
                    'municipio': data.get('municipio'),
                    'data': data.get('data'),
                    'foto': data.get('foto'),
                    'demanda': '',
                    'ov': '',
                    'pro': '',
                    'observacao': ''
                }
                writer.writerow(linha)

    # Salva no CSV principal (fixo)
    escrever_linhas_csv(caminho_principal)

    # Salva no backup diário
    escrever_linhas_csv(caminho_backup)

    # Salva no CSV semanal
    escrever_linhas_csv(caminho_semanal)


# --- NOVAS FUNÇÕES PARA POSTGRESQL ---
def conectar_banco():
    """Conecta ao banco de dados PostgreSQL."""
    try:
        url = os.environ.get("DATABASE_PUBLIC_URL")
        parsed_url = urllib.parse.urlparse(url)

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
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None


def salvar_no_banco(data: dict):
    """Salva os dados no banco de dados PostgreSQL."""

    conn = conectar_banco()  # Conecta ao banco
    if conn is None:
        return  # Se a conexão falhar, sai da função

    cursor = conn.cursor()  # Cria um cursor para executar comandos SQL

    try:
        # Insere os dados principais na tabela 'registros'
        cursor.execute("""
            INSERT INTO registros (
                colaborador, orgao_publico, figura_publica, cargo,
                assunto, municipio, data, foto
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get('colaborador'), data.get('orgao_publico'),
            data.get('figura_publica'), data.get('cargo'),
            data.get('assunto'), data.get('municipio'),
            data.get('data'), data.get('foto')
        ))

        # Se houver demandas, insira-as na tabela 'demandas'
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

        conn.commit()  # Salva as alterações no banco
        print("Dados salvos no PostgreSQL!")

    except psycopg2.Error as e:
        conn.rollback()  # Em caso de erro, desfaz as alterações
        print(f"Erro ao salvar no banco de dados: {e}")

    finally:
        cursor.close()  # Fecha o cursor
        conn.close()  # Fecha a conexão