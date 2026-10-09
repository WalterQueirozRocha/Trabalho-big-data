import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))

import tratar
from tratar import (CSV_ORIGINAL, LINHAS_FOMENTO, NAO_INFORMADO, NAO_SE_APLICA, RACAS, SAIDA, SEXOS, UF_REFERENCIA, UFS,
                    categoria, chave, corrigir_grande_area, corrigir_valores, filtrar, inferir_modalidade, padronizar,
                    padronizar_grafias, padronizar_siglas, padronizar_uf, remover_duplicados, texto)


def lista(serie):
    return [None if pd.isna(v) else v for v in serie]


class Limpeza(unittest.TestCase):
    def test_modalidade_vazia_vem_das_outras_edicoes_da_chamada(self):
        df = pd.DataFrame({"chamada": ["PQ - 2023", "PQ - 2024", "X 2023", "X 2023", "X 2024"],
                           "modalidade": ["Produtividade em Pesquisa", None, "A", "B", None]})
        inferir_modalidade(df, "teste")
        self.assertEqual(list(df["modalidade"]), ["Produtividade em Pesquisa", "Produtividade em Pesquisa", "A", "B",
                                                  NAO_INFORMADO])

    def test_grande_area_segue_a_classificacao_predominante_da_area(self):
        df = pd.DataFrame({"area": ["Biotecnologia"] * 20 + ["Física"],
                           "grande_area": ["Ciências Biológicas"] * 19 + ["Tecnologias", "Ciências Exatas e da Terra"],
                           "qtd_demandada": 1})
        corrigir_grande_area(df, "teste")
        self.assertEqual(set(df.loc[df["area"] == "Biotecnologia", "grande_area"]), {"Ciências Biológicas"})

    def test_remove_duplicado_exato_e_mantem_o_primeiro_processo(self):
        df = pd.DataFrame({"nu_processo": ["000002/2024-0", "000001/2024-0"], "ano_chamada": ["2024"] * 2,
                           "chamada": ["PDJ 2024"] * 2, "titulo": ["Não Informado"] * 2, "palavras_chave": ["x"] * 2,
                           "sigla_instituicao": ["USP"] * 2, "area": ["Física"] * 2, "modalidade": ["PDJ"] * 2,
                           "st_atendimento": ["N"] * 2})
        self.assertEqual(list(remover_duplicados(df)["nu_processo"]), ["000001/2024-0"])

    def test_reenvio_mantem_o_atendido_ou_o_ultimo_envio(self):
        comum = {"ano_chamada": ["2024"] * 4, "chamada": ["PDJ 2024"] * 4,
                 "sigla_instituicao": ["USP"] * 4, "area": ["Física"] * 4, "modalidade": ["PDJ"] * 4}
        df = pd.DataFrame({"nu_processo": ["000001/2024-0", "000002/2024-0", "000003/2024-0", "000004/2024-0"],
                           "titulo": ["Projeto A", "Projeto A", "Projeto B", "projeto  b"],
                           "st_atendimento": ["S", "N", "N", "N"], "valor": [1, 2, 3, 4], **comum})
        self.assertEqual(sorted(remover_duplicados(df)["nu_processo"]), ["000001/2024-0", "000004/2024-0"])

    def test_reenvio_ignora_acento_pontuacao_e_palavras_chave(self):
        df = pd.DataFrame({"nu_processo": ["000001/2024-0", "000002/2024-0"], "ano_chamada": ["2024"] * 2,
                           "chamada": ["GDE 2019"] * 2, "titulo": ["Indústria 4.0: CNC", "industria 4 0 cnc"],
                           "palavras_chave": ["IoT;CNC", "CNC;IoT;CAM"], "sigla_instituicao": ["UMINHO"] * 2,
                           "area": ["Engenharias"] * 2, "modalidade": ["GDE"] * 2, "st_atendimento": ["N"] * 2})
        self.assertEqual(list(remover_duplicados(df)["nu_processo"]), ["000002/2024-0"])

    def test_grafias_unificadas_na_forma_mais_completa(self):
        df = pd.DataFrame({"cidade": ["Sao Paulo", "Sao Paulo", "SAO PAULO", "São Paulo", "Itauna", "Itabuna"]})
        padronizar_grafias(df, ["cidade"], "teste")
        self.assertEqual(list(df["cidade"]), ["São Paulo"] * 4 + ["Itauna", "Itabuna"])

    def test_uf_pela_lista_oficial(self):
        df = pd.DataFrame({"sigla_uf": ["BA", "", "XX", "\\EX", "SP"],
                           "nome_uf": ["Bahia", "bahia", "Baia", "Exterior", "SAO PAULO"],
                           "regiao": ["Sul", "Nordeste", "Nordeste", "Exterior", "Sudeste"]})
        padronizar_uf(df)
        self.assertEqual(lista(df["sigla_uf"]), ["BA", "BA", "BA", None, "SP"])
        self.assertEqual(list(df["regiao"]), ["Nordeste", "Nordeste", "Nordeste", "Exterior", "Sudeste"])

    def test_chave_ignora_acento_caixa_e_pontuacao(self):
        self.assertEqual(lista(chave(pd.Series(["São-Paulo ", "SAO PAULO", "sao.paulo"]))), ["SAO PAULO"] * 3)

    def test_titulo_nao_informado_nao_conta_como_reenvio(self):
        df = pd.DataFrame({"nu_processo": ["000001/2024-0", "000002/2024-0"], "ano_chamada": ["2024"] * 2,
                           "chamada": ["PQ - 2024"] * 2, "titulo": ["Não Informado"] * 2, "palavras_chave": ["x"] * 2,
                           "sigla_instituicao": ["USP"] * 2, "area": ["Física"] * 2, "modalidade": ["PQ"] * 2,
                           "st_atendimento": ["N"] * 2, "valor": [1, 2]})
        self.assertEqual(len(remover_duplicados(df)), 2)

    def test_siglas_unificadas_por_nome_e_uf(self):
        df = pd.DataFrame({"sigla_instituicao": ["PUC-Rio", "PUC-Rio", "PUC/RJ", "Fiocruz", "FIOCRUZ", "IFBA", "IFSertaoPE"],
                           "instituicao": ["PUC RIO"] * 3 + ["FUNDACAO OSWALDO CRUZ"] * 2 + ["INSTITUTO FEDERAL"] * 2,
                           "sigla_uf": ["RJ"] * 5 + ["BA", "PE"]})
        padronizar_siglas(df)
        self.assertEqual(list(df["sigla_instituicao"]),
                         ["PUC-RIO", "PUC-RIO", "PUC-RIO", "FIOCRUZ", "FIOCRUZ", "IFBA", "IFSERTAOPE"])

    def test_valores_zero_virgula_deslocada_e_implausivel(self):
        bolsas = [68160.0] * 30 + [6816000.0, 0.0]
        projetos = [40000.0] * 25 + [5000000.0]
        df = pd.DataFrame({"modalidade": ["Pós-Doutorado Júnior"] * 32 + [NAO_SE_APLICA] * 26,
                           "chamada": ["PDJ 2024"] * 32 + ["Universal 2024"] * 26,
                           "valor_demandado": bolsas + projetos, "valor_atendido": 0.0})
        corrigir_valores(df)
        self.assertEqual(df["valor_demandado"].iloc[30], 68160.0)
        self.assertTrue(pd.isna(df["valor_demandado"].iloc[31]))
        self.assertTrue(pd.isna(df["valor_demandado"].iloc[-1]))
        self.assertEqual(df["valor_demandado"].iloc[0], 68160.0)


