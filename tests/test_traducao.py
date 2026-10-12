import json
import tempfile
import unittest
from pathlib import Path

from vatty import traducao


def pasta_com(d, textos):
    (Path(d) / "transcricao.json").write_text(json.dumps({"segmentos": [
        {"inicio": i, "fim": i + 1, "texto": t} for i, t in enumerate(textos)]}))
    return Path(d)


class TestPreparar(unittest.TestCase):
    def test_uma_linha_numerada_por_bloco_sem_horario(self):
        with tempfile.TemporaryDirectory() as d:
            destino, n = traducao.preparar(pasta_com(d, ["Olá, mundo", "Tchau"]), "en")
            self.assertEqual((destino.name, n), ("traducao-en-entrada.txt", 2))
            self.assertEqual(destino.read_text(encoding="utf-8").splitlines(), ["1|Olá, mundo", "2|Tchau"])

    def test_idioma_invalido_e_sem_transcricao(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(traducao.TraducaoErro):
                traducao.preparar(pasta_com(d, ["a"]), "../x")
            with self.assertRaises(traducao.TraducaoErro):
                traducao.preparar(Path(d) / "nada", "en")


class TestMontar(unittest.TestCase):
    def test_junta_traducao_com_os_horarios_originais(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = pasta_com(d, ["Olá", "Tchau"])
            (pasta / "traducao-en.txt").write_text("lixo\n1|Hello\n2|Bye\n", encoding="utf-8")
            (caminho,) = traducao.montar(pasta, "en")
            texto = caminho.read_text(encoding="utf-8")
            self.assertEqual(caminho.name, "legenda.en.srt")
            self.assertIn("00:00:00,000 --> 00:00:01,000\nHello", texto)
            self.assertIn("00:00:01,000 --> 00:00:02,000\nBye", texto)

    def test_bloco_faltando_e_erro_que_lista_os_numeros(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = pasta_com(d, ["a", "b", "c"])
            (pasta / "traducao-en.txt").write_text("1|A\n3|C\n", encoding="utf-8")
            with self.assertRaises(traducao.TraducaoErro) as e:
                traducao.montar(pasta, "en")
            self.assertIn("Faltam 1 bloco(s) na tradução: 2", str(e.exception))

    def test_sem_arquivo_do_agente(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(traducao.TraducaoErro):
                traducao.montar(pasta_com(d, ["a"]), "en")

    def test_ler_traducao_ignora_vazio_e_usa_o_ultimo_repetido(self):
        self.assertEqual(traducao.ler_traducao("1|a\n2|\n1|b\nfora"), {1: "b"})


if __name__ == "__main__":
    unittest.main()
