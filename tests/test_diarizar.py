import unittest

import numpy as np

from vatty import diarizar
from vatty.motor import Segmento


class VozesFalsas:
    """
    Modelo de voz de mentira: cada pessoa tem um vetor-base; a janela herda o da pessoa que fala no meio dela
    (mais um pouco de ruído, semente fixa). `agenda` é [(inicio, fim, pessoa)].
    """
    nome = "falso"

    def __init__(self, agenda, dimensao=16, ruido=0.15):
        self.agenda = agenda
        rng = np.random.default_rng(7)
        self.bases = {p: rng.normal(size=dimensao) for p in {a[2] for a in agenda}}
        self.rng = np.random.default_rng(3)
        self.ruido = ruido

    def trechos_de_fala(self, amostras):
        return [(i, f) for i, f, _ in self.agenda]

    def vetor(self, pessoa):
        return self.bases[pessoa] + self.rng.normal(scale=self.ruido, size=len(self.bases[pessoa]))

    def embutir(self, amostras, jan):
        saida = []
        for ini, fim in jan:
            meio = (ini + fim) / 2
            pessoa = next(p for i, f, p in self.agenda if i <= meio <= f)
            saida.append(self.vetor(pessoa))
        return np.array(saida)


AGENDA = [(0, 8, "a"), (9, 15, "b"), (16, 24, "a"), (25, 33, "c"), (34, 40, "b"), (41, 50, "c")]


class TestJanelas(unittest.TestCase):
    def test_trecho_longo_vira_janelas_que_cobrem_ate_o_fim(self):
        j = diarizar.janelas([(0, 5)])
        self.assertEqual(j[0], (0, 2.0))
        self.assertEqual(j[-1][1], 5)
        self.assertTrue(all(abs((f - i) - 2.0) < 1e-9 for i, f in j))

    def test_trecho_curto_vira_uma_janela_e_curtissimo_some(self):
        self.assertEqual(diarizar.janelas([(3, 4.5)]), [(3, 4.5)])
        self.assertEqual(diarizar.janelas([(3, 3.5)]), [])

    def test_sem_trechos(self):
        self.assertEqual(diarizar.janelas([]), [])


class TestAgrupar(unittest.TestCase):
    def emb(self, rotulos):
        v = VozesFalsas([(0, 1, 0), (1, 2, 1), (2, 3, 2)])
        return np.array([v.vetor(r) for r in rotulos])

    def test_acha_o_numero_de_pessoas_sozinha(self):
        verdade = [0] * 8 + [1] * 8 + [2] * 8 + [0] * 8
        r = diarizar.agrupar(self.emb(verdade))
        self.assertEqual(len(set(r)), 3)
        self.assertEqual(list(r[:8]), [0] * 8)           # numerado pela ordem de aparição
        self.assertEqual(list(r[-8:]), [0] * 8)           # a primeira pessoa volta com o mesmo número

    def test_numero_fixo_respeita_o_pedido(self):
        r = diarizar.agrupar(self.emb([0] * 6 + [1] * 6 + [2] * 6), n_falantes=2)
        self.assertEqual(len(set(r)), 2)

    def test_numero_maior_que_janelas_nao_quebra(self):
        self.assertEqual(len(set(diarizar.agrupar(self.emb([0, 1]), n_falantes=5))), 2)

    def test_vazio_e_uma_janela(self):
        self.assertEqual(len(diarizar.agrupar(np.zeros((0, 4)))), 0)
        self.assertEqual(list(diarizar.agrupar(np.ones((1, 4)))), [0])

    def test_grupo_minusculo_e_ruido_no_modo_automatico(self):
        verdade = [0] * 10 + [1] * 10 + [2]   # uma janela esquisita sozinha
        r = diarizar.agrupar(self.emb(verdade))
        self.assertEqual(len(set(r)), 2)

    def test_muitas_janelas_usam_amostra_e_ainda_acham_todos(self):
        antigo = diarizar.MAX_PARA_AGRUPAR
        diarizar.MAX_PARA_AGRUPAR = 30
        try:
            r = diarizar.agrupar(self.emb(([0] * 20 + [1] * 20 + [2] * 20) * 2))
        finally:
            diarizar.MAX_PARA_AGRUPAR = antigo
        self.assertEqual(len(set(r)), 3)
        self.assertEqual(len(r), 120)


class TestPerfis(unittest.TestCase):
    def setUp(self):
        self.v = VozesFalsas([(0, 1, "ana"), (1, 2, "beto"), (2, 3, "outra")])
        self.perfis = {"Ana": self.v.bases["ana"], "Beto": self.v.bases["beto"]}

    def test_reconhece_quem_tem_perfil_e_deixa_o_resto_sem_nome(self):
        emb = np.array([self.v.vetor("ana"), self.v.vetor("beto"), self.v.vetor("outra")])
        self.assertEqual(diarizar.reconhecer(emb, self.perfis, limite=0.7), ["Ana", "Beto", None])

    def test_sem_perfis_ninguem_e_reconhecido(self):
        self.assertEqual(diarizar.reconhecer(np.ones((2, 4)), {}), [None, None])

    def test_nomear_grupos_nao_repete_o_mesmo_perfil(self):
        emb = np.array([self.v.vetor("ana") for _ in range(4)] + [self.v.vetor("ana") for _ in range(4)])
        rotulos = np.array([0] * 4 + [1] * 4)
        nomes = diarizar.nomear_grupos(emb, rotulos, {"Ana": self.v.bases["ana"]}, limite=0.7)
        self.assertEqual(len(nomes), 1)  # só um dos dois grupos leva o nome

    def test_nomear_grupos_sem_perfil(self):
        self.assertEqual(diarizar.nomear_grupos(np.ones((2, 4)), np.array([0, 0]), {}), {})


class TestTurnos(unittest.TestCase):
    def test_janelas_da_mesma_pessoa_viram_um_turno(self):
        turnos = diarizar.montar_turnos([(0, 2), (1, 3), (2, 4)], ["A", "A", "A"])
        self.assertEqual([(t.inicio, t.fim, t.pessoa) for t in turnos], [(0, 4, "A")])

    def test_troca_fica_no_meio_da_sobreposicao(self):
        turnos = diarizar.montar_turnos([(0, 2), (1, 3), (2, 4), (3, 5)], ["A", "A", "B", "B"])
        self.assertEqual([(t.pessoa, t.inicio, t.fim) for t in turnos], [("A", 0, 2.5), ("B", 2.5, 5)])

    def test_pausa_longa_separa_turnos_da_mesma_pessoa(self):
        turnos = diarizar.montar_turnos([(0, 2), (5, 7)], ["A", "A"])
        self.assertEqual(len(turnos), 2)

    def test_pausa_curta_junta(self):
        self.assertEqual(len(diarizar.montar_turnos([(0, 2), (2.5, 4.5)], ["A", "A"])), 1)

    def test_janela_isolada_entre_vizinhas_iguais_e_troca_falsa(self):
        turnos = diarizar.montar_turnos([(0, 2), (1, 3), (2, 4)], ["A", "B", "A"])
        self.assertEqual([t.pessoa for t in turnos], ["A"])

    def test_vazio(self):
        self.assertEqual(diarizar.montar_turnos([], []), [])


class TestAtribuir(unittest.TestCase):
    def turnos(self):
        return [diarizar.Turno(0, 5, "A"), diarizar.Turno(5, 10, "B")]

    def test_vence_quem_mais_falou_no_segmento(self):
        segs = [Segmento(0, 4, "oi"), Segmento(4, 9, "tchau"), Segmento(4, 6.5, "meio")]
        r = diarizar.atribuir(segs, self.turnos())
        self.assertEqual([s.pessoa for s in r], ["A", "B", "B"])

    def test_nao_mexe_nos_segmentos_originais(self):
        original = Segmento(0, 4, "oi")
        diarizar.atribuir([original], self.turnos())
        self.assertIsNone(original.pessoa)

    def test_sem_sobreposicao_pega_o_turno_proximo_ou_nada(self):
        turnos = [diarizar.Turno(0, 5, "A")]
        r = diarizar.atribuir([Segmento(5.5, 6, "perto"), Segmento(20, 21, "longe")], turnos)
        self.assertEqual([s.pessoa for s in r], ["A", None])


class TestSeparar(unittest.TestCase):
    def acertos(self, separacao):
        """Pessoa que mais falou em cada trecho da agenda."""
        saida = []
        for ini, fim, _ in AGENDA:
            tempo = {}
            for t in separacao.turnos:
                comum = min(fim, t.fim) - max(ini, t.inicio)
                if comum > 0:
                    tempo[t.pessoa] = tempo.get(t.pessoa, 0) + comum
            saida.append(max(tempo, key=tempo.get))
        return saida

    def test_agrupar_acha_as_tres_pessoas_na_ordem_certa(self):
        s = diarizar.separar(None, VozesFalsas(AGENDA), "agrupar")
        self.assertEqual(self.acertos(s), ["Pessoa 1", "Pessoa 2", "Pessoa 1", "Pessoa 3", "Pessoa 2", "Pessoa 3"])
        self.assertEqual(s.info["modo"], "agrupar")
        self.assertEqual(s.info["modelo_voz"], "falso")
        self.assertEqual(len(s.info["pessoas"]), 3)

    def test_agrupar_com_numero_fixo(self):
        s = diarizar.separar(None, VozesFalsas(AGENDA), "agrupar", n_falantes=3)
        self.assertEqual(len({p["pessoa"] for p in s.info["pessoas"]}), 3)
        self.assertEqual(s.info["falantes_pedidos"], 3)

    def test_agrupar_nomeia_quem_tem_perfil_e_numera_o_resto(self):
        v = VozesFalsas(AGENDA)
        s = diarizar.separar(None, v, "agrupar", perfis={"Ana": v.bases["a"]})
        r = self.acertos(s)
        self.assertEqual(r[0], "Ana")
        self.assertEqual(r[2], "Ana")
        self.assertEqual(sorted({r[1], r[3]}), ["Pessoa 1", "Pessoa 2"])  # a numeração segue de 1 para quem não tem perfil
        self.assertTrue(next(p for p in s.info["pessoas"] if p["pessoa"] == "Ana")["perfil"])

    def test_modo_perfis_marca_desconhecido(self):
        v = VozesFalsas(AGENDA)
        s = diarizar.separar(None, v, "perfis", perfis={"Ana": v.bases["a"], "Beto": v.bases["b"]})
        self.assertEqual(self.acertos(s), ["Ana", "Beto", "Ana", diarizar.DESCONHECIDO, "Beto", diarizar.DESCONHECIDO])

    def test_modo_perfis_sem_perfil_e_erro(self):
        with self.assertRaises(ValueError):
            diarizar.separar(None, VozesFalsas(AGENDA), "perfis")

    def test_modo_invalido(self):
        with self.assertRaises(ValueError):
            diarizar.separar(None, VozesFalsas(AGENDA), "inventado")

    def test_sem_fala_nao_quebra(self):
        class Mudo(VozesFalsas):
            def trechos_de_fala(self, amostras):
                return []
        s = diarizar.separar(None, Mudo(AGENDA), "agrupar")
        self.assertEqual(s.turnos, [])
        self.assertEqual(s.info["pessoas"], [])


class TestVetorDePerfil(unittest.TestCase):
    def test_amostra_boa(self):
        vetor, info = diarizar.vetor_de_perfil(None, VozesFalsas([(0, 20, "x")]))
        self.assertAlmostEqual(float(np.linalg.norm(vetor)), 1.0, places=4)
        self.assertGreater(info["coerencia"], 0.8)
        self.assertGreaterEqual(info["fala_s"], 20)

    def test_pouca_fala_e_recusada(self):
        with self.assertRaises(ValueError) as ctx:
            diarizar.vetor_de_perfil(None, VozesFalsas([(0, 4, "x")]))
        self.assertIn("20 a 30 s", str(ctx.exception))

    def test_duas_vozes_na_amostra_e_recusada(self):
        agenda = [(0, 8, "x"), (8, 16, "y")]
        v = VozesFalsas(agenda)
        v.bases["y"] = -v.bases["x"]  # vozes opostas: a média some
        with self.assertRaises(ValueError) as ctx:
            diarizar.vetor_de_perfil(None, v)
        self.assertIn("mais de uma voz", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