class Regras(unittest.TestCase):
    def test_texto_remove_espacos_excedentes_e_vazios(self):
        self.assertEqual(lista(texto(pd.Series(["  Bolsas   no  País ", "", None], dtype=str))),
                         ["Bolsas no País", None, None])

    def test_categoria_agrupa_nao_declarado_e_ausente(self):
        serie = pd.Series(["Feminino", " Masculino ", "Não desejo declarar", None], dtype=str)
        self.assertEqual(list(categoria(serie, SEXOS)), ["Feminino", "Masculino", NAO_INFORMADO, NAO_INFORMADO])

    def test_padronizar_converte_ano_regiao_e_vazios(self):
        df = padronizar(pd.DataFrame({
            "ano_chamada": ["2019", " INTELIGÊNCIA"], "chamada": [" PQ  - 2019", "X"],
            "linha_fomento": [" Bolsas no País", "Prêmios"], "grande_area": [None, "Engenharias"],
            "area": ["", "Física"], "modalidade": ["", "Produtividade em Pesquisa"], "regiao": ["SE", "\\EX"],
        }, dtype=str))
        self.assertEqual(df["ano_chamada"].iloc[0], 2019)
        self.assertTrue(pd.isna(df["ano_chamada"].iloc[1]))
        self.assertEqual(df["chamada"].iloc[0], "PQ - 2019")
        self.assertEqual(list(df["regiao"]), ["Sudeste", "Exterior"])
        self.assertEqual(df["grande_area"].iloc[0], NAO_INFORMADO)
        self.assertEqual(df["area"].iloc[0], NAO_INFORMADO)
        self.assertTrue(pd.isna(df["modalidade"].iloc[0]))

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

    def test_valores_conhecidos_sao_positivos(self):
        self.assertTrue((self.processos["valor_demandado"].dropna() > 0).all())
        self.assertTrue((self.processos["valor_atendido"].dropna() >= 0).all())

    def test_uma_grafia_por_cidade_e_instituicao(self):
        for coluna in ("cidade", "instituicao", "pais"):
            with self.subTest(coluna=coluna):
                valores = self.processos[coluna].dropna()
                self.assertTrue((valores.groupby(chave(valores)).nunique() == 1).all())

    def test_uf_coerente_com_a_regiao(self):
        regioes = {nome: id_ for id_, nome in self.dims["dim_regiao"][["id", "nome"]].itertuples(index=False)}
        com_uf = self.processos.dropna(subset=["sigla_uf"])
        esperado = com_uf["sigla_uf"].map(lambda s: regioes[UF_REFERENCIA[s][1]])
        self.assertTrue((com_uf["regiao_id"] == esperado).all())

    def test_siglas_em_maiusculas_e_sem_acento(self):
        siglas = self.processos["sigla_instituicao"].dropna()
        self.assertTrue((siglas == siglas.str.upper()).all())
        self.assertTrue(siglas.str.isascii().all())

    @unittest.skipUnless(CSV_ORIGINAL.exists(), "CSV original ausente")
    def test_removidos_do_original_estao_explicados_no_log(self):
        original = pd.read_csv(CSV_ORIGINAL, sep=";", dtype=str, usecols=["nu_processo", "nme_chamada_macro"])
        mantidos = set(self.processos["nu_processo"])
        removidos = original[~original["nu_processo"].isin(mantidos)]
        no_recorte = removidos["nme_chamada_macro"].str.strip().isin(LINHAS_FOMENTO).sum()
        log = pd.read_csv(SAIDA / "log_tratamento.csv").set_index("etapa")["linhas"]
        duplicados = log.filter(like="duplicados exatos").sum() + log.filter(like="reenvios").sum()
        self.assertTrue(mantidos <= set(original["nu_processo"]))
        self.assertEqual(no_recorte, duplicados)


if __name__ == "__main__":
    unittest.main()
