import unittest

from natty_ata.motor import Segmento
from natty_ata.texto import DURACAO_MAX_PARAGRAFO_S, PAUSA_PARAGRAFO_S, formatar, juntar_em_paragrafos


class TestParagrafos(unittest.TestCase):
    def test_pausa_curta_junta(self):
        segs = [Segmento(0.0, 4.0, "Vocês entram"), Segmento(4.5, 8.0, "na taverna.")]
        self.assertEqual(juntar_em_paragrafos(segs), ["Vocês entram na taverna."])

    def test_pausa_longa_separa(self):
        segs = [Segmento(0.0, 4.0, "Fim da cena."), Segmento(4.0 + PAUSA_PARAGRAFO_S + 0.1, 9.0, "Outra cena.")]
        self.assertEqual(juntar_em_paragrafos(segs), ["Fim da cena.", "Outra cena."])

    def test_pausa_igual_ao_limite_separa(self):
        segs = [Segmento(0.0, 1.0, "a"), Segmento(1.0 + PAUSA_PARAGRAFO_S, 4.0, "b")]
        self.assertEqual(juntar_em_paragrafos(segs), ["a", "b"])

    def test_fala_sem_pausa_quebra_pela_duracao(self):
        # como a legenda automática: segmentos colados, sem pausa nenhuma
        segs = [Segmento(t, t + 10, f"s{t}") for t in range(0, 130, 10)]
        paragrafos = juntar_em_paragrafos(segs, duracao_max=DURACAO_MAX_PARAGRAFO_S)
        self.assertEqual(paragrafos, ["s0 s10 s20 s30 s40 s50", "s60 s70 s80 s90 s100 s110", "s120"])

    def test_ignora_texto_vazio(self):
        segs = [Segmento(0.0, 1.0, "a"), Segmento(1.2, 1.5, "  "), Segmento(1.6, 2.0, "b")]
        self.assertEqual(juntar_em_paragrafos(segs), ["a b"])

    def test_formatar_com_linha_em_branco(self):
        self.assertEqual(formatar(["um", "dois"]), "um\n\ndois\n")
        self.assertEqual(formatar([]), "")


if __name__ == "__main__":
    unittest.main()
