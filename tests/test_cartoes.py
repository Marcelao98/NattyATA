import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from vatty import cartoes

MD = """## Derivadas
P: O que é a derivada?
R: A taxa de variação
instantânea de uma função.
[12:34]

P: E o limite?
R: O valor de que ela se aproxima.

## Integrais
P: Pergunta sem resposta
P: Boa?
R: Sim.
[1:02:03]
"""


class TestLer(unittest.TestCase):
    def test_le_topico_resposta_em_varias_linhas_e_horario(self):
        c = cartoes.ler(MD)
        self.assertEqual(len(c), 3)
        self.assertEqual((c[0]["topico"], c[0]["resposta"], c[0]["horario"]),
                         ("Derivadas", "A taxa de variação instantânea de uma função.", "12:34"))
        self.assertEqual(c[1]["horario"], "")

    def test_cartao_sem_resposta_e_ignorado(self):
        self.assertEqual([x["pergunta"] for x in cartoes.ler(MD)], ["O que é a derivada?", "E o limite?", "Boa?"])

    def test_vazio(self):
        self.assertEqual(cartoes.ler("texto solto"), [])


class TestCsv(unittest.TestCase):
    def test_cabecalho_tags_e_link_do_youtube(self):
        fonte = {"tipo": "youtube", "url": "https://youtu.be/x"}
        linhas = list(csv.reader(io.StringIO(cartoes.para_csv(cartoes.ler(MD), fonte))))
        self.assertEqual(linhas[0], ["Frente", "Verso", "Tags", "Origem"])
        self.assertEqual(linhas[1][2:], ["Derivadas", "https://youtu.be/x?t=754s"])
        self.assertEqual(linhas[3][3], "https://youtu.be/x?t=3723s")

    def test_sem_youtube_a_origem_e_o_horario(self):
        linhas = list(csv.reader(io.StringIO(cartoes.para_csv(cartoes.ler(MD), {"tipo": "arquivo"}))))
        self.assertEqual(linhas[1][3], "12:34")

    def test_virgula_e_aspas_no_texto_ficam_protegidas(self):
        saida = cartoes.para_csv([{"topico": "T", "pergunta": 'Diga "oi", sim?', "resposta": "a, b", "horario": ""}])
        self.assertEqual(list(csv.reader(io.StringIO(saida)))[1][:2], ['Diga "oi", sim?', "a, b"])


class TestGerar(unittest.TestCase):
    def test_gera_ao_lado_do_md_e_erra_sem_arquivo_ou_com_dois(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(cartoes.CartoesErro):
                cartoes.gerar(d)
            (Path(d) / "cartoes-a.md").write_text(MD, encoding="utf-8")
            (Path(d) / "fonte.json").write_text(json.dumps({"tipo": "arquivo"}))
            self.assertEqual(cartoes.gerar(d).name, "cartoes-a.csv")
            (Path(d) / "cartoes-b.md").write_text(MD, encoding="utf-8")
            with self.assertRaises(cartoes.CartoesErro):
                cartoes.gerar(d)
            self.assertEqual(cartoes.gerar(d, "cartoes-b.md").name, "cartoes-b.csv")

    def test_md_fora_do_formato(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "cartoes-a.md").write_text("nada", encoding="utf-8")
            with self.assertRaises(cartoes.CartoesErro):
                cartoes.gerar(d)


if __name__ == "__main__":
    unittest.main()
