from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CSV_ORIGINAL = RAIZ.parent / "Base_CNPq_Demanda_Atendimento_2019_2024.csv"
PAINEL = RAIZ / "data" / "raw" / "painel_agregado_2019_2024.csv"
SAIDA = RAIZ / "data" / "processed"

ANOS = (2019, 2024)
LINHAS_FOMENTO = {"Bolsas no País", "Bolsas no Exterior", "Apoio a Projetos de Pesquisa"}
REGIOES = {"SE": "Sudeste", "SU": "Sul", "NE": "Nordeste", "CO": "Centro-Oeste", "NO": "Norte", "\\EX": "Exterior"}
NAO_INFORMADO = "Não informado"
SEXOS = {"Feminino", "Masculino"}
RACAS = {"Amarela", "Branca", "Indígena", "Parda", "Preta"}
DIMENSOES = {"grande_area": "dim_grande_area", "linha_fomento": "dim_linha_fomento",
             "modalidade": "dim_modalidade", "regiao": "dim_regiao"}
CHAVE = ["ano_chamada", *DIMENSOES]
QUANTIDADES = ["qtd_demandada", "qtd_atendida"]
METRICAS = QUANTIDADES + ["valor_demandado", "valor_atendido"]
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
       "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
COLUNAS_PROCESSO = ["nu_processo", "ano_chamada", *DIMENSOES, "sigla_uf", "sigla_instituicao", "atendido",
                    "valor_demandado", "valor_atendido"]

log = []


def registrar(etapa, linhas):
    log.append({"etapa": etapa, "linhas": linhas})
    print(f"{etapa}: {linhas}")


def texto(serie):
    return serie.str.strip().str.replace(r"\s+", " ", regex=True).replace("", pd.NA)


def categoria(serie, validos):
    serie = texto(serie)
    return serie.where(serie.isin(validos), NAO_INFORMADO)


def padronizar(df):
    df["ano_chamada"] = pd.to_numeric(df["ano_chamada"].str.extract(r"(\d{4})")[0], errors="coerce")
    df["linha_fomento"] = texto(df["linha_fomento"])
    df["grande_area"] = texto(df["grande_area"]).fillna(NAO_INFORMADO)
    df["modalidade"] = texto(df["modalidade"]).fillna(NAO_INFORMADO)
    df["regiao"] = texto(df["regiao"]).map(REGIOES).fillna(NAO_INFORMADO)
    return df


def filtrar(df, origem):
    df = df[df["ano_chamada"].between(*ANOS)].copy()
    registrar(f"{origem}: recorte {ANOS[0]}-{ANOS[1]}", len(df))
    df = df[df["linha_fomento"].isin(LINHAS_FOMENTO)].copy()
    registrar(f"{origem}: somente bolsas e auxílios à pesquisa", len(df))
    df["ano_chamada"] = df["ano_chamada"].astype(int)
    return df


def tratar_csv():
    colunas = {"ano_chamada": "ano_chamada", "nu_processo": "nu_processo", "nme_chamada_macro": "linha_fomento",
               "nme_modalidade": "modalidade", "nme_grande_area": "grande_area", "sgl_regiao": "regiao",
               "vlr_total_solicitado": "valor_demandado", "vlr_total_atendido": "valor_atendido",
               "st_atendimento": "st_atendimento", "sgl_uf": "sigla_uf", "sigla_instituicao": "sigla_instituicao"}
    blocos = pd.read_csv(CSV_ORIGINAL, sep=";", dtype=str, usecols=list(colunas), chunksize=50_000, encoding="utf-8")
    df = pd.concat(blocos, ignore_index=True).rename(columns=colunas)
    registrar("csv: linhas lidas", len(df))
    df = df.drop_duplicates("nu_processo")
    registrar("csv: sem processos duplicados", len(df))
    df = filtrar(padronizar(df), "csv")

    df["nu_processo"] = texto(df["nu_processo"])
    uf = texto(df["sigla_uf"]).str.upper()
    df["sigla_uf"] = uf.where(uf.isin(UFS))
    df["sigla_instituicao"] = texto(df["sigla_instituicao"]).str.upper()
    df["atendido"] = texto(df["st_atendimento"]) == "S"
    for coluna in ("valor_demandado", "valor_atendido"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0)
    registrar("csv: valor atendido maior que demandado (mantidos)", int((df["valor_atendido"] > df["valor_demandado"]).sum()))

    df["qtd_demandada"] = 1
    df["qtd_atendida"] = df["atendido"].astype(int)
    agregado = df.groupby(CHAVE, as_index=False)[METRICAS].sum()
    registrar("csv: combinações agregadas", len(agregado))
    return df[COLUNAS_PROCESSO].copy(), agregado


def tratar_painel():
    colunas = {"ANO_CHAMADA": "ano_chamada", "DSC_SEXO": "sexo", "DSC_RACA_COR": "raca_cor",
               "NME_GRANDE_AREA": "grande_area", "NME_CHAMADA_MACRO": "linha_fomento",
               "NME_MODALIDADE": "modalidade", "SGL_REGIAO": "regiao",
               "Propostas Demandadas": "qtd_demandada", "Propostas Atendidas": "qtd_atendida",
               "Valor Total Demandado": "valor_demandado", "Valor Total Atendido": "valor_atendido"}
    df = pd.read_csv(PAINEL, dtype=str, encoding="utf-8").rename(columns=colunas)
    registrar("painel: combinações extraídas", len(df))
    df = filtrar(padronizar(df), "painel")
    df["sexo"] = categoria(df["sexo"], SEXOS)
    df["raca_cor"] = categoria(df["raca_cor"], RACAS)
    for coluna in METRICAS:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0)

    # Reagrega porque categorias distintas na origem podem ter virado "Não informado".
    df = df.groupby(CHAVE + ["sexo", "raca_cor"], as_index=False)[METRICAS].sum()
    df = df[df["qtd_demandada"] > 0].copy()
    registrar("painel: combinações com demanda > 0", len(df))
    return df


def main():
    grupo = tratar_painel()
    processos, csv = tratar_csv()
    assert len(processos) == csv["qtd_demandada"].sum() and processos["atendido"].sum() == csv["qtd_atendida"].sum()
    SAIDA.mkdir(parents=True, exist_ok=True)

    for coluna, tabela in DIMENSOES.items():
        ids = {nome: i for i, nome in enumerate(sorted(set(grupo[coluna]) | set(csv[coluna])), 1)}
        pd.DataFrame({"id": ids.values(), "nome": ids.keys()}).to_csv(SAIDA / f"{tabela}.csv", index=False)
        for df in (grupo, csv, processos):
            df[f"{coluna}_id"] = df.pop(coluna).map(ids)

    for df, nome in ((grupo, "fato_atendimento_grupo"), (csv, "fato_atendimento_csv")):
        df[QUANTIDADES] = df[QUANTIDADES].astype(int)
        df.to_csv(SAIDA / f"{nome}.csv", index=False, float_format="%.2f")
    processos.to_csv(SAIDA / "processo_tratado.csv", index=False, float_format="%.2f")
    pd.DataFrame(log).to_csv(SAIDA / "log_tratamento.csv", index=False)


if __name__ == "__main__":
    main()
