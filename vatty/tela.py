"""
Gravação da tela junto com o áudio (`vatty gravar --tela`).

O ffmpeg roda em segundo plano (gdigrab, só Windows) e grava `tela.mp4` na
pasta da gravação: 2 quadros por segundo, sem áudio, no máximo 1280 px de
largura. O áudio continua pelo caminho de sempre (`gravacao.py`).

Sincronia: cada faixa guarda o seu horário real de início (relógio do
sistema, em segundos). O áudio começa quando `gravacao.gravar` liga o relógio;
a tela começa quando o ffmpeg grava o primeiro quadro, calculado pelo
relatório de progresso dele (`-progress`): horário do relatório menos o tempo
de vídeo já escrito. `deslocamento` e `sincronizar` levam os horários do
visual para a linha do tempo do áudio, para o `[mm:ss]` da fala bater com o
do slide.

A captura real (`CapturaTela`) recebe o ffmpeg por parâmetro (`abrir`,
`achar`), e os testes passam dublês. A prova com a tela de verdade fica em
`docs/testes-reais.md`.
"""

import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ARQUIVO = "tela.mp4"
FPS = 2
LARGURA_MAX = 1280
ESPERA_INICIO_S = 10.0   # quanto esperar o primeiro quadro antes de usar o horário aproximado
ESPERA_FIM_S = 15.0      # quanto esperar o ffmpeg fechar o arquivo depois do "q"


class ErroTela(Exception):
    """Falha ao começar a gravar a tela (mensagem para o usuário)."""


def comando(exe: str, saida, janela: str | None = None, fps: int = FPS) -> list:
    """Linha de comando do ffmpeg: tela inteira, ou a janela com esse título."""
    return [
        exe, "-hide_banner", "-loglevel", "error", "-nostats",
        "-f", "gdigrab", "-framerate", str(fps), "-i", f"title={janela}" if janela else "desktop",
        "-an",
        # largura par (o yuv420p exige) e no máximo LARGURA_MAX; a altura acompanha
        "-vf", f"scale='trunc(min({LARGURA_MAX},iw)/2)*2':-2",
        # zerolatency: o x264 não segura quadros, então o progresso mostra o horário real da captura
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-crf", "28",
        "-pix_fmt", "yuv420p", "-g", str(fps * 10),
        # mp4 fragmentado: se o ffmpeg morrer no meio, o que já foi gravado continua legível
        "-movflags", "+frag_keyframe+empty_moov",
        "-progress", "pipe:1", "-y", str(saida),
    ]


def ler_progresso(linha: str) -> float | None:
    """`out_time_us=1500000` -> 1.5 (segundos de vídeo já escritos). Outras linhas e `N/A` -> None."""
    chave, _, valor = linha.strip().partition("=")
    if chave != "out_time_us":
        return None
    try:
        micros = int(valor)
    except ValueError:
        return None
    return micros / 1e6 if micros > 0 else None


def deslocamento(inicios: dict) -> float:
    """
    Quanto somar a um horário da tela para cair na linha do tempo do áudio:
    início da tela menos o início do áudio (a primeira faixa de áudio). 0 se faltar algum.
    """
    audios = [v for nome, v in (inicios or {}).items() if nome != "tela"]
    if "tela" not in (inicios or {}) or not audios:
        return 0.0
    return inicios["tela"] - min(audios)


def sincronizar(dados: dict, desloc: float) -> dict:
    """
    Leva os eventos do visual para a linha do tempo do áudio. O que fica antes
    do zero do áudio é cortado (o slide que já estava na tela começa em 0) e o
    que acaba antes dele sai. O cabeçalho registra o deslocamento usado.
    """
    eventos = []
    for e in dados.get("eventos", []):
        inicio, fim = round(e["inicio"] + desloc, 1), round(e["fim"] + desloc, 1)
        if fim <= 0:
            continue
        eventos.append({**e, "inicio": max(0.0, inicio), "fim": fim})
    return {**dados, "sincronia": {"deslocamento_s": round(desloc, 3)}, "eventos": eventos}


class CapturaTela:
    """
    O ffmpeg gravando a tela em segundo plano. Abre já gravando; `parar()` fecha
    o arquivo. `inicio` é o horário real (relógio do sistema) do primeiro quadro;
    `inicio_aproximado` diz se o ffmpeg não informou e ficou o horário em que foi aberto.
    """

    def __init__(self, saida, *, janela: str | None = None, abrir=subprocess.Popen, achar=shutil.which,
                 agora=time.time, plataforma=sys.platform, espera_inicio=ESPERA_INICIO_S):
        if plataforma != "win32":
            raise ErroTela("a gravação da tela só funciona no Windows por enquanto.")
        exe = achar("ffmpeg")
        if not exe:
            raise ErroTela("ffmpeg não encontrado no PATH (precisa dele para gravar a tela).")
        self.saida = Path(saida)
        self.janela = janela
        self.inicio = None
        self.inicio_aproximado = False
        self._agora = agora
        self._primeiro_quadro = threading.Event()
        aberto_em = agora()
        self._proc = abrir(
            comando(exe, self.saida, janela), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # grupo próprio: o Ctrl+C que para a gravação não derruba o ffmpeg antes de fechar o arquivo
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        # o progresso precisa ser lido até o fim: com o cano cheio, o ffmpeg trava
        self._leitor = threading.Thread(target=self._ler, daemon=True)
        self._leitor.start()
        try:
            self._primeiro_quadro.wait(espera_inicio)
        except BaseException:  # Ctrl+C na espera: o ffmpeg tem grupo próprio e ficaria gravando sozinho
            self._proc.kill()
            raise
        if self.inicio is None:
            if self._proc.poll() is not None:
                raise ErroTela(f"a gravação da tela não começou: {self._erro() or 'o ffmpeg fechou sem dizer por quê'}"
                               + (f' (a janela "{janela}" está aberta?)' if janela else ""))
            self.inicio, self.inicio_aproximado = aberto_em, True

    def _ler(self) -> None:
        for linha in self._proc.stdout:
            gravado = ler_progresso(linha.decode("utf-8", errors="replace"))
            if gravado is not None and self.inicio is None:
                self.inicio = self._agora() - gravado
                self._primeiro_quadro.set()
        self._primeiro_quadro.set()  # o ffmpeg fechou: ninguém fica esperando à toa

    def _erro(self) -> str:
        try:
            return self._proc.stderr.read().decode("utf-8", errors="replace").strip()
        except (OSError, ValueError):
            return ""

    def parar(self) -> bool:
        """Pede ao ffmpeg para fechar o arquivo. Devolve False se ele já tinha parado sozinho (janela fechada?)."""
        ate_o_fim = self._proc.poll() is None
        if ate_o_fim:
            try:
                self._proc.stdin.write(b"q")
                self._proc.stdin.flush()
                self._proc.stdin.close()
            except OSError:
                pass
            try:
                self._proc.wait(timeout=ESPERA_FIM_S)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                self._proc.wait(timeout=5)
        self._leitor.join(timeout=5)
        return ate_o_fim
