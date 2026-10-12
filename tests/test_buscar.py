import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from vatty import buscar


def _pasta(raiz: Path, nome: str, txt: str, fonte: dict | None = None) -> Path:
    pasta = raiz / nome
    pasta.mkdir(parents=True)
    (pasta / "transcricao.txt").write_text(txt, encoding="utf-8")
    if fonte is not None:
        (pasta / "fonte.json").write_text(json.dumps(fonte), encoding="utf-8")
    return pasta


class TestSepararHorario(unittest.TestCase):
    def test_minuto_e_segundo(self):
        self.assertEqual(buscar.separar_horario("[01:12] oi"), (72, "[01:12]", "oi"))

    def test_com_hora(self):
        self.assertEqual(buscar.separar_horario("[1:02:03] oi")[0], 3723)

    def test_sem_horario(self):
        self.assertEqual(buscar.separar_horario("só texto"), (None, "", "só texto"))


class TestNormalizar(unittest.TestCase):
    def test_tira_acento_e_maiuscula_mantendo_o_mapa(self):
        norm, mapa = buscar._normalizar("Ação")
        self.assertEqual(norm, "acao")
        self.assertEqual(mapa, [0, 1, 2, 3])


class TestLink(unittest.TestCase):
    def test_youtube_com_interrogacao_usa_e_comercial(self):
        fonte = {"tipo": "youtube", "url": "https://www.youtube.com/watch?v=abc"}
        self.assertEqual(buscar.link_do_horario(fonte, 754), "https://www.youtube.com/watch?v=abc&t=754s")

    def test_youtube_sem_interrogacao_usa_interrogacao(self):
        fonte = {"tipo": "youtube", "url": "https://youtu.be/abc"}
        self.assertEqual(buscar.link_do_horario(fonte, 5), "https://youtu.be/abc?t=5s")

    def test_outras_fontes_nao_tem_link(self):
        self.assertIsNone(buscar.link_do_horario({"tipo": "arquivo"}, 5))
        self.assertIsNone(buscar.link_do_horario({"tipo": "youtube", "url": "https://y/x"}, None))


class TestBuscar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_acha_sem_diferenciar_acento_nem_maiuscula(self):
        _pasta(self.raiz, "a", "[00:10] A AÇÃO subiu hoje.", {"titulo": "Aula", "tipo": "arquivo"})
        achados = buscar.buscar("acao", self.raiz)
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].titulo, "Aula")
        self.assertEqual(achados[0].inicio_s, 10)
        self.assertIn("AÇÃO", achados[0].trecho)

    def test_link_no_segundo_certo(self):
        _pasta(self.raiz, "yt", "[12:34] falou de margem aqui",
               {"titulo": "V", "tipo": "youtube", "url": "https://www.youtube.com/watch?v=x"})
        self.assertEqual(buscar.buscar("margem", self.raiz)[0].link, "https://www.youtube.com/watch?v=x&t=754s")

    def test_um_achado_por_paragrafo_e_ordem_das_pastas(self):
        _pasta(self.raiz, "b", "[00:01] gato e gato\n\n[00:09] outro gato")
        _pasta(self.raiz, "a", "[00:05] um gato")
        achados = buscar.buscar("gato", self.raiz)
        self.assertEqual([(a.pasta, a.inicio_s) for a in achados], [("a", 5), ("b", 1), ("b", 9)])

    def test_pasta_sem_transcricao_e_ignorada(self):
        (self.raiz / "vazia").mkdir()
        _pasta(self.raiz, "ok", "[00:01] gato")
        self.assertEqual([a.pasta for a in buscar.buscar("gato", self.raiz)], ["ok"])

    def test_texto_antigo_sem_horario(self):
        _pasta(self.raiz, "velho", "um gato sem horário")
        achado = buscar.buscar("gato", self.raiz)[0]
        self.assertIsNone(achado.inicio_s)
        self.assertEqual(achado.horario, "")
        self.assertEqual(achado.titulo, "velho")  # sem fonte.json: o nome da pasta

    def test_limite(self):
        _pasta(self.raiz, "a", "\n\n".join(f"[00:{i:02d}] gato" for i in range(10)))
        self.assertEqual(len(buscar.buscar("gato", self.raiz, limite=3)), 3)

    def test_termo_vazio_ou_raiz_inexistente(self):
        _pasta(self.raiz, "a", "[00:01] gato")
        self.assertEqual(buscar.buscar("   ", self.raiz), [])
        self.assertEqual(buscar.buscar("gato", self.raiz / "nao-existe"), [])

    def test_trecho_com_reticencias_nas_pontas(self):
        longo = "x" * 200 + " margem " + "y" * 200
        _pasta(self.raiz, "a", f"[00:01] {longo}")
        trecho = buscar.buscar("margem", self.raiz)[0].trecho
        self.assertTrue(trecho.startswith("...") and trecho.endswith("..."))
        self.assertIn("margem", trecho)
        self.assertLess(len(trecho), 160)

    def test_acento_no_original_corta_no_lugar_certo(self):
        _pasta(self.raiz, "a", "[00:01] não é opção, é margem de segurança")
        self.assertIn("margem de segurança", buscar.buscar("MARGEM", self.raiz)[0].trecho)


class TestFormatarEMain(unittest.TestCase):
    def test_formatar_inclui_link(self):
        a = buscar.Achado("p", "Título", 5, "[00:05]", "um gato", "https://y/x?t=5s")
        saida = buscar.formatar([a])
        self.assertIn("Título [00:05] um gato", saida)
        self.assertIn("https://y/x?t=5s", saida)

    def test_main_imprime_e_conta(self):
        with tempfile.TemporaryDirectory() as tmp:
            _pasta(Path(tmp), "a", "[00:01] um gato")
            saida = io.StringIO()
            with contextlib.redirect_stdout(saida):
                codigo = buscar.main(["gato", "--raiz", tmp])
        self.assertEqual(codigo, 0)
        self.assertIn("1 achado(s).", saida.getvalue())

    def test_main_sem_achado(self):
        with tempfile.TemporaryDirectory() as tmp:
            saida = io.StringIO()
            with contextlib.redirect_stdout(saida):
                buscar.main(["gato", "--raiz", tmp])
        self.assertIn("Nada achado.", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
