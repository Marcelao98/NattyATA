import json
import tempfile
import unittest
from pathlib import Path

from natty_ata import pasta
from natty_ata.motor import Resultado, Segmento


class TestPasta(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(pasta.slug("Aula 3: Derivadas & Integrais!"), "aula-3-derivadas-integrais")
        self.assertEqual(pasta.slug("Cálculo 📚", "abc123"), "calculo-abc123")
        self.assertEqual(pasta.slug("📚"), "video")
        self.assertLessEqual(len(pasta.slug("a" * 200)), pasta.TAMANHO_MAX_SLUG)

    def test_gravar(self):
        resultado = Resultado(
            fonte="https://youtu.be/x", duracao_s=20.0, modelo=None, idioma="pt",
            segmentos=[Segmento(0.0, 2.0, "Olá."), Segmento(2.5, 4.0, "Tudo bem?"), Segmento(10.0, 12.0, "Tchau.")],
            origem="legenda-manual",
        )
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "aula-x"
            txt = pasta.gravar(destino, {"tipo": "youtube", "titulo": "Aula"}, resultado)

            self.assertEqual(txt.read_text(encoding="utf-8"), "Olá. Tudo bem?\n\nTchau.\n")
            self.assertEqual(json.loads((destino / "fonte.json").read_text(encoding="utf-8"))["titulo"], "Aula")
            transcricao = json.loads((destino / "transcricao.json").read_text(encoding="utf-8"))
            self.assertEqual(transcricao["origem"], "legenda-manual")
            self.assertIsNone(transcricao["modelo"])
            self.assertEqual(transcricao["segmentos"][1], {"inicio": 2.5, "fim": 4.0, "texto": "Tudo bem?"})


if __name__ == "__main__":
    unittest.main()
