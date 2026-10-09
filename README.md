# Fase 2 – Tratamento e Armazenamento dos Dados

ETL que extrai, trata e carrega no PostgreSQL (Aiven) os dados do Painel de Demanda e Atendimento do CNPq.

## Pré-requisitos

- Python 3.14 e [uv](https://docs.astral.sh/uv/)
- Serviço PostgreSQL no Aiven
- CSV original `Base_CNPq_Demanda_Atendimento_2019_2024.csv` na pasta **acima** deste projeto

## Configuração

1. Crie o ambiente e instale as dependências:
   ```bash
   uv venv --python 3.14 .venv
   uv pip install --python .venv -r requirements.txt
   ```
2. Copie `.env.example` para `.env` e preencha `DATABASE_URL` com o Service URI do Aiven.
3. Baixe o **CA certificate** do serviço no console do Aiven e salve como `ca.pem` na raiz do projeto.

`.env` e `ca.pem` não são versionados.

## Execução

```bash
.venv\Scripts\python etl/extrair_painel.py
.venv\Scripts\python etl/tratar.py
.venv\Scripts\python etl/carregar.py
```

| Script | O que faz |
|---|---|
| `etl/extrair_painel.py` | Extrai o agregado do painel para `data/raw/` |
| `etl/tratar.py` | Limpa e padroniza o CSV e o extrato do painel e gera `data/processed/` |
| `etl/carregar.py` | Recria o esquema (`sql/schema.sql`) e carrega `data/processed/` no Aiven |

## Testes

```bash
.venv\Scripts\python -m unittest discover -s tests -v
```

Os testes de banco são pulados sem `.env` e `ca.pem`, e o de comparação com o original, sem o CSV original na pasta acima.
