import difflib
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
NAO_SE_APLICA = "Não se aplica"
SEXOS = {"Feminino", "Masculino"}
RACAS = {"Amarela", "Branca", "Indígena", "Parda", "Preta"}
DIMENSOES = {"grande_area": "dim_grande_area", "linha_fomento": "dim_linha_fomento",
             "modalidade": "dim_modalidade", "regiao": "dim_regiao"}
CHAVE = ["ano_chamada", *DIMENSOES]
QUANTIDADES = ["qtd_demandada", "qtd_atendida"]
VALORES = ["valor_demandado", "valor_atendido"]
METRICAS = QUANTIDADES + VALORES
UF_REFERENCIA = {
    "AC": ("Acre", "Norte"), "AL": ("Alagoas", "Nordeste"), "AP": ("Amapá", "Norte"), "AM": ("Amazonas", "Norte"),
    "BA": ("Bahia", "Nordeste"), "CE": ("Ceará", "Nordeste"), "DF": ("Distrito Federal", "Centro-Oeste"),
    "ES": ("Espírito Santo", "Sudeste"), "GO": ("Goiás", "Centro-Oeste"), "MA": ("Maranhão", "Nordeste"),
    "MT": ("Mato Grosso", "Centro-Oeste"), "MS": ("Mato Grosso do Sul", "Centro-Oeste"), "MG": ("Minas Gerais", "Sudeste"),
    "PA": ("Pará", "Norte"), "PB": ("Paraíba", "Nordeste"), "PR": ("Paraná", "Sul"), "PE": ("Pernambuco", "Nordeste"),
    "PI": ("Piauí", "Nordeste"), "RJ": ("Rio de Janeiro", "Sudeste"), "RN": ("Rio Grande do Norte", "Nordeste"),
    "RS": ("Rio Grande do Sul", "Sul"), "RO": ("Rondônia", "Norte"), "RR": ("Roraima", "Norte"),
    "SC": ("Santa Catarina", "Sul"), "SP": ("São Paulo", "Sudeste"), "SE": ("Sergipe", "Nordeste"),
    "TO": ("Tocantins", "Norte"),
}
UFS = set(UF_REFERENCIA)
COLUNAS_PROCESSO = ["nu_processo", "ano_chamada", *DIMENSOES, "sigla_uf", "cidade", "sigla_instituicao", "instituicao",
                    "pais", "atendido", "valor_demandado", "valor_atendido"]
CHAVE_REENVIO = ["ano_chamada", "chamada", "titulo", "sigla_instituicao", "area", "modalidade"]
CATEGORICAS_CSV = ["chamada", "linha_fomento", "modalidade", "grande_area", "area", "regiao", "instituicao", "cidade",
                   "nome_uf", "pais"]
CATEGORICAS_PAINEL = ["chamada", "linha_fomento", "modalidade", "grande_area", "area", "regiao", "sexo", "raca_cor"]

PREDOMINIO_AREA = 0.95
SEMELHANCA_NOME_UF = 0.85
FATOR_OUTLIER_BOLSA = 10
FATOR_OUTLIER_PROJETO = 20
MIN_PROPOSTAS_CHAMADA = 20
DIVISORES_DIGITACAO = (10, 100, 1000)

log = []


def registrar(etapa, linhas):
    log.append({"etapa": etapa, "linhas": linhas})
    print(f"{etapa}: {linhas}")


def texto(serie):
    return serie.str.strip().str.replace(r"\s+", " ", regex=True).replace("", pd.NA)


def sem_acento(serie):
    return serie.str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")


def chave(serie):
    return sem_acento(serie.str.upper()).str.replace(r"[^A-Z0-9]+", " ", regex=True).str.strip().replace("", pd.NA)


def grafia_preferida(serie):
    contagem = serie.value_counts()
    return max(contagem.index, key=lambda v: (not v.isascii(), v != v.upper(), contagem[v]))


