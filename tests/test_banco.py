import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))

from carregar import DADOS, RAIZ, TABELAS, conectar, database_url

CONFIGURADO = (RAIZ / ".env").exists() and (RAIZ / "ca.pem").exists()


@unittest.skipUnless(CONFIGURADO, "sem .env ou ca.pem: banco não configurado")
class BancoCarregado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = conectar(database_url())

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def contar(self, sql):
        return self.conn.run(sql)[0][0]

    def test_cada_tabela_tem_as_linhas_do_arquivo_tratado(self):
        for tabela in TABELAS:
            with self.subTest(tabela=tabela), (DADOS / f"{tabela}.csv").open(encoding="utf-8") as f:
                linhas = sum(1 for _ in f) - 1
                self.assertEqual(self.contar(f"SELECT count(*) FROM {tabela}"), linhas)

    def test_taxa_de_atendimento_bate_com_as_quantidades(self):
        divergentes = self.contar("SELECT count(*) FROM fato_atendimento_grupo "
                                  "WHERE taxa_atendimento <> round(qtd_atendida::numeric / qtd_demandada, 4)")
        self.assertEqual(divergentes, 0)

    def test_views_retornam_dados(self):
        self.assertGreater(self.contar("SELECT count(*) FROM vw_diferenca_grupo"), 0)
        self.assertEqual(self.contar("SELECT count(*) FROM vw_diferenca_grupo WHERE diferenca_grupo IS NULL"), 0)
        self.assertGreater(self.contar("SELECT count(*) FROM vw_reconciliacao_fontes"), 0)

    def test_reconciliacao_soma_os_totais_das_fontes(self):
        painel, csv = self.conn.run("SELECT sum(qtd_demandada_painel), sum(qtd_demandada_csv) FROM vw_reconciliacao_fontes")[0]
        self.assertEqual(painel, self.contar("SELECT sum(qtd_demandada) FROM fato_atendimento_grupo"))
        self.assertEqual(csv, self.contar("SELECT count(*) FROM processo_tratado"))

    def test_tamanho_dentro_da_meta(self):
        self.assertLess(self.contar("SELECT pg_database_size(current_database())"), 650 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
