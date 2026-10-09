import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))

import tratar
from tratar import (CSV_ORIGINAL, LINHAS_FOMENTO, NAO_INFORMADO, RACAS, SAIDA, SEXOS, UFS, categoria, filtrar,
                    padronizar, texto)


def lista(serie):
    return [None if pd.isna(v) else v for v in serie]


class Regras(unittest.TestCase):
    def test_texto_remove_espacos_excedentes_e_vazios(self):
        self.assertEqual(lista(texto(pd.Series(["  Bolsas   no  País ", "", None], dtype=str))),
                         ["Bolsas no País", None, None])

    def test_categoria_agrupa_nao_declarado_e_ausente(self):
        serie = pd.Series(["Feminino", " Masculino ", "Não desejo declarar", None], dtype=str)
        self.assertEqual(list(categoria(serie, SEXOS)), ["Feminino", "Masculino", NAO_INFORMADO, NAO_INFORMADO])

    def test_padronizar_converte_ano_regiao_e_vazios(self):
        df = padronizar(pd.DataFrame({
            "ano_chamada": ["2019", " INTELIGÊNCIA"], "linha_fomento": [" Bolsas no País", "Prêmios"],
            "grande_area": [None, "Engenharias"], "modalidade": ["", "Produtividade em Pesquisa"],
            "regiao": ["SE", "\\EX"],
        }, dtype=str))
        self.assertEqual(df["ano_chamada"].iloc[0], 2019)
        self.assertTrue(pd.isna(df["ano_chamada"].iloc[1]))
        self.assertEqual(list(df["regiao"]), ["Sudeste", "Exterior"])
        self.assertEqual(df["grande_area"].iloc[0], NAO_INFORMADO)
        self.assertEqual(df["modalidade"].iloc[0], NAO_INFORMADO)

    def test_filtrar_aplica_recorte_e_linha_de_fomento(self):
        df = pd.DataFrame({"ano_chamada": [2018.0, 2019.0, 2024.0, 2024.0, None],
                           "linha_fomento": ["Bolsas no País", "Bolsas no País", "Prêmios",
                                             "Apoio a Projetos de Pesquisa", "Bolsas no País"]})
        resultado = filtrar(df, "teste")
        self.assertEqual(list(resultado["ano_chamada"]), [2019, 2024])


@unittest.skipUnless((SAIDA / "processo_tratado.csv").exists(), "rode etl/tratar.py antes")
class DadosTratados(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ler = lambda nome: pd.read_csv(SAIDA / f"{nome}.csv", keep_default_na=False, na_values=[""])
        cls.dims = {nome: ler(nome) for nome in tratar.DIMENSOES.values()}
        cls.grupo = ler("fato_atendimento_grupo")
        cls.csv = ler("fato_atendimento_csv")
        cls.processos = ler("processo_tratado")

    def test_dimensoes_tem_ids_e_nomes_unicos(self):
        for nome, dim in self.dims.items():
            with self.subTest(dimensao=nome):
                self.assertTrue(dim["id"].is_unique and dim["nome"].is_unique)
                self.assertFalse(dim["nome"].isna().any())

    def test_chaves_estrangeiras_existem_nas_dimensoes(self):
        for coluna, nome in tratar.DIMENSOES.items():
            ids = set(self.dims[nome]["id"])
            for tabela, df in (("grupo", self.grupo), ("csv", self.csv), ("processos", self.processos)):
                with self.subTest(tabela=tabela, coluna=coluna):
                    self.assertTrue(set(df[f"{coluna}_id"]) <= ids)

    def test_somente_linhas_de_bolsas_e_auxilios(self):
        self.assertEqual(set(self.dims["dim_linha_fomento"]["nome"]), LINHAS_FOMENTO)

    def test_anos_no_recorte(self):
        for df in (self.grupo, self.csv, self.processos):
            self.assertTrue(df["ano_chamada"].between(2019, 2024).all())

    def test_categorias_de_sexo_e_raca(self):
        self.assertTrue(set(self.grupo["sexo"]) <= SEXOS | {NAO_INFORMADO})
        self.assertTrue(set(self.grupo["raca_cor"]) <= RACAS | {NAO_INFORMADO})

    def test_quantidades_validas(self):
        for df in (self.grupo, self.csv):
            self.assertTrue((df["qtd_demandada"] > 0).all())
            self.assertTrue((df["qtd_atendida"] >= 0).all())

    def test_processos_unicos_e_uf_valida(self):
        self.assertTrue(self.processos["nu_processo"].is_unique)
        ufs = self.processos["sigla_uf"].dropna()
        self.assertTrue(set(ufs) <= UFS)

    def test_processos_conferem_com_o_agregado(self):
        self.assertEqual(len(self.processos), self.csv["qtd_demandada"].sum())
        self.assertEqual(self.processos["atendido"].sum(), self.csv["qtd_atendida"].sum())
        for coluna in ("valor_demandado", "valor_atendido"):
            self.assertAlmostEqual(self.processos[coluna].sum(), self.csv[coluna].sum(), delta=1)

    def test_sem_sexo_ou_raca_por_processo(self):
        self.assertFalse({"sexo", "raca_cor"} & set(self.processos.columns))

    @unittest.skipUnless(CSV_ORIGINAL.exists(), "CSV original ausente")
    def test_so_saem_do_original_linhas_fora_do_recorte(self):
        original = pd.read_csv(CSV_ORIGINAL, sep=";", dtype=str, usecols=["nu_processo", "nme_chamada_macro"])
        mantidos = set(self.processos["nu_processo"])
        removidos = original[~original["nu_processo"].isin(mantidos)]
        self.assertTrue(mantidos <= set(original["nu_processo"]))
        self.assertFalse(removidos["nme_chamada_macro"].str.strip().isin(LINHAS_FOMENTO).any())


if __name__ == "__main__":
    unittest.main()
