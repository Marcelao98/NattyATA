import unittest
from types import SimpleNamespace

import numpy as np

from natty_ata import motor


class ModeloDuble:
    """Faz o papel do WhisperModel: guarda o que recebeu e devolve segmentos prontos."""

    def __init__(self, segmentos=(), idioma="pt"):
        self.segmentos = segmentos
        self.idioma = idioma
        self.audio = None
        self.opcoes = None

    def transcribe(self, audio, **opcoes):
        self.audio, self.opcoes = audio, opcoes
        brutos = (SimpleNamespace(start=a, end=b, text=t) for a, b, t in self.segmentos)
        return brutos, SimpleNamespace(language=self.idioma)


def transcrever(duble, duracao=10.0, **kwargs):
    array = np.zeros(int(duracao * 16000), dtype=np.float32)
    return motor.transcrever(
        "sessao.opus",
        carregar_audio=lambda caminho: (array, duracao),
        obter_modelo=lambda nome: duble,
        **kwargs,
    )


class TestParametros(unittest.TestCase):
    def test_padroes_provados_na_sessao_real(self):
        duble = ModeloDuble()
        transcrever(duble)
        self.assertEqual(duble.opcoes["language"], "pt")
        self.assertIs(duble.opcoes["vad_filter"], True)
        self.assertIs(duble.opcoes["condition_on_previous_text"], False)
        self.assertNotIn("hotwords", duble.opcoes)

    def test_recebe_array_e_nao_caminho(self):
        duble = ModeloDuble()
        transcrever(duble)
        self.assertIsInstance(duble.audio, np.ndarray)

    def test_hotwords_so_quando_passado(self):
        duble = ModeloDuble()
        transcrever(duble, hotwords="Nhalor, Vorric")
        self.assertEqual(duble.opcoes["hotwords"], "Nhalor, Vorric")

    def test_hotwords_vazio_continua_desligado(self):
        duble = ModeloDuble()
        transcrever(duble, hotwords="")
        self.assertNotIn("hotwords", duble.opcoes)

    def test_auto_vira_none(self):
        duble = ModeloDuble(idioma="en")
        resultado = transcrever(duble, idioma="auto")
        self.assertIsNone(duble.opcoes["language"])
        self.assertEqual(resultado.idioma, "en")


class TestResultado(unittest.TestCase):
    def test_segmentos_e_metadados(self):
        duble = ModeloDuble([(0.0, 2.5, " Olá, mesa. "), (3.0, 6.0, "Rolem iniciativa.")])
        resultado = transcrever(duble, duracao=8.0, modelo="small")
        self.assertEqual(resultado.fonte, "sessao.opus")
        self.assertEqual(resultado.duracao_s, 8.0)
        self.assertEqual(resultado.modelo, "small")
        self.assertEqual(resultado.idioma, "pt")
        self.assertEqual(
            resultado.segmentos,
            [motor.Segmento(0.0, 2.5, "Olá, mesa."), motor.Segmento(3.0, 6.0, "Rolem iniciativa.")],
        )

    def test_progresso(self):
        chamadas = []
        duble = ModeloDuble([(0.0, 2.0, "a"), (3.0, 5.0, "b")])
        transcrever(duble, duracao=8.0, progresso=lambda atual, total: chamadas.append((atual, total)))
        self.assertEqual(chamadas, [(2.0, 8.0), (5.0, 8.0), (8.0, 8.0)])


class TestTermos(unittest.TestCase):
    def test_um_por_linha_ignorando_vazios_e_comentarios(self):
        conteudo = "# nomes da campanha\nNhalor\n\n  Vorric  \nElijah Vorren # NPC\n"
        self.assertEqual(motor.ler_termos(conteudo), "Nhalor, Vorric, Elijah Vorren")


class TestCarregamentoPreguicoso(unittest.TestCase):
    def test_reaproveita_modelo_ja_carregado(self):
        sentinela = object()
        motor._MODELOS["dublê"] = sentinela
        try:
            self.assertIs(motor.carregar_modelo("dublê"), sentinela)
        finally:
            del motor._MODELOS["dublê"]


if __name__ == "__main__":
    unittest.main()
