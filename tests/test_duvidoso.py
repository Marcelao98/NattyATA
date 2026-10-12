import unittest
from types import SimpleNamespace

from vatty import duvidoso
from vatty.motor import Segmento


class TestMotivo(unittest.TestCase):
    def test_segmento_bom_nao_e_duvidoso(self):
        self.assertIsNone(duvidoso.motivo(-0.3, 0.05, 1.4))

    def test_cada_numero_ruim_gera_um_motivo(self):
        self.assertIn("confianca", duvidoso.motivo(-1.5, 0.0, 1.0))
        self.assertIn("sem fala", duvidoso.motivo(-0.2, 0.9, 1.0))
        self.assertIn("repeticao", duvidoso.motivo(-0.2, 0.0, 3.0))

    def test_limite_exato_ainda_e_bom(self):
        self.assertIsNone(duvidoso.motivo(duvidoso.LOGPROB_MIN, duvidoso.SEM_FALA_MAX, duvidoso.COMPRESSAO_MAX))

    def test_numero_ausente_e_ignorado(self):
        self.assertIsNone(duvidoso.motivo(None, None, None))


class TestSegmentoBruto(unittest.TestCase):
    def test_le_os_campos_do_whisper_e_tolera_a_falta_deles(self):
        ruim = SimpleNamespace(avg_logprob=-2.0, no_speech_prob=0.1, compression_ratio=1.0)
        self.assertIn("confianca", duvidoso.do_segmento_bruto(ruim))
        self.assertIsNone(duvidoso.do_segmento_bruto(SimpleNamespace()))


class TestContar(unittest.TestCase):
    def test_conta_so_os_marcados(self):
        self.assertEqual(duvidoso.contar([Segmento(0, 1, "a", duvidoso="x"), Segmento(1, 2, "b")]), 1)


if __name__ == "__main__":
    unittest.main()
