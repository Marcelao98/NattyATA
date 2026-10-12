import json
import tempfile
import unittest
from pathlib import Path

from vatty import acervo


def video(raiz, slug, texto, **fonte):
    p = Path(raiz) / slug
    p.mkdir()
    (p / "fonte.json").write_text(json.dumps({"titulo": slug.upper(), **fonte}))
    (p / "transcricao.txt").write_text(texto, encoding="utf-8")


class TestTermos(unittest.TestCase):
    def test_tira_palavra_comum_acento_e_repeticao(self):
        self.assertEqual(acervo.termos("O que o professor disse sobre a Margem de margem?"), ["professor", "disse", "margem"])


class TestSelecionar(unittest.TestCase):
    def test_ordena_por_termos_distintos_e_traz_link_do_youtube(self):
        with tempfile.TemporaryDirectory() as d:
            video(d, "a", "[00:10] a margem sobe\n\n[00:20] margem de segurança e risco do contrato\n",
                  tipo="youtube", url="https://youtu.be/x")
            video(d, "b", "[01:00] nada a ver\n")
            r = acervo.selecionar("margem segurança risco", d)
            self.assertEqual([t["horario"] for t in r], ["[00:20]"])
            self.assertEqual(r[0]["link"], "https://youtu.be/x?t=20s")

    def test_pergunta_curta_basta_um_termo_e_limita_n(self):
        with tempfile.TemporaryDirectory() as d:
            video(d, "a", "\n\n".join(f"[00:{i:02d}] margem {i}" for i in range(10)) + "\n")
            self.assertEqual(len(acervo.selecionar("margem", d, n=3)), 3)

    def test_pergunta_so_de_palavra_comum_ou_raiz_inexistente(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(acervo.selecionar("o que é isso?", d), [])
        self.assertEqual(acervo.selecionar("margem", "/nao/existe"), [])

    def test_ignora_a_pasta_de_consultas(self):
        with tempfile.TemporaryDirectory() as d:
            video(d, "_consultas", "[00:01] margem\n")
            self.assertEqual(acervo.selecionar("margem", d), [])


class TestGravar(unittest.TestCase):
    def test_grava_trechos_md_com_a_pergunta(self):
        with tempfile.TemporaryDirectory() as d:
            video(d, "a", "[00:10] a margem sobe\n")
            trechos = acervo.selecionar("margem", d)
            destino = acervo.gravar(d, "O que dizem sobre margem?", trechos)
            texto = destino.read_text(encoding="utf-8")
            self.assertEqual(destino.parent.parent.name, "_consultas")
            self.assertIn("# Pergunta", texto)
            self.assertIn("## [1] A [00:10]", texto)


if __name__ == "__main__":
    unittest.main()
