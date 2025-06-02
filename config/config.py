import os
import stat

BOT_TOKEN = os.getenv("BOT_TOKEN")

# CAMINHO_BASE -  Relative to the project root (where Procfile is)
CAMINHO_BASE = "."  # Current directory
CSV_ORGAOS = os.path.join(CAMINHO_BASE, "listas", "orgaos.csv")
CSV_PATH = os.path.join(CAMINHO_BASE, "data")
FOTO_PATH = os.path.join(CAMINHO_BASE, "fotos")
CSV_ASSUNTOS = os.path.join(CAMINHO_BASE, "listas", "assuntos.csv")
CSV_REGISTRO = os.path.join(CAMINHO_BASE, "data", "registros.csv")
PAGINACAO_TAMANHO = 5
COLABORADORES = ["Orlando", "Derielle", "Ricardo", "Vania", "Danillo"]

def escrever_permissao(path):
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        try:
            #olha se tem permissao
            open(os.path.join(path, "test_write.txt"), "w").close()
            os.remove(os.path.join(path, "test_write.txt"))  # faz um teste escrevendo um arquivo txt
        except PermissionError:
            # se não tiver permissão ele escrever 
            os.chmod(path, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR) 
            os.makedirs(path, exist_ok=True)  
            print(f"Escrever permissão: {path}")  
        except Exception as e:
            print(f"erro ao olhar a permissão/dar permissão {path}: {e}")

    # Ensure permissions for data and fotos
escrever_permissao(CSV_PATH)
escrever_permissao(FOTO_PATH)


# Ensure directories exist (this is VERY important)
os.makedirs(os.path.dirname(CSV_ORGAOS), exist_ok=True)
os.makedirs(CSV_PATH, exist_ok=True)
os.makedirs(FOTO_PATH, exist_ok=True)
os.makedirs(os.path.dirname(CSV_ASSUNTOS), exist_ok=True)
os.makedirs(os.path.dirname(CSV_REGISTRO), exist_ok=True)