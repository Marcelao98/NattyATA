import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vatty import glossario
from vatty.motor import Segmento


class TestLer(unittest.TestCase):
    def test_le_regras_e_ignora_comentario_e_vazio(self):
        self.assertEqual(glossario.ler("# nomes\n\nNatty = Nattie\n  ata=ATA \n"), {"Natty": "Nattie", "ata": "ATA"})

    def test_linha_sem_igual_ou_sem_lado_e_erro(self):
        for ruim in ("so um lado", "= certo", "errado ="):
            with self.assertRaises(glossario.GlossarioErro):
                glossario.ler(ruim)


class TestCorrigirTexto(unittest.TestCase):
    def test_palavra_inteira_sem_diferenciar_maiuscula(self):
        texto, n = glossario.corrigir_texto("A natty e a Natal, NATTY!", {"Natty": "Nattie"})
        self.assertEqual(texto, "A Nattie e a Natal, Nattie!")
        self.assertEqual(n, {"Natty": 2})

    def test_regra_maior_vence_a_menor(self):
        texto, _ = glossario.corrigir_texto("visual studio", {"visual": "V", "visual studio": "VS Code"})
        self.assertEqual(texto, "VS Code")

    def test_caractere_especial_no_errado_nao_quebra(self):
        texto, _ = glossario.corrigir_texto("usa c++ hoje", {"c++": "C++"})
        self.assertEqual(texto, "usa C++ hoje")


class TestAplicar(unittest.TestCase):
    def test_nao_altera_os_originais_e_soma_contagem(self):
        orig = [Segmento(0, 1, "natty fala", falante="eu"), Segmento(1, 2, "outra coisa"), Segmento(2, 3, "Natty")]
        novos, cont = glossario.aplicar(orig, {"natty": "Nattie"})
        self.assertEqual([s.texto for s in novos], ["Nattie fala", "outra coisa", "Nattie"])
        self.assertEqual(orig[0].texto, "natty fala")
        self.assertEqual(novos[0].falante, "eu")
        self.assertEqual(cont, {"natty": 2})

    def test_sem_regras_nada_muda(self):
        orig = [Segmento(0, 1, "oi")]
        self.assertEqual(glossario.aplicar(orig, {}), (orig, {}))


class TestArquivoPadrao(unittest.TestCase):
    def test_variavel_de_ambiente_manda(self):
        with mock.patch.dict(os.environ, {"VATTY_GLOSSARIO": "/tmp/x.txt"}):
            self.assertEqual(glossario.arquivo_padrao(), Path("/tmp/x.txt"))


if __name__ == "__main__":
    unittest.main()
