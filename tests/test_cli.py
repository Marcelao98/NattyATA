import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import numpy as np

from natty_ata import cli, fonte, gravacao
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


class _Tom:
    """Entrada falsa a 16 kHz mono: a cada leitura entrega 0,25 s de tom."""

    taxa, canais, descricao = 16000, 1, "dispositivo falso"

    def __init__(self, nome):
        self.nome = nome

    def pegar(self):
        t = np.arange(4000) / 16000
        return (0.4 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16).tobytes()

    def fechar(self):
        pass


def _whisper_falso(caminho, args, idioma):
    fala = {"sistema": Segmento(0.0, 2.0, "Bom dia, pessoal."), "microfone": Segmento(3.0, 4.0, "Bom dia!")}
    return Resultado(fonte="x", duracao_s=5.0, modelo="large-v3-turbo", idioma="pt",
                     segmentos=[fala[Path(caminho).stem]])


class TestGravacaoCli(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)
        self.gravacoes = self.raiz / "gravacoes"
        self.saida = self.raiz / "transcricoes"
        real = gravacao.gravar

        def gravar_sem_esperar(entradas, pasta, **opcoes):
            agora = [0.0]
            return real(entradas, pasta, relogio=lambda: agora[0],
                        dormir=lambda s: agora.__setitem__(0, agora[0] + s), **opcoes)

        for objeto, nome, valor in (
            (gravacao, "abrir_entradas", lambda microfone=False: [_Tom("sistema")] + ([_Tom("microfone")] if microfone else [])),
            (gravacao, "gravar", gravar_sem_esperar),
            (cli, "_whisper", _whisper_falso),
        ):
            p = mock.patch.object(objeto, nome, valor)
            p.start()
            self.addCleanup(p.stop)

    def rodar(self, argv, tty=False, respostas=()):
        respostas = iter(respostas)
        with mock.patch.object(cli.sys.stdin, "isatty", return_value=tty), \
             mock.patch("builtins.input", lambda prompt: next(respostas)), \
             redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            codigo = cli.main(argv)
        return codigo, out.getvalue(), err.getvalue()

    def gravar(self, *flags, **kw):
        return self.rodar(["gravar", "--duracao", "2", "--gravacoes", str(self.gravacoes),
                           "--saida", str(self.saida), *flags], **kw)

    def pastas_de_audio(self):
        return list(self.gravacoes.iterdir()) if self.gravacoes.exists() else []

    def texto(self):
        (pasta_video,) = list(self.saida.iterdir())
        return (pasta_video / "transcricao.txt").read_text(encoding="utf-8")

    def test_so_gravar_guarda_o_audio_e_diz_como_transcrever(self):
        codigo, out, _ = self.gravar()
        self.assertEqual(codigo, 0)
        (pasta_audio,) = self.pastas_de_audio()
        self.assertTrue((pasta_audio / "sistema.wav").is_file())
        self.assertFalse((pasta_audio / "microfone.wav").exists())
        self.assertIn("ata " + str(pasta_audio), out)
        self.assertIn("avisar", out)  # lembrete de consentimento
        self.assertFalse(self.saida.exists())

    def test_com_mic_grava_duas_faixas(self):
        self.gravar("--mic")
        (pasta_audio,) = self.pastas_de_audio()
        self.assertTrue((pasta_audio / "microfone.wav").is_file())

    def test_transcrever_junta_as_faixas_com_o_falante(self):
        codigo, _, _ = self.gravar("--mic", "--transcrever", "--manter-audio")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.texto(), "Outros: Bom dia, pessoal.\n\nEu: Bom dia!\n")
        (pasta_video,) = list(self.saida.iterdir())
        fonte_json = json.loads((pasta_video / "fonte.json").read_text(encoding="utf-8"))
        self.assertEqual(fonte_json["tipo"], "gravacao")
        self.assertEqual(fonte_json["faixas"], ["sistema", "microfone"])
        self.assertEqual(len(self.pastas_de_audio()), 1)  # --manter-audio

    def test_apagar_audio_remove_os_wav_e_a_pasta(self):
        self.gravar("--mic", "--transcrever", "--apagar-audio")
        self.assertEqual(self.pastas_de_audio(), [])
        self.assertTrue(self.saida.exists())  # o texto fica

    def test_sem_flag_e_sem_terminal_guarda_o_audio(self):
        _, out, _ = self.gravar("--transcrever", tty=False)
        self.assertEqual(len(self.pastas_de_audio()), 1)
        self.assertIn("--apagar-audio", out)

    def test_sem_flag_pergunta_e_so_apaga_se_disser_sim(self):
        self.gravar("--transcrever", tty=True, respostas=["s"])
        self.assertEqual(self.pastas_de_audio(), [])

    def test_resposta_vazia_guarda(self):
        self.gravar("--transcrever", tty=True, respostas=[""])
        self.assertEqual(len(self.pastas_de_audio()), 1)

    def test_nao_apaga_o_que_nao_e_do_ata(self):
        # um arquivo estranho na pasta impede o rmdir: a pasta e o arquivo ficam
        original = gravacao.pasta_nova
        def com_extra(raiz, nome):
            pasta_audio = original(raiz, nome)
            pasta_audio.mkdir(parents=True)
            (pasta_audio / "notas.txt").write_text("meu", encoding="utf-8")
            return pasta_audio
        with mock.patch.object(gravacao, "pasta_nova", com_extra):
            self.gravar("--transcrever", "--apagar-audio")
        (pasta_audio,) = self.pastas_de_audio()
        self.assertEqual([p.name for p in pasta_audio.iterdir()], ["notas.txt"])

    def test_transcrever_uma_gravacao_ja_existente_pela_pasta(self):
        self.gravar("--mic")
        (pasta_audio,) = self.pastas_de_audio()
        codigo, _, _ = self.rodar([str(pasta_audio), "--saida", str(self.saida), "--manter-audio"])
        self.assertEqual(codigo, 0)
        self.assertIn("Eu: Bom dia!", self.texto())

    def test_pasta_sem_faixas_da_erro(self):
        vazia = self.raiz / "vazia"
        vazia.mkdir()
        codigo, _, err = self.rodar([str(vazia), "--saida", str(self.saida)])
        self.assertEqual(codigo, 1)
        self.assertIn("sistema.wav", err)

    def test_erro_ao_abrir_o_dispositivo(self):
        def falha(microfone=False):
            raise gravacao.ErroGravacao("a gravação só funciona no Windows por enquanto.")
        with mock.patch.object(gravacao, "abrir_entradas", falha):
            codigo, _, err = self.gravar()
        self.assertEqual(codigo, 1)
        self.assertIn("Windows", err)
        self.assertEqual(self.pastas_de_audio(), [])

    def test_faixa_muda_gera_aviso(self):
        class Muda(_Tom):
            def pegar(self):
                return b""
        with mock.patch.object(gravacao, "abrir_entradas", lambda microfone=False: [Muda("sistema")]):
            _, out, _ = self.gravar()
        self.assertIn("quase muda", out)


if __name__ == "__main__":
    unittest.main()
