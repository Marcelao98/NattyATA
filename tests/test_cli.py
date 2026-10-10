import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from natty_ata import cli, fonte
from natty_ata.motor import Resultado, Segmento

VIDEO = fonte.Video(
    id="abc", url="https://www.youtube.com/watch?v=abc", titulo="Aula", canal="C",
    duracao_s=60.0, data=None, idioma="pt", legendas={"pt-BR": []}, legendas_automaticas={},
)


def _vtt(url, chave, automatica, destino):
    caminho = Path(destino) / "legenda.vtt"
    caminho.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nOlá, turma.\n", encoding="utf-8")
    return caminho


class TestFluxoYoutube(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.saida = Path(tmp.name)
        for alvo, valor in (("inspecionar", lambda url: VIDEO), ("baixar_legenda", _vtt)):
            p = mock.patch.object(fonte, alvo, valor)
            p.start()
            self.addCleanup(p.stop)
        self.whisper = mock.patch.object(cli, "_whisper", return_value=Resultado(
            fonte="x", duracao_s=60.0, modelo="large-v3-turbo", idioma="pt",
            segmentos=[Segmento(0, 1, "do whisper")]))
        self.whisper.start()
        self.addCleanup(self.whisper.stop)
        p = mock.patch.object(fonte, "baixar_audio", lambda url, destino: Path(destino) / "audio.webm")
        p.start()
        self.addCleanup(p.stop)

    def rodar(self, *flags, tty=True, respostas=()):
        respostas = iter(respostas)
        with mock.patch.object(cli.sys.stdin, "isatty", return_value=tty), \
             mock.patch("builtins.input", lambda prompt: next(respostas)), \
             redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            codigo = cli.main([VIDEO.url, "--saida", str(self.saida), *flags])
        return codigo, out.getvalue(), err.getvalue()

    def transcricao(self):
        return (self.saida / "aula-abc" / "transcricao.txt").read_text(encoding="utf-8")

    def test_usuario_aprova_a_legenda(self):
        codigo, out, _ = self.rodar(respostas=["l"])
        self.assertEqual(codigo, 0)
        self.assertIn("Olá, turma.", out)  # mostrou o trecho antes de perguntar
        self.assertEqual(self.transcricao(), "Olá, turma.\n")
        cli._whisper.assert_not_called()

    def test_usuario_prefere_whisper(self):
        codigo, _, _ = self.rodar(respostas=["x", "w"])
        self.assertEqual(codigo, 0)
        self.assertEqual(self.transcricao(), "do whisper\n")

    def test_sem_terminal_exige_flag(self):
        codigo, _, err = self.rodar(tty=False)
        self.assertEqual(codigo, 1)
        self.assertIn("--texto", err)
        self.assertFalse((self.saida / "aula-abc").exists())

    def test_flag_legenda_nao_pergunta(self):
        codigo, _, _ = self.rodar("--texto", "legenda", tty=False)
        self.assertEqual(codigo, 0)
        self.assertEqual(self.transcricao(), "Olá, turma.\n")

    def test_sem_legenda_vai_direto_pro_whisper(self):
        sem = fonte.Video(**{**VIDEO.__dict__, "legendas": {}})
        with mock.patch.object(fonte, "inspecionar", lambda url: sem):
            codigo, out, _ = self.rodar(tty=False)
        self.assertEqual(codigo, 0)
        self.assertIn("Sem legenda", out)
        self.assertEqual(self.transcricao(), "do whisper\n")


if __name__ == "__main__":
    unittest.main()
