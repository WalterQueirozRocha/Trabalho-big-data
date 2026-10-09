# Fase 2 – Unificação, Tratamento, Modelagem e Armazenamento

Tema: **Auditoria de Viés Étnico-Gênero em Fomento à Pesquisa Científica** (CNPq, chamadas de 2019 a 2024).

## 1. Origem dos dados

| Fonte | Conteúdo | Como é obtida | Versão original |
|---|---|---|---|
| CSV de dados abertos do CNPq (`Base_CNPq_Demanda_Atendimento_2019_2024.csv`) | 1 linha por processo: chamada, modalidade, área, instituição, região, quantidades, valores e situação. **Não tem sexo nem raça/cor** | Exportação do Painel de Demanda e Atendimento | 100.693.334 bytes, 142.222 linhas, 39 colunas. SHA-256 `18d9dfddd734ffca2db1310a6e3eaad1cf2a7c2d8af57918a53e525f9da09120`. Não versionado (tamanho); fica na pasta acima deste projeto |
| [Painel de Demanda e Atendimento (Power BI)](https://app.powerbi.com/view?r=eyJrIjoiMzcyZDkyMTQtZDk3MC00MTgyLWI5MzEtNjFlNmM3OGQwMGIxIiwidCI6IjE2MDE4YmVhLTBhMzItNGY5Mi05Y2IwLWI3YzgxMWFhNTcyNiJ9) | Mesmo cadastro, com `DSC_SEXO` e `DSC_RACA_COR` | `etl/extrair_painel.py` consulta a API pública do relatório e grava `data/raw/painel_agregado_2019_2024.csv` (versionado) | Extrato bruto, sem tratamento |

## 2. Estrutura

```
fase2_etl/
├── etl/extrair_painel.py        # painel -> data/raw (agregado por sexo e raça/cor)
├── etl/tratar.py                # CSV + painel -> data/processed (dimensões, fatos, processos, log)
├── etl/carregar.py              # schema.sql + COPY no PostgreSQL (Aiven)
├── sql/schema.sql               # tabelas e views
├── tests/                       # testes de extração, tratamento e banco
├── data/raw/                    # versão original extraída do painel
└── data/processed/              # versão tratada (o que vai para o banco) + log_tratamento.csv
```

## 3. Como executar

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv -r requirements.txt
.venv\Scripts\python etl/extrair_painel.py
.venv\Scripts\python etl/tratar.py
copy .env.example .env      # preencher DATABASE_URL com o Service URI do Aiven
.venv\Scripts\python etl/carregar.py
.venv\Scripts\python -m unittest discover -s tests -v
```

### Testes

27 testes em `unittest` (biblioteca padrão), todos passando na carga atual:

| Arquivo | O que valida |
|---|---|
| `tests/test_extrair_painel.py` | Decodificação do formato DSR do Power BI (dicionário, repetição, nulos) e montagem da consulta por ano |
| `tests/test_tratar.py` | Regras de padronização e filtro; nos arquivos tratados: ids e chaves estrangeiras, recorte, categorias, processos únicos, UF válida, ausência de sexo/raça por processo, processos = agregado, e que do CSV original só saíram linhas fora de bolsas e auxílios |
| `tests/test_banco.py` | No Aiven: linhas de cada tabela = arquivo tratado, `taxa_atendimento` correta, views preenchidas, reconciliação somando as fontes e tamanho abaixo de 650 MB |

Os testes de dados são pulados se `data/processed/` não existir; os de banco, sem `.env` e `ca.pem`; o de comparação com o original, sem o CSV original na pasta acima.

Antes da carga, baixe o **CA certificate** do serviço no console do Aiven e salve-o como `ca.pem` na raiz do projeto. A conexão valida o certificado do servidor (equivalente a `sslmode=verify-full`). `.env` e `ca.pem` não são versionados.

O driver é o `pg8000` (Python puro), porque a DLL do `psycopg[binary]` foi bloqueada pelo Controle de Aplicativos do Windows.

## 4. Decisões técnicas e justificativas

| # | Decisão | Justificativa |
|---|---|---|
| 1 | Sexo e raça/cor são extraídos do painel **somente agregados**, nunca por processo | Raça/cor é dado pessoal sensível (LGPD, art. 5º, II). A auditoria compara grupos e não precisa de dados individuais (Etapa 1, seção 2.3) |
| 2 | Unificação por **dimensões comuns** (ano, grande área, linha de fomento, modalidade, região), não por processo | As fontes não compartilham chave individual depois da agregação. As dimensões conformadas permitem comparar e reconciliar as duas bases |
| 3 | `nme_chamada_macro` é usada como **linha de fomento** | `nme_linha_fomento` tem "0.0 - Problemas Encontrar Modalidade Processo" em 122.234 de 142.222 linhas (86%), o que a torna inutilizável |
| 4 | Filtro de linha: Bolsas no País, Bolsas no Exterior e Apoio a Projetos de Pesquisa | São as linhas de bolsas e auxílios à pesquisa (Etapa 1, 2.1). Saem ARC (eventos), Apoio a Eventos e Prêmios |
| 5 | Leitura em blocos, tudo como texto, com parser CSV real (`;` dentro de aspas) | Preserva códigos e evita colunas deslocadas: `txt_plv_chave` e títulos contêm `;` |
| 6 | Remoção de processos duplicados (`nu_processo`) | Cada proposta deve ser contada uma vez |
| 7 | "Não desejo declarar" e ausentes viram **"Não informado"**, mantidos como categoria própria | Etapa 1, 2.1: não redistribuir entre grupos para não distorcer as diferenças |
| 8 | Regiões por extenso (`SE` → Sudeste, `\EX` → Exterior); textos sem espaços excedentes; modalidade vazia → "Não informado" | Padronização das categorias (Etapa 1, Quadro 3) |
| 9 | Valores convertidos de texto com ponto decimal; um valor ausente viraria 0 | O CSV usa ponto decimal e não "R$". Nenhum valor total ausente foi encontrado; a regra fica como proteção, pois um ausente corresponderia a valor não concedido |
| 10 | Valor atendido maior que o demandado é **mantido** e contado no log | Pode ocorrer legitimamente (ex.: bolsa concedida em nível superior ao solicitado); excluir alteraria os totais |
| 11 | Agregação antes da carga; `taxa_atendimento` calculada no banco (coluna gerada) | Reduz o volume (meta ≤ 650 MB) e garante que a taxa sempre bate com as quantidades |
| 12 | `diferenca_grupo` em view, com referência **Masculino + Branca** | Etapa 1, Quadro 4: calculada após a agregação, sem alterar dados. O grupo de referência é o maior da base |
| 13 | Sem amostragem | Etapa 1, 2.2: grupos pequenos (ex.: Indígena) ficariam instáveis |
| 14 | Esquema recriado a cada carga (`DROP` + `CREATE`) | Carga completa e reprodutível; a base é pequena |
| 15 | Valores do painel obtidos pela **soma direta** das colunas `Valor Total Demandado/Atendido` (R$), não pelas medidas "Total Geral" | As medidas dependem do seletor de moeda do relatório e retornam vazio quando consultadas sem ele. Verificado que a tabela do painel tem 1 linha por processo (linhas = processos distintos), portanto a soma não duplica valores |
| 16 | Tabela `processo_tratado` com os 139.999 processos tratados, um por linha | Permite conferir registro a registro o resultado do tratamento. Não tem sexo nem raça/cor: contém só o que o CNPq já publica no CSV de dados abertos, então a decisão 1 continua valendo |
| 17 | UF validada contra as 27 siglas; `\EX` e `\NI` viram nulo | `CHAR(2)` exige sigla válida (Etapa 1, Quadro 3). A região já registra "Exterior" |

## 5. Modelo de dados (PostgreSQL)

Esquema estrela: duas tabelas fato agregadas e a tabela de processos tratados compartilham as mesmas dimensões.

```
dim_grande_area ─┐
dim_linha_fomento┼──< fato_atendimento_grupo   (painel: + sexo, raca_cor)
dim_modalidade   ┼──< fato_atendimento_csv     (dados abertos, agregado)
dim_regiao      ─┴──< processo_tratado         (dados abertos, 1 linha por processo)
```

| Tabela | Campos e tipos |
|---|---|
| `dim_grande_area`, `dim_linha_fomento`, `dim_modalidade`, `dim_regiao` | `id SMALLSERIAL PK`, `nome VARCHAR UNIQUE` |
| `fato_atendimento_grupo` | `ano_chamada SMALLINT`, `sexo VARCHAR(20)`, `raca_cor VARCHAR(30)`, `grande_area_id`, `linha_fomento_id`, `modalidade_id`, `regiao_id` (`SMALLINT FK`), `qtd_demandada INTEGER`, `qtd_atendida INTEGER`, `valor_demandado NUMERIC(16,2)`, `valor_atendido NUMERIC(16,2)`, `taxa_atendimento NUMERIC(7,4)` (gerada) |
| `fato_atendimento_csv` | Mesmas colunas, sem `sexo`, `raca_cor` e `taxa_atendimento` |
| `processo_tratado` | `nu_processo VARCHAR(20) PK`, `ano_chamada SMALLINT`, as 4 FKs (`SMALLINT`), `sigla_uf CHAR(2)`, `sigla_instituicao VARCHAR(30)`, `atendido BOOLEAN`, `valor_demandado NUMERIC(16,2)`, `valor_atendido NUMERIC(16,2)` |
| `vw_diferenca_grupo` | Taxa por ano × grande área × sexo × raça/cor e `diferenca_grupo` em relação ao grupo de referência |
| `vw_reconciliacao_fontes` | Totais painel × CSV por ano, grande área e linha de fomento |

## 6. Resultados

### Tratamento (`data/processed/log_tratamento.csv`)

| Etapa | Linhas |
|---|---:|
| Painel: combinações extraídas (2019–2024) | 11.201 |
| Painel: somente bolsas e auxílios à pesquisa | 9.157 |
| Painel: combinações com demanda > 0 | 9.157 |
| CSV: linhas lidas | 142.222 |
| CSV: sem processos duplicados | 142.222 |
| CSV: recorte 2019–2024 | 142.222 |
| CSV: somente bolsas e auxílios à pesquisa | 139.999 |
| CSV: valor atendido maior que demandado (mantidos) | 7.864 |
| CSV: combinações agregadas | 1.398 |

### Banco (PostgreSQL no Aiven Free Tier)

| Tabela | Registros | Tamanho |
|---|---:|---:|
| `dim_grande_area` | 11 | 40 kB |
| `dim_linha_fomento` | 3 | 40 kB |
| `dim_modalidade` | 14 | 40 kB |
| `dim_regiao` | 7 | 40 kB |
| `fato_atendimento_grupo` | 9.157 | 1.216 kB |
| `fato_atendimento_csv` | 1.398 | 144 kB |
| `processo_tratado` | 139.999 | 16 MB |
| **Banco inteiro** | | **25 MB** (≈ 4% da meta de 650 MB) |

`processo_tratado` confere com `fato_atendimento_csv`: mesmo total de propostas (139.999), de atendidas (47.198) e de valores. `tratar.py` verifica isso a cada execução. 4.576 processos têm `sigla_uf` nula (exterior).

`vw_diferenca_grupo` retorna 732 linhas (ano × grande área × sexo × raça/cor), todas com `diferenca_grupo` calculada. `vw_reconciliacao_fontes` retorna 135 linhas, com 184.794 propostas no painel e 139.999 no CSV.

### Visão geral da taxa de atendimento (2019–2024, painel)

| Sexo | Raça/cor | Demandadas | Atendidas | Taxa |
|---|---|---:|---:|---:|
| Masculino | Branca | 67.042 | 24.438 | 0,3645 |
| Feminino | Branca | 55.272 | 17.421 | 0,3152 |
| Masculino | Parda | 18.496 | 5.632 | 0,3045 |
| Feminino | Parda | 11.966 | 3.136 | 0,2621 |
| Masculino | Preta | 3.857 | 1.035 | 0,2683 |
| Feminino | Preta | 2.603 | 694 | 0,2666 |
| Masculino | Amarela | 1.565 | 532 | 0,3399 |
| Feminino | Amarela | 1.518 | 471 | 0,3103 |
| Masculino | Indígena | 379 | 110 | 0,2902 |
| Feminino | Indígena | 191 | 75 | 0,3927 |

## 7. Limitações

- A API do painel não é documentada e pode mudar. Por isso o extrato bruto fica versionado em `data/raw/`.
- Os totais do painel e do CSV não coincidem: o painel cobre mais processos que o CSV exportado (ex.: 2022 tem 19.979 propostas no painel e 10.486 no CSV). As divergências ficam expostas em `vw_reconciliacao_fontes`, sem ajuste artificial. A auditoria usa o painel, que é a fonte com sexo e raça/cor.

| Ano | Propostas (painel) | Propostas (CSV) | Atendidas (painel) | Atendidas (CSV) |
|---|---:|---:|---:|---:|
| 2019 | 20.888 | 18.157 | 6.111 | 5.336 |
| 2020 | 26.627 | 17.495 | 7.073 | 4.602 |
| 2021 | 30.446 | 24.907 | 13.454 | 10.935 |
| 2022 | 19.979 | 10.486 | 8.760 | 5.295 |
| 2023 | 38.631 | 30.446 | 11.301 | 9.028 |
| 2024 | 48.223 | 38.508 | 15.115 | 12.002 |
