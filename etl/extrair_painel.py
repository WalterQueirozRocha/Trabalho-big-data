from pathlib import Path

import pandas as pd
import requests

API = "https://wabi-brazil-south-b-primary-api.analysis.windows.net/public/reports"
RESOURCE_KEY = "372d9214-d970-4182-b931-61e6c78d00b1"
ANOS = range(2019, 2025)
# Sem NU_PROCESSO: sexo e raça/cor por processo são dados pessoais sensíveis (LGPD).
COLUNAS = ["ANO_CHAMADA", "DSC_SEXO", "DSC_RACA_COR", "NME_GRANDE_AREA",
           "NME_CHAMADA_MACRO", "NME_MODALIDADE", "SGL_REGIAO"]
MEDIDAS = ["Propostas Demandadas", "Propostas Atendidas"]
# Soma direta em R$: as medidas de valor do painel dependem do seletor de moeda e voltam vazias sem ele.
SOMAS = ["Valor Total Demandado", "Valor Total Atendido"]
ALIAS = {"Dados": "d", "Medidas": "m"}
SAIDA = Path(__file__).resolve().parents[1] / "data" / "raw" / "painel_agregado_2019_2024.csv"


def _coluna(nome):
    return {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": nome}, "Name": f"Dados.{nome}"}


def _medida(nome):
    return {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": nome}, "Name": f"Medidas.{nome}"}


def _soma(nome):
    return {"Aggregation": {"Expression": {"Column": _coluna(nome)["Column"]}, "Function": 0}, "Name": f"Sum({nome})"}


def montar_consulta(modelo, ano):
    select = [_coluna(c) for c in COLUNAS] + [_medida(m) for m in MEDIDAS] + [_soma(s) for s in SOMAS]
    filtro_ano = {"Condition": {"In": {
        "Expressions": [{"Column": _coluna("ANO_CHAMADA")["Column"]}],
        "Values": [[{"Literal": {"Value": f"'{ano}'"}}]],
    }}}
    consulta = {
        "Version": 2,
        "From": [{"Name": alias, "Entity": entidade, "Type": 0} for entidade, alias in ALIAS.items()],
        "Select": select,
        "Where": [filtro_ano],
    }
    comando = {"SemanticQueryDataShapeCommand": {"Query": consulta, "Binding": {
        "Primary": {"Groupings": [{"Projections": list(range(len(select)))}]},
        "DataReduction": {"DataVolume": 4, "Primary": {"Window": {"Count": 30000}}},
        "Version": 1,
    }}}
    return {
        "version": "1.0.0",
        "queries": [{
            "Query": {"Commands": [comando]},
            "ApplicationContext": {"DatasetId": modelo["dbName"], "Sources": [{"ReportId": RESOURCE_KEY}]},
        }],
        "cancelQueries": [],
        "modelId": modelo["id"],
    }


def decodificar_dsr(ds):
    # Formato DSR do Power BI: "R" e "Ø" são bitmasks de colunas repetidas da linha anterior e de colunas nulas.
    dicionarios = ds.get("ValueDicts", {})
    linhas, schema, anterior = [], None, None
    for item in ds["PH"][0]["DM0"]:
        schema = item.get("S", schema)
        valores = iter(item.get("C", []))
        repetidas, nulas = item.get("R", 0), item.get("Ø", 0)
        linha = []
        for i, coluna in enumerate(schema):
            bit = 1 << i
            if repetidas & bit:
                linha.append(anterior[i])
            elif nulas & bit:
                linha.append(None)
            else:
                valor = next(valores)
                if "DN" in coluna and isinstance(valor, int):
                    valor = dicionarios[coluna["DN"]][valor]
                linha.append(valor)
        linhas.append(linha)
        anterior = linha
    return linhas


def main():
    sessao = requests.Session()
    sessao.headers["X-PowerBI-ResourceKey"] = RESOURCE_KEY
    resposta = sessao.get(f"{API}/{RESOURCE_KEY}/modelsAndExploration",
                          params={"preferReadOnlySession": "true"}, timeout=60)
    resposta.raise_for_status()
    modelo = resposta.json()["models"][0]

    partes = []
    for ano in ANOS:
        resposta = sessao.post(f"{API}/querydata", params={"synchronous": "true"},
                               json=montar_consulta(modelo, ano), timeout=120)
        resposta.raise_for_status()
        ds = resposta.json()["results"][0]["result"]["data"]["dsr"]["DS"][0]
        if not ds.get("IC", False):
            raise RuntimeError(f"Resultado incompleto para {ano}: reduzir a granularidade da consulta.")
        parte = pd.DataFrame(decodificar_dsr(ds), columns=COLUNAS + MEDIDAS + SOMAS)
        print(f"{ano}: {len(parte)} combinações")
        partes.append(parte)

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(partes, ignore_index=True).to_csv(SAIDA, index=False, encoding="utf-8")
    print(f"Extrato salvo em {SAIDA}")


if __name__ == "__main__":
    main()
