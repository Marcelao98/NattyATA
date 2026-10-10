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


class ModeloComLoop(ModeloDuble):
    """Com hotwords entra em loop no 2º segmento; sem hotwords transcreve certo."""

    def __init__(self):
        super().__init__()
        self.chamadas = []

    def transcribe(self, audio, **opcoes):
        self.chamadas.append((len(audio), opcoes))
        if "hotwords" in opcoes:
            self.segmentos = [(0.0, 4.0, "A call dá direito de compra."),
                              (5.0, 9.0, "Call, put, strike, notional, delta."),
                              (10.0, 14.0, "Fim da aula.")]
        else:
            self.segmentos = [(0.3, 3.8, "O notional é quantidade vezes strike.")]
        return super().transcribe(audio, **opcoes)


class TestLoopComTermos(unittest.TestCase):
    def test_refaz_so_o_trecho_suspeito_sem_os_termos(self):
        duble = ModeloComLoop()
        r = transcrever(duble, duracao=15.0, hotwords="call, put, strike, notional, delta")
        self.assertEqual(len(duble.chamadas), 2)
        tamanho, opcoes = duble.chamadas[1]
        self.assertNotIn("hotwords", opcoes)
        self.assertIs(opcoes["vad_filter"], True)
        self.assertEqual(tamanho, int(5.0 * 16000))  # de 4.5 s a 9.5 s: folga sem invadir vizinhos
        self.assertEqual([s.texto for s in r.segmentos],
                         ["A call dá direito de compra.", "O notional é quantidade vezes strike.", "Fim da aula."])
        self.assertAlmostEqual(r.segmentos[1].inicio, 4.8)  # horário deslocado para o vídeo
        self.assertEqual(r.refeitos, [{"inicio": 4.5, "fim": 9.5, "motivo": "eco da lista de termos",
                                       "antes": "Call, put, strike, notional, delta."}])

    def test_sem_termos_nao_procura_loop(self):
        duble = ModeloDuble([(0, 1, "a a a a")])
        r = transcrever(duble)
        self.assertEqual(r.refeitos, [])

    def test_avisa_lista_longa_demais(self):
        class Tokenizador:
            def encode(self, texto):
                return type("E", (), {"ids": texto.split()})()

        duble = ModeloDuble()
        duble.hf_tokenizer = Tokenizador()
        r = transcrever(duble, hotwords=", ".join(["termo"] * 300))
        self.assertTrue(any("tokens" in a for a in r.avisos))


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
