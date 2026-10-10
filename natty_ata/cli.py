"""CLI fina: traduz argumentos e chama o motor. `ata <arquivo>`."""

import argparse
import sys
import time
from pathlib import Path

from . import motor, texto
from .audio import ErroDeDecodificacao, FfmpegAusente


def _relogio(segundos: float) -> str:
    m, s = divmod(int(segundos), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _mostrar_progresso(atual: float, total: float) -> None:
    porcento = int(atual / total * 100) if total else 100
    print(f"\r  {porcento:3d}%  {_relogio(atual)} / {_relogio(total)}", end="", flush=True)


def _argumentos(argv):
    p = argparse.ArgumentParser(prog="ata", description="Transcreve um arquivo de áudio ou vídeo em texto.")
    p.add_argument("arquivo", type=Path, help="áudio ou vídeo (.opus, .ogg, .mp3, .m4a, .wav, .mp4...)")
    p.add_argument("--modelo", default=motor.MODELO_PADRAO, help=f"modelo do faster-whisper (padrão: {motor.MODELO_PADRAO})")
    p.add_argument("--lang", default=motor.IDIOMA_PADRAO, help="idioma (padrão: pt; 'auto' detecta)")
    p.add_argument("--termos", type=Path, help="arquivo .txt com termos, um por linha (vira hotwords)")
    p.add_argument("--saida", type=Path, default=Path("transcricoes"), help="pasta de saída (padrão: transcricoes/)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _argumentos(argv)
    hotwords = None
    if args.termos:
        hotwords = motor.ler_termos(args.termos.read_text(encoding="utf-8")) or None

    if not motor.modelo_em_cache(args.modelo):
        print(f"Primeira execução com '{args.modelo}': o modelo (cerca de 1,5 GB) vai ser baixado "
              "pro cache do Hugging Face. Isso só acontece uma vez.")

    print(f"Transcrevendo {args.arquivo.name}...")
    comeco = time.perf_counter()
    try:
        resultado = motor.transcrever(
            args.arquivo, modelo=args.modelo, idioma=args.lang,
            hotwords=hotwords, progresso=_mostrar_progresso,
        )
    except (FileNotFoundError, FfmpegAusente, ErroDeDecodificacao) as e:
        print(f"\nErro: {e}", file=sys.stderr)
        return 1
    print()

    args.saida.mkdir(parents=True, exist_ok=True)
    destino = args.saida / f"{args.arquivo.stem}.txt"
    destino.write_text(texto.formatar(texto.juntar_em_paragrafos(resultado.segmentos)), encoding="utf-8")
    gasto = time.perf_counter() - comeco
    print(f"Pronto em {_relogio(gasto)} ({resultado.duracao_s:.0f}s de áudio, idioma {resultado.idioma}): {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
