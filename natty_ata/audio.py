"""
Arquivo de áudio ou vídeo -> array float32 mono 16 kHz, pronto pro Whisper.

Decodifica com o ffmpeg (aceita qualquer coisa que ele abra: .opus, .ogg,
.mp3, .m4a, .wav, .mp4...). O faster-whisper NÃO recebe o caminho: o 1.2.x
abre arquivo pelo PyAV, e o PyAV 19 recusa um parâmetro que ele passa
(TypeError "metadata_errors", visto no Escriba em 02/10/2026). Com array o
decodificador dele nem é chamado.
"""

import shutil
import subprocess
from pathlib import Path

import numpy as np

TAXA = 16000  # o Whisper só trabalha em 16 kHz mono

COMO_INSTALAR_FFMPEG = (
    "ffmpeg não encontrado no PATH. Instale e abra um terminal novo:\n"
    "  Windows: winget install Gyan.FFmpeg\n"
    "  macOS:   brew install ffmpeg\n"
    "  Linux:   sudo apt install ffmpeg"
)


class FfmpegAusente(RuntimeError):
    """O ffmpeg não está no PATH."""


class ErroDeDecodificacao(RuntimeError):
    """O ffmpeg não conseguiu ler o arquivo."""


def comando_ffmpeg(executavel: str, caminho: Path) -> list:
    """Linha de comando que manda PCM f32le mono 16 kHz pra saída padrão."""
    return [
        executavel, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(caminho),
        "-vn", "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1", "-ar", str(TAXA),
        "-",
    ]


def carregar(caminho, executar=subprocess.run, achar=shutil.which):
    """
    Caminho do arquivo -> (array float32, duração em segundos).
    `executar` e `achar` existem pros testes trocarem o ffmpeg por um dublê.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"arquivo não encontrado: {caminho}")
    executavel = achar("ffmpeg")
    if not executavel:
        raise FfmpegAusente(COMO_INSTALAR_FFMPEG)
    saida = executar(comando_ffmpeg(executavel, caminho), capture_output=True)
    if saida.returncode != 0:
        erro = saida.stderr.decode("utf-8", errors="replace").strip()
        raise ErroDeDecodificacao(f"ffmpeg não conseguiu ler {caminho.name}: {erro}")
    audio = np.frombuffer(saida.stdout, dtype=np.float32)
    return audio, len(audio) / TAXA
