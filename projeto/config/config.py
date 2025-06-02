from pydantic import BaseSettings
from typing import List, Optional


class AppConfig(BaseSettings):
    """
    Configurações principais da aplicação.
    """

    BOT_TOKEN: str
    DATABASE_URL: str  # Usar DATABASE_URL para maior compatibilidade com o Railway
    GOOGLE_DRIVE_CREDENTIALS: Optional[str] = None  # Conteúdo do arquivo de credenciais do Google Drive
    ONEDRIVE_CLIENT_ID: Optional[str] = None
    ONEDRIVE_CLIENT_SECRET: Optional[str] = None
    ONEDRIVE_TENANT_ID: Optional[str] = None
    #ONEDRIVE_REFRESH_TOKEN: Optional[str] = None # Removido, não é mais necessário aqui
    CAMINHO_BASE: str = "."  # Caminho base do projeto
    CSV_ORGAOS: str = "listas/orgaos.csv"
    CSV_ASSUNTOS: str = "listas/assuntos.csv"
    CSV_REGISTRO: str = "data/registros.csv"
    FOTO_PATH: str = "fotos"
    PAGINACAO_TAMANHO: int = 5
    COLABORADORES: List[str] = ["Orlando", "Derielle", "Ricardo", "Vania", "Danillo"]

    class Config:
        env_file = "rail.env"  # Caminho para o arquivo .env
        env_file_encoding = "utf-8"


config = AppConfig()


import os
import stat


def escrever_permissao(path: str) -> None:
    """
    Garante que o diretório exista e tenha permissões de escrita.
    """
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    try:
        # Tenta escrever um arquivo para verificar as permissões
        test_file = os.path.join(path, "test_write.txt")
        open(test_file, "w").close()
        os.remove(test_file)
    except PermissionError:
        # Se não tiver permissão, tenta alterar as permissões
        os.chmod(path, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
        os.makedirs(path, exist_ok=True)
        print(f"Escrever permissão: {path}")
    except Exception as e:
        print(f"Erro ao verificar/definir permissões em: {path} - {e}")