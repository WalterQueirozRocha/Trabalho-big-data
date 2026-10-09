import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))

from extrair_painel import COLUNAS, MEDIDAS, SOMAS, decodificar_dsr, montar_consulta


def ds(linhas, dicionarios=None):
    return {"ValueDicts": dicionarios or {}, "PH": [{"DM0": linhas}]}


class DecodificarDsr(unittest.TestCase):
    schema = [{"N": "G0", "DN": "D0"}, {"N": "G1", "DN": "D1"}, {"N": "M0"}]
    dicionarios = {"D0": ["2019"], "D1": ["Feminino", "Masculino"]}

    def test_traduz_indices_pelo_dicionario(self):
        linhas = decodificar_dsr(ds([{"S": self.schema, "C": [0, 1, 7]}], self.dicionarios))
        self.assertEqual(linhas, [["2019", "Masculino", 7]])

    def test_repete_colunas_marcadas_em_r(self):
        linhas = decodificar_dsr(ds([{"S": self.schema, "C": [0, 0, 5]}, {"C": [1, 3], "R": 1}], self.dicionarios))
        self.assertEqual(linhas[1], ["2019", "Masculino", 3])

    def test_anula_colunas_marcadas_em_nulo(self):
        linhas = decodificar_dsr(ds([{"S": self.schema, "C": [0, 0, 5]}, {"C": [1], "R": 1, "Ø": 4}], self.dicionarios))
        self.assertEqual(linhas[1], ["2019", "Masculino", None])

    def test_mantem_valor_literal_fora_do_dicionario(self):
        linhas = decodificar_dsr(ds([{"S": self.schema, "C": ["2020", "Feminino", 2]}], self.dicionarios))
        self.assertEqual(linhas, [["2020", "Feminino", 2]])

    def test_resposta_vazia(self):
        self.assertEqual(decodificar_dsr(ds([])), [])


class MontarConsulta(unittest.TestCase):
    def setUp(self):
        self.consulta = montar_consulta({"id": 123, "dbName": "base"}, 2021)
        self.query = self.consulta["queries"][0]["Query"]["Commands"][0]["SemanticQueryDataShapeCommand"]["Query"]

    def test_seleciona_dimensoes_medidas_e_somas(self):
        self.assertEqual(len(self.query["Select"]), len(COLUNAS) + len(MEDIDAS) + len(SOMAS))

    def test_filtra_um_unico_ano(self):
        valores = self.query["Where"][0]["Condition"]["In"]["Values"]
        self.assertEqual(valores, [[{"Literal": {"Value": "'2021'"}}]])

    def test_usa_o_modelo_informado(self):
        self.assertEqual(self.consulta["modelId"], 123)
        self.assertEqual(self.consulta["queries"][0]["ApplicationContext"]["DatasetId"], "base")


if __name__ == "__main__":
    unittest.main()