def padronizar_grafias(df, colunas, origem):
    for coluna in colunas:
        valor = texto(df[coluna])
        k = chave(valor)
        canonica = valor.groupby(k).agg(grafia_preferida)
        novo = k.map(canonica).fillna(valor)
        registrar(f"{origem}: grafias padronizadas em {coluna}", int((novo.notna() & (novo != valor)).sum()))
        df[coluna] = novo


def padronizar_uf(df):
    sigla = texto(df["sigla_uf"]).str.upper()
    valida = sigla.isin(UFS)
    oficiais = pd.Series({s: nome for s, (nome, _) in UF_REFERENCIA.items()})
    por_chave = dict(zip(chave(oficiais), oficiais.index))
    k = chave(texto(df["nome_uf"]))
    pelo_nome = k.map(por_chave)
    # Erro de digitação só é corrigido contra a lista oficial de UFs, nunca entre valores da própria base.
    digitado = pd.Series(False, index=df.index)
    for valor in k[pelo_nome.isna() & k.notna()].unique():
        parecido = difflib.get_close_matches(valor, list(por_chave), n=1, cutoff=SEMELHANCA_NOME_UF)
        if parecido:
            linhas = k == valor
            pelo_nome[linhas] = por_chave[parecido[0]]
            digitado |= linhas
    registrar("csv: nome de UF com erro de digitação reconhecido", int(digitado.sum()))
    registrar("csv: UF deduzida pelo nome do estado", int((~valida & pelo_nome.notna()).sum()))
    registrar("csv: sigla e nome de UF incoerentes (mantida a sigla)", int((valida & pelo_nome.notna() & (pelo_nome != sigla)).sum()))
    df["sigla_uf"] = sigla.where(valida, pelo_nome)
    registrar("csv: sem UF válida (exterior ou não informada)", int(df["sigla_uf"].isna().sum()))

    esperada = df["sigla_uf"].map({s: regiao for s, (_, regiao) in UF_REFERENCIA.items()})
    errada = esperada.notna() & (df["regiao"] != esperada)
    df.loc[errada, "regiao"] = esperada[errada]
    registrar("csv: região corrigida pela UF", int(errada.sum()))


def categoria(serie, validos):
    serie = texto(serie)
    return serie.where(serie.isin(validos), NAO_INFORMADO)


def padronizar(df):
    df["ano_chamada"] = pd.to_numeric(df["ano_chamada"].str.extract(r"(\d{4})")[0], errors="coerce")
    df["chamada"] = texto(df["chamada"])
    df["linha_fomento"] = texto(df["linha_fomento"])
    df["grande_area"] = texto(df["grande_area"]).fillna(NAO_INFORMADO)
    df["area"] = texto(df["area"]).fillna(NAO_INFORMADO)
    df["modalidade"] = texto(df["modalidade"])
    df["regiao"] = texto(df["regiao"]).map(REGIOES).fillna(NAO_INFORMADO)
    return df


def familia_chamada(chamada):
    return chamada.str.replace(r"(19|20)\d{2}", "", regex=True).str.strip(" -_/.").str.upper()


def inferir_modalidade(df, origem):
    familia = familia_chamada(df["chamada"])
    conhecidas = df["modalidade"].groupby(familia).apply(lambda m: m.dropna().unique())
    unica = conhecidas[conhecidas.map(len) == 1].map(lambda m: m[0])
    vazia = df["modalidade"].isna()
    df.loc[vazia, "modalidade"] = familia[vazia].map(unica)
    registrar(f"{origem}: modalidade vazia deduzida pelas outras edições da chamada", int(df.loc[vazia, "modalidade"].notna().sum()))
    df["modalidade"] = df["modalidade"].fillna(NAO_INFORMADO)


