import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np

from vatty import perfis


class TestPerfis(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pasta = Path(tmp.name) / "perfis"
        self.agora = lambda: datetime(2026, 10, 12, 15, 30)

    def criar(self, nome="Ana", **extra):
        dados = dict(vetor=[0.6, 0.8], modelo_voz="m1", consentimento=True, pasta=self.pasta, agora=self.agora)
        dados.update(extra)
        return perfis.criar(nome, **dados)

    def test_cria_so_com_vetor_e_registro_do_consentimento(self):
        arquivo = self.criar(info={"fala_s": 20.0})
        d = json.loads(arquivo.read_text(encoding="utf-8"))
        self.assertEqual(d["nome"], "Ana")
        self.assertEqual(d["vetor"], [0.6, 0.8])
        self.assertTrue(d["consentimento"]["confirmado"])
        self.assertEqual(d["consentimento"]["data"], "2026-10-12")
        self.assertEqual(d["amostra"], {"fala_s": 20.0})
        self.assertEqual([p.name for p in self.pasta.iterdir()], ["ana.json"])  # nenhum áudio

    def test_sem_consentimento_recusa_e_nao_cria_nada(self):
        for valor in (False, None, "sim"):
            with self.assertRaises(perfis.PerfilErro):
                self.criar(consentimento=valor)
        self.assertFalse(self.pasta.exists())

    def test_nome_vazio_ou_parecido_com_rotulo_automatico(self):
        for nome in ("", "  ", "Pessoa 3", "desconhecido", "Eu", "outros"):
            with self.assertRaises(perfis.PerfilErro):
                self.criar(nome)

    def test_nome_repetido_exige_substituir(self):
        self.criar()
        with self.assertRaises(perfis.PerfilErro):
            self.criar()
        self.criar(vetor=[1.0, 0.0], substituir=True)
        vetores, _ = perfis.carregar("m1", self.pasta)
        np.testing.assert_allclose(vetores["Ana"], [1.0, 0.0])

    def test_listar_nao_mostra_o_vetor(self):
        self.criar("Ana")
        self.criar("Beto")
        lista = perfis.listar(self.pasta)
        self.assertEqual([d["nome"] for d in lista], ["Ana", "Beto"])
        self.assertNotIn("vetor", lista[0])
        self.assertEqual(perfis.listar(self.pasta / "nao-existe"), [])

    def test_carregar_ignora_perfil_de_outro_modelo_com_aviso(self):
        self.criar("Ana")
        self.criar("Beto", modelo_voz="outro")
        vetores, avisos = perfis.carregar("m1", self.pasta)
        self.assertEqual(list(vetores), ["Ana"])
        self.assertIn("Beto", avisos[0])

    def test_carregar_so_os_pedidos_e_avisa_dos_que_faltam(self):
        self.criar("Ana")
        self.criar("Beto")
        vetores, avisos = perfis.carregar("m1", self.pasta, so_nomes=["beto", "Carla"])
        self.assertEqual(list(vetores), ["Beto"])
        self.assertIn("Carla", avisos[0])

    def test_arquivo_estragado_vira_aviso(self):
        self.criar("Ana")
        (self.pasta / "ruim.json").write_text("{nao e json", encoding="utf-8")
        vetores, avisos = perfis.carregar("m1", self.pasta)
        self.assertEqual(list(vetores), ["Ana"])
        self.assertIn("ruim.json", avisos[0])

    def test_apagar(self):
        self.criar()
        perfis.apagar("Ana", self.pasta)
        self.assertEqual(perfis.listar(self.pasta), [])
        with self.assertRaises(perfis.PerfilErro):
            perfis.apagar("Ana", self.pasta)

    def test_pasta_vem_da_variavel_de_ambiente(self):
        import os
        antigo = os.environ.get("VATTY_PERFIS")
        os.environ["VATTY_PERFIS"] = str(self.pasta)
        try:
            self.assertEqual(perfis.pasta_perfis(), self.pasta)
        finally:
            if antigo is None:
                del os.environ["VATTY_PERFIS"]
            else:
                os.environ["VATTY_PERFIS"] = antigo


if __name__ == "__main__":
    unittest.main()
