import json
import tempfile
import unittest
from pathlib import Path

from vatty import srt


def seg(i, f, t, **extra):
    return {"inicio": i, "fim": f, "texto": t, **extra}


class TestHorario(unittest.TestCase):
    def test_srt_usa_virgula_e_vtt_usa_ponto(self):
        self.assertEqual(srt.horario(3662.5, "srt"), "01:01:02,500")
        self.assertEqual(srt.horario(3662.5, "vtt"), "01:01:02.500")

    def test_negativo_vira_zero(self):
        self.assertEqual(srt.horario(-1, "srt"), "00:00:00,000")


class TestBlocos(unittest.TestCase):
    def test_segmento_curto_vira_um_bloco(self):
        self.assertEqual(srt.blocos([seg(1, 3, "Oi gente")]), [(1, 3, "Oi gente")])

    def test_segmento_vazio_sai(self):
        self.assertEqual(srt.blocos([seg(0, 1, "   ")]), [])

    def test_segmento_longo_divide_a_duracao_sem_perder_texto(self):
        texto = " ".join(["palavra"] * 30)
        res = srt.blocos([seg(0, 10, texto)])
        self.assertGreater(len(res), 1)
        self.assertEqual(res[0][0], 0)
        self.assertAlmostEqual(res[-1][1], 10)
        for _, _, t in res:
            self.assertLessEqual(len(t.split("\n")), srt.LINHAS_POR_BLOCO)
        self.assertEqual(" ".join(t.replace("\n", " ") for _, _, t in res), texto)

    def test_pessoa_e_falante_viram_prefixo(self):
        self.assertEqual(srt.blocos([seg(0, 1, "oi", pessoa="Ana")])[0][2], "Ana: oi")
        self.assertEqual(srt.blocos([seg(0, 1, "oi", falante="eu")])[0][2], "Eu: oi")


class TestMontar(unittest.TestCase):
    def test_srt_numera_blocos(self):
        texto = srt.montar([seg(0, 1, "a"), seg(1, 2, "b")], "srt")
        self.assertIn("1\n00:00:00,000 --> 00:00:01,000\na\n", texto)
        self.assertIn("2\n00:00:01,000 --> 00:00:02,000\nb\n", texto)

    def test_vtt_tem_cabecalho_e_nao_numera(self):
        texto = srt.montar([seg(0, 1, "a")], "vtt")
        self.assertTrue(texto.startswith("WEBVTT\n"))
        self.assertNotIn("\n1\n", texto)

    def test_formato_desconhecido(self):
        with self.assertRaises(srt.LegendaErro):
            srt.montar([], "ass")


class TestGerar(unittest.TestCase):
    def test_escreve_os_arquivos(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "transcricao.json").write_text(json.dumps({"segmentos": [seg(0, 1, "oi")]}), encoding="utf-8")
            caminhos = srt.gerar(d, ("srt", "vtt"))
            self.assertEqual([c.name for c in caminhos], ["legenda.srt", "legenda.vtt"])
            self.assertIn("oi", caminhos[0].read_text(encoding="utf-8"))

    def test_sem_transcricao(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(srt.LegendaErro):
            srt.gerar(d)


if __name__ == "__main__":
    unittest.main()