def corrigir_grande_area(df, origem):
    informada = df["area"] != NAO_INFORMADO
    total = df[informada].groupby(["area", "grande_area"])["qtd_demandada"].sum()
    parcela = total / total.groupby(level="area").transform("sum")
    predominante = parcela[parcela >= PREDOMINIO_AREA].reset_index(level="grande_area")["grande_area"]
    nova = df["area"].map(predominante)
    trocar = informada & nova.notna() & (nova != df["grande_area"])
    df.loc[trocar, "grande_area"] = nova[trocar]
    registrar(f"{origem}: grande área corrigida pela área predominante", int(trocar.sum()))


def filtrar(df, origem):
    df = df[df["ano_chamada"].between(*ANOS)].copy()
    registrar(f"{origem}: recorte {ANOS[0]}-{ANOS[1]}", len(df))
    df = df[df["linha_fomento"].isin(LINHAS_FOMENTO)].copy()
    registrar(f"{origem}: somente bolsas e auxílios à pesquisa", len(df))
    df["ano_chamada"] = df["ano_chamada"].astype(int)
    return df


def remover_duplicados(df):
    df = df.sort_values("nu_processo")
    exatos = df.duplicated([c for c in df.columns if c != "nu_processo"])
    registrar("csv: duplicados exatos removidos (só o número do processo muda)", int(exatos.sum()))
    df = df[~exatos]

    comparacao = pd.DataFrame({c: chave(df[c].astype("string")) for c in CHAVE_REENVIO})
    comparacao["atendido"] = texto(df["st_atendimento"]) == "S"
    comparacao["nu_processo"] = df["nu_processo"]
    informado = comparacao["titulo"].notna() & (comparacao["titulo"] != "NAO INFORMADO")
    candidatos = comparacao[informado].sort_values(["atendido", "nu_processo"], ascending=False)
    reenvios = candidatos.index[candidatos.duplicated(CHAVE_REENVIO)]
    registrar("csv: reenvios removidos (mantido o atendido ou o último envio)", len(reenvios))
    return df.drop(reenvios)


def padronizar_siglas(df):
    original = texto(df["sigla_instituicao"])
    sigla = sem_acento(original.str.upper())
    nome = sem_acento(texto(df["instituicao"]).str.upper())
    base = pd.DataFrame({"nome": nome, "uf": df["sigla_uf"].fillna("-"), "sigla": sigla})
    canonica = base.groupby(["nome", "uf"])["sigla"].transform(lambda s: s.value_counts().index[0])
    df["sigla_instituicao"] = canonica.fillna(sigla)
    registrar("csv: siglas de instituição padronizadas", int((df["sigla_instituicao"] != original).sum()))


def corrigir_valores(df):
    for coluna in VALORES:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    zerado = df["valor_demandado"] == 0
    df.loc[zerado, "valor_demandado"] = None
    registrar("csv: valor demandado zero tornado nulo", int(zerado.sum()))

    bolsa = ~df["modalidade"].isin({NAO_SE_APLICA, NAO_INFORMADO})
    projeto = df["modalidade"] == NAO_SE_APLICA
    corrigidos = implausiveis = 0
    for coluna in VALORES:
        positivo = df[coluna].where(df[coluna] > 0)

        modalidade = df.loc[bolsa, "modalidade"]
        mediana = positivo[bolsa].groupby(modalidade).transform("median")
        valor = df.loc[bolsa, coluna]
        alto = valor > FATOR_OUTLIER_BOLSA * mediana
        normal = positivo[bolsa].where(~alto).groupby(modalidade)
        p1, p99 = normal.transform(lambda s: s.quantile(.01)), normal.transform(lambda s: s.quantile(.99))
        ajustado = pd.Series(float("nan"), index=valor.index)
        for divisor in DIVISORES_DIGITACAO:
            cabe = alto & ajustado.isna() & (valor / divisor).between(p1, p99)
            ajustado[cabe] = valor[cabe] / divisor
        df.loc[ajustado.dropna().index, coluna] = ajustado.dropna()
        df.loc[alto[alto & ajustado.isna()].index, coluna] = None
        corrigidos += int(ajustado.notna().sum())
        implausiveis += int((alto & ajustado.isna()).sum())

        por_chamada = positivo[projeto].groupby(df.loc[projeto, "chamada"])
        alto = (df.loc[projeto, coluna] > FATOR_OUTLIER_PROJETO * por_chamada.transform("median")) \
            & (por_chamada.transform("size") >= MIN_PROPOSTAS_CHAMADA)
        df.loc[alto[alto].index, coluna] = None
        implausiveis += int(alto.sum())

    registrar("csv: valores com vírgula deslocada corrigidos", corrigidos)
    registrar("csv: valores implausíveis tornados nulos", implausiveis)


