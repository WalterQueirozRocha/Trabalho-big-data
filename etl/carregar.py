import os
import ssl
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pg8000.native  # Python puro: a DLL do psycopg é bloqueada pelo Controle de Aplicativos do Windows.

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "data" / "processed"
TABELAS = ["dim_grande_area", "dim_linha_fomento", "dim_modalidade", "dim_regiao",
           "fato_atendimento_grupo", "fato_atendimento_csv", "processo_tratado"]


def database_url():
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]
    env = RAIZ / ".env"
    if env.exists():
        for linha in env.read_text(encoding="utf-8").splitlines():
            chave, _, valor = linha.partition("=")
            if chave.strip() == "DATABASE_URL":
                return valor.strip()
    raise SystemExit("Defina DATABASE_URL no ambiente ou no arquivo .env")


def conectar(url):
    partes = urlsplit(url)
    ca = RAIZ / "ca.pem"
    if not ca.exists():
        raise SystemExit("Baixe o CA certificate do serviço no console do Aiven e salve como ca.pem na raiz do projeto")
    contexto = ssl.create_default_context(cafile=ca)
    return pg8000.native.Connection(
        user=unquote(partes.username), password=unquote(partes.password), host=partes.hostname,
        port=partes.port or 5432, database=partes.path.lstrip("/"), ssl_context=contexto)


def main():
    conn = conectar(database_url())
    try:
        conn.run("BEGIN")
        # Divisão simples por ";": vale enquanto o schema não tiver ";" dentro de literais.
        for comando in (RAIZ / "sql" / "schema.sql").read_text(encoding="utf-8").split(";"):
            if comando.strip():
                conn.run(comando)
        for tabela in TABELAS:
            with (DADOS / f"{tabela}.csv").open(encoding="utf-8") as f:
                colunas = f.readline().strip()
                f.seek(0)
                conn.run(f"COPY {tabela} ({colunas}) FROM STDIN WITH (FORMAT csv, HEADER true)", stream=f)
        conn.run("COMMIT")

        for tabela in TABELAS:
            linhas, tamanho = conn.run(f"SELECT count(*), pg_size_pretty(pg_total_relation_size('{tabela}')) FROM {tabela}")[0]
            print(tabela, linhas, tamanho)
        print("tamanho do banco:", conn.run("SELECT pg_size_pretty(pg_database_size(current_database()))")[0][0])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
