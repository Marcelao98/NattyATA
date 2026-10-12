import unittest

from vatty.ui import saude


def checar(**faltando):
    tudo = {"ffmpeg": True, "tesseract": True, "yt_dlp": True, "sherpa_onnx": True, "docx": True, "reportlab": True}
    tudo.update(faltando)
    return saude.checar(procurar=lambda n: n if tudo.get(n, True) else None,
                        tem_modulo=lambda n: tudo.get(n, True),
                        modelo_em_cache=lambda: tudo.get("modelo", True))


class TestSaude(unittest.TestCase):
    def test_tudo_certo(self):
        itens = checar()
        self.assertTrue(all(i["ok"] for i in itens))
        self.assertEqual(saude.faltando_essencial(itens), [])

    def test_falta_essencial_traz_a_ajuda_em_portugues(self):
        faltam = saude.faltando_essencial(checar(ffmpeg=False, modelo=False))
        self.assertEqual([i["id"] for i in faltam], ["ffmpeg", "modelo"])
        self.assertIn("winget", faltam[0]["ajuda"])

    def test_opcional_nao_conta_como_essencial(self):
        itens = checar(tesseract=False, sherpa_onnx=False, docx=False)
        self.assertEqual(saude.faltando_essencial(itens), [])
        self.assertEqual([i["id"] for i in itens if not i["ok"]], ["tesseract", "falantes", "ata"])


if __name__ == "__main__":
    unittest.main()