def tratar_csv():
    colunas = {"nme_chamada_macro": "linha_fomento", "sgl_chamada": "chamada", "nme_modalidade": "modalidade",
               "nme_grande_area": "grande_area", "nme_area": "area", "sgl_regiao": "regiao",
               "vlr_total_solicitado": "valor_demandado", "vlr_total_atendido": "valor_atendido",
               "sgl_uf": "sigla_uf", "nme_uf": "nome_uf", "txt_titulo_obj_proposta": "titulo"}
    blocos = pd.read_csv(CSV_ORIGINAL, sep=";", dtype=str, chunksize=50_000, encoding="utf-8")
    df = pd.concat(blocos, ignore_index=True).rename(columns=colunas)
    registrar("csv: linhas lidas", len(df))
    df = df.drop_duplicates("nu_processo")
    registrar("csv: sem números de processo repetidos", len(df))

    df["qtd_demandada"] = 1
    padronizar_grafias(df, CATEGORICAS_CSV, "csv")
    df = padronizar(df)
    padronizar_uf(df)
    inferir_modalidade(df, "csv")
    corrigir_grande_area(df, "csv")
    df = filtrar(df, "csv")
    padronizar_siglas(df)
    df = remover_duplicados(df)
    registrar("csv: processos após limpeza", len(df))

    df["nu_processo"] = texto(df["nu_processo"])
    df["atendido"] = texto(df["st_atendimento"]) == "S"
    df["qtd_atendida"] = df["atendido"].astype(int)
    corrigir_valores(df)
    registrar("csv: valor atendido maior que demandado (mantidos)", int((df["valor_atendido"] > df["valor_demandado"]).sum()))

    agregado = df.groupby(CHAVE, as_index=False)[METRICAS].sum(min_count=1)
    registrar("csv: combinações agregadas", len(agregado))
    return df[COLUNAS_PROCESSO].copy(), agregado


def tratar_painel():
    colunas = {"ANO_CHAMADA": "ano_chamada", "DSC_SEXO": "sexo", "DSC_RACA_COR": "raca_cor",
               "NME_GRANDE_AREA": "grande_area", "NME_AREA": "area", "SGL_CHAMADA": "chamada",
               "NME_CHAMADA_MACRO": "linha_fomento", "NME_MODALIDADE": "modalidade", "SGL_REGIAO": "regiao",
               "Propostas Demandadas": "qtd_demandada", "Propostas Atendidas": "qtd_atendida",
               "Valor Total Demandado": "valor_demandado", "Valor Total Atendido": "valor_atendido"}
    df = pd.read_csv(PAINEL, dtype=str, encoding="utf-8").rename(columns=colunas)
    registrar("painel: combinações extraídas", len(df))
    for coluna in METRICAS:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0)
    padronizar_grafias(df, CATEGORICAS_PAINEL, "painel")
    df = padronizar(df)
    inferir_modalidade(df, "painel")
    corrigir_grande_area(df, "painel")
    df = filtrar(df, "painel")
    df["sexo"] = categoria(df["sexo"], SEXOS)
    df["raca_cor"] = categoria(df["raca_cor"], RACAS)

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
