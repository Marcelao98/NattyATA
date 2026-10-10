import unittest

from natty_ata.motor import Segmento
from natty_ata import texto
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

    def test_falante_abre_paragrafo_com_rotulo(self):
        segs = [
            Segmento(0.0, 2.0, "Bom dia.", "outros"), Segmento(2.2, 4.0, "Vamos começar.", "outros"),
            Segmento(4.5, 5.5, "Bom dia!", "eu"), Segmento(6.0, 7.0, "Certo.", "outros"),
        ]
        self.assertEqual(juntar_em_paragrafos(segs),
                         ["Outros: Bom dia. Vamos começar.", "Eu: Bom dia!", "Outros: Certo."])

    def test_sem_falante_nao_ganha_rotulo(self):
        self.assertEqual(juntar_em_paragrafos([Segmento(0.0, 1.0, "oi")]), ["oi"])

    def test_formatar_com_linha_em_branco(self):
        self.assertEqual(formatar(["um", "dois"]), "um\n\ndois\n")
        self.assertEqual(formatar([]), "")


class TestCanaisSeparados(unittest.TestCase):
    # Trecho real de uma chamada de 11 min: a fala de "eu" no meio da frase de
    # "outros" não pode partir a frase.
    EXEMPLO = [
        Segmento(0.0, 3.0, "Eu já fiz um vídeo antes, mas", "outros"),
        Segmento(3.2, 4.0, "Vamos ver", "eu"),
        Segmento(3.5, 6.0, "eu quero que esse seja o tutorial", "outros"),
    ]

    def test_frase_de_um_canal_nao_e_partida_pela_fala_do_outro(self):
        canais = texto.por_canal(self.EXEMPLO)
        self.assertEqual(canais["outros"], [(0.0, "Eu já fiz um vídeo antes, mas eu quero que esse seja o tutorial")])
        self.assertEqual(canais["eu"], [(3.2, "Vamos ver")])

    def test_linha_do_tempo_ordena_os_paragrafos_prontos_pelo_inicio(self):
        canais = texto.por_canal(self.EXEMPLO)
        self.assertEqual(texto.linha_do_tempo(canais),
                         "[00:00] Outros: Eu já fiz um vídeo antes, mas eu quero que esse seja o tutorial\n\n"
                         "[00:03] Eu: Vamos ver\n")

    def test_cada_canal_segue_as_mesmas_regras_de_pausa_e_duracao(self):
        segs = [Segmento(0.0, 4.0, "Fim da cena.", "eu"), Segmento(4.0 + PAUSA_PARAGRAFO_S + 0.1, 9.0, "Outra.", "eu"),
                Segmento(0.0, 1.0, "oi", "outros")]
        canais = texto.por_canal(segs)
        self.assertEqual([t for _, t in canais["eu"]], ["Fim da cena.", "Outra."])
        # fala contínua passa da duração máxima e abre outro parágrafo
        longos = [Segmento(t, t + 10, f"s{t}", "outros") for t in range(0, 130, 10)]
        self.assertEqual([t for _, t in texto.por_canal(longos)["outros"]],
                         ["s0 s10 s20 s30 s40 s50", "s60 s70 s80 s90 s100 s110", "s120"])

    def test_formatar_canal_com_horario_no_comeco_de_cada_paragrafo(self):
        self.assertEqual(texto.formatar_canal([(5.0, "um"), (75.4, "dois")]), "[00:05] um\n\n[01:15] dois\n")
        self.assertEqual(texto.formatar_canal([]), "")

    def test_horario_passa_para_h_mm_ss_a_partir_de_1_hora(self):
        self.assertEqual(texto.horario(0), "[00:00]")
        self.assertEqual(texto.horario(3599.9), "[59:59]")
        self.assertEqual(texto.horario(3600), "[1:00:00]")
        self.assertEqual(texto.horario(3723), "[1:02:03]")

    def test_empate_de_horario_fica_na_ordem_dos_canais(self):
        canais = {"outros": [(2.0, "a")], "eu": [(2.0, "b")]}
        self.assertEqual(texto.linha_do_tempo(canais), "[00:02] Outros: a\n\n[00:02] Eu: b\n")

    def test_duas_faixas(self):
        self.assertTrue(texto.duas_faixas(self.EXEMPLO))
        self.assertFalse(texto.duas_faixas([Segmento(0.0, 1.0, "oi", "eu")]))
        self.assertFalse(texto.duas_faixas([Segmento(0.0, 1.0, "oi")]))


if __name__ == "__main__":
    unittest.main()
