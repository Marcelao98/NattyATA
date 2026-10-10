"""CLI fina: traduz argumentos, chama as camadas e pergunta ao usuário. `ata <url-ou-arquivo>`."""

import argparse
import sys
import tempfile
import textwrap
import time
from pathlib import Path

from . import fonte, gravacao, legenda, motor, pasta
from .audio import ErroDeDecodificacao, FfmpegAusente

TEXTO_ESCOLHAS = ("perguntar", "legenda", "whisper")

AVISO_CONSENTIMENTO = ("Aviso: gravar uma conversa sem avisar os outros participantes pode ser ilegal "
                       "onde você mora. Avise quem estiver na gravação.")


class Erro(Exception):
    """Erro para mostrar ao usuário e sair com código 1."""


def _relogio(segundos: float) -> str:
    m, s = divmod(int(segundos), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _mostrar_progresso(atual: float, total: float) -> None:
    porcento = int(atual / total * 100) if total else 100
    print(f"\r  {porcento:3d}%  {_relogio(atual)} / {_relogio(total)}", end="", flush=True)


def _opcoes_comuns(p) -> None:
    """Opções que `ata` e `ata gravar` compartilham (o que o Whisper e a pasta de saída precisam)."""
    p.add_argument("--modelo", default=motor.MODELO_PADRAO, help=f"modelo do faster-whisper (padrão: {motor.MODELO_PADRAO})")
    p.add_argument("--lang", default=motor.IDIOMA_PADRAO, help="idioma (padrão: pt; 'auto' usa o do vídeo ou detecta)")
    p.add_argument("--termos", type=Path, help="arquivo .txt com termos, um por linha (vira hotwords do Whisper)")
    p.add_argument("--saida", type=Path, default=Path("transcricoes"), help="pasta de saída (padrão: transcricoes/)")
    p.add_argument("--apagar-audio", dest="apagar_audio", action="store_true", default=None,
                   help="gravação: apaga os .wav depois de transcrever, sem perguntar")
    p.add_argument("--manter-audio", dest="apagar_audio", action="store_false", default=None,
                   help="gravação: guarda os .wav depois de transcrever, sem perguntar")


def _argumentos(argv):
    p = argparse.ArgumentParser(prog="ata", description="Transcreve um vídeo do YouTube, um arquivo de áudio/vídeo "
                                "ou uma gravação. Para gravar o áudio do PC: ata gravar --help.")
    p.add_argument("entrada", help="URL do YouTube, arquivo (.opus, .ogg, .mp3, .m4a, .wav, .mp4...) "
                                   "ou pasta de uma gravação (gravacoes/AAAA-MM-DD_HH-MM)")
    _opcoes_comuns(p)
    p.add_argument("--texto", choices=TEXTO_ESCOLHAS, default="perguntar",
                   help="YouTube: usar a legenda, o Whisper, ou perguntar depois de mostrar trechos (padrão)")
    return p.parse_args(argv)


# --- Whisper -----------------------------------------------------------------

def _whisper(caminho, args, idioma):
    hotwords = None
    if args.termos:
        hotwords = motor.ler_termos(args.termos.read_text(encoding="utf-8")) or None
    if not motor.modelo_em_cache(args.modelo):
        print(f"Primeira execução com '{args.modelo}': o modelo (cerca de 1,5 GB) vai ser baixado "
              "pro cache do Hugging Face. Isso só acontece uma vez.")
    print("Transcrevendo com Whisper...")
    try:
        resultado = motor.transcrever(caminho, modelo=args.modelo, idioma=idioma,
                                      hotwords=hotwords, progresso=_mostrar_progresso)
    except (FileNotFoundError, FfmpegAusente, ErroDeDecodificacao) as e:
        raise Erro(str(e)) from e
    print()
    for aviso in resultado.avisos:
        print(f"Aviso: {aviso}")
    if resultado.refeitos:
        print(f"{len(resultado.refeitos)} trecho(s) com sinal de loop refeito(s) sem os termos:")
        for r in resultado.refeitos:
            print(f"  [{_relogio(r['inicio'])}-{_relogio(r['fim'])}] {r['motivo']}")
    return resultado


# --- Legenda -----------------------------------------------------------------

def _mostrar_legenda(escolha, segmentos, duracao) -> None:
    tipo = "automática do YouTube" if escolha.automatica else "manual (escrita pelo autor)"
    ind = legenda.indicadores(segmentos, duracao)
    print(f"\nLegenda {tipo}, '{escolha.chave}':")
    print(f"  {ind['palavras']} palavras, cobre {ind['cobertura_pct']}% do vídeo")
    print(f"  pontuação: {ind['pontuacao_por_100']} sinais a cada 100 palavras")
    print(f"  palavras com maiúscula: {ind['maiusculas_pct']}%")
    print(f"  marcas como [Música]: {ind['marcas']}")
    print("\nTrechos:")
    for inicio, trecho in legenda.amostras(segmentos):
        corpo = textwrap.fill(trecho, width=96, initial_indent="    ", subsequent_indent="    ")
        print(f"\n  [{_relogio(inicio)}]\n{corpo}")
    print()


def _perguntar() -> str:
    while True:
        try:
            resposta = input("Usar a [l]egenda ou transcrever com [w]hisper? ").strip().lower()
        except EOFError:
            raise Erro("cancelado")
        if resposta in ("l", "legenda"):
            return "legenda"
        if resposta in ("w", "whisper"):
            return "whisper"


# --- Fluxos ------------------------------------------------------------------

def _do_youtube(args):
    """URL -> (pasta, fonte.json, resultado). Legenda primeiro, Whisper se o usuário quiser."""
    try:
        from yt_dlp.utils import DownloadError
    except ImportError:  # pragma: no cover
        DownloadError = RuntimeError

    try:
        print("Lendo o vídeo no YouTube...")
        video = fonte.inspecionar(args.entrada)
        print(f"{video.titulo} ({_relogio(video.duracao_s)})")
        lang = video.idioma if args.lang == "auto" else args.lang
        escolha = None
        if lang and args.texto != "whisper":
            escolha = legenda.escolher(video.legendas, video.legendas_automaticas, lang)
        if escolha is None and args.texto != "whisper":
            print(f"Sem legenda confiável em '{lang or '?'}': vai com Whisper.")
        if escolha and args.texto == "perguntar" and not sys.stdin.isatty():
            raise Erro("o vídeo tem legenda, mas não há terminal para perguntar. "
                       "Use --texto legenda ou --texto whisper.")

        destino = args.saida / pasta.slug(video.titulo, video.id)
        with tempfile.TemporaryDirectory(prefix="natty-ata-") as tmp:
            if escolha:
                vtt = fonte.baixar_legenda(video.url, escolha.chave, escolha.automatica, Path(tmp))
                segmentos = legenda.ler_vtt(vtt.read_text(encoding="utf-8"))
                decisao = args.texto
                if decisao == "perguntar":
                    _mostrar_legenda(escolha, segmentos, video.duracao_s)
                    decisao = _perguntar()
                if decisao == "legenda":
                    resultado = legenda.para_resultado(segmentos, video.url, video.duracao_s, lang, escolha)
                    return destino, video.para_json(), resultado
            print("Baixando o áudio...")
            audio = fonte.baixar_audio(video.url, Path(tmp))
            idioma = None if args.lang == "auto" else args.lang
            resultado = _whisper(audio, args, idioma)
            resultado.fonte = video.url
            # o áudio some junto com a pasta temporária: só o texto fica
            return destino, video.para_json(), resultado
    except DownloadError as e:
        raise Erro(f"YouTube: {e}") from e


def _do_gravacao(args, pasta_audio: Path):
    """Pasta de gravação (sistema.wav e/ou microfone.wav) -> um texto só, com `falante`."""
    faixas = gravacao.faixas_na_pasta(pasta_audio)
    if not faixas:
        raise Erro(f"não achei sistema.wav nem microfone.wav em {pasta_audio}")
    idioma = None if args.lang == "auto" else args.lang
    resultados = {}
    for nome, caminho in faixas.items():
        print(f"Faixa '{nome}'...")
        resultados[nome] = _whisper(caminho, args, idioma)
    resultado = gravacao.juntar_faixas(resultados)
    dados = {"tipo": "gravacao", "titulo": f"Gravação {pasta_audio.name}", "data": pasta_audio.name,
             "duracao_s": resultado.duracao_s, "faixas": list(faixas), "falantes": gravacao.FALANTES}
    return args.saida / pasta.slug(f"gravacao {pasta_audio.name}"), dados, resultado


def _apagar_audio(args, pasta_audio: Path) -> None:
    """Depois que o texto foi gravado: pergunta se apaga os .wav (padrão: guardar)."""
    arquivos = list(gravacao.faixas_na_pasta(pasta_audio).values())
    decisao = args.apagar_audio
    if decisao is None:
        if not sys.stdin.isatty():
            print(f"Áudio guardado em {pasta_audio} (use --apagar-audio para apagar).")
            return
        try:
            decisao = input("Apagar os áudios gravados? [s/N] ").strip().lower() in ("s", "sim", "y", "yes")
        except EOFError:
            decisao = False
    if not decisao:
        print(f"Áudio guardado em {pasta_audio}.")
        return
    for arquivo in arquivos:
        arquivo.unlink()
    try:
        pasta_audio.rmdir()  # só se ficou vazia: nunca apaga o que não é nosso
    except OSError:
        pass
    print("Áudio apagado.")


def _do_arquivo(args):
    caminho = Path(args.entrada)
    if caminho.is_dir():
        return _do_gravacao(args, caminho)
    if not caminho.is_file():
        raise Erro(f"arquivo não encontrado: {caminho}")
    print(f"Transcrevendo {caminho.name}...")
    resultado = _whisper(caminho, args, None if args.lang == "auto" else args.lang)
    dados = {"tipo": "arquivo", "caminho": str(caminho.resolve()), "titulo": caminho.stem,
             "duracao_s": resultado.duracao_s}
    return args.saida / pasta.slug(caminho.stem), dados, resultado


# --- Gravação ----------------------------------------------------------------

def _argumentos_gravar(argv):
    p = argparse.ArgumentParser(
        prog="ata gravar",
        description="Grava o áudio do PC (Windows) até Ctrl+C. Com --mic grava também o microfone, "
                    "em outra faixa. Cada faixa vira um .wav em gravacoes/AAAA-MM-DD_HH-MM/.")
    p.add_argument("--mic", action="store_true", help="grava também o microfone (faixa separada: 'eu')")
    p.add_argument("--transcrever", action="store_true", help="ao parar, já transcreve e cria a pasta do vídeo")
    p.add_argument("--duracao", type=float, metavar="SEGUNDOS", help="para sozinho depois desse tempo (bom para testar: 5)")
    p.add_argument("--gravacoes", type=Path, default=Path("gravacoes"), help="onde guardar os .wav (padrão: gravacoes/)")
    _opcoes_comuns(p)
    return p.parse_args(argv)


def _barra(pico: float) -> str:
    cheio = min(8, int(pico * 24))
    return "#" * cheio + "." * (8 - cheio)


def _mostrar_gravando(decorrido: float, niveis: dict) -> None:
    faixas = "  ".join(f"{nome} [{_barra(p)}]" for nome, p in niveis.items())
    print(f"\r  {_relogio(decorrido)}  {faixas}  ", end="", flush=True)


def _main_gravar(argv) -> int:
    args = _argumentos_gravar(argv)
    print(AVISO_CONSENTIMENTO)
    try:
        entradas = gravacao.abrir_entradas(microfone=args.mic)
        for e in entradas:
            print(f"  {e.nome}: {getattr(e, 'descricao', '')}")
        destino = gravacao.pasta_nova(args.gravacoes, time.strftime("%Y-%m-%d_%H-%M"))
        print("Gravando. Ctrl+C para parar." if args.duracao is None else f"Gravando por {args.duracao:g}s.")
        resultado = gravacao.gravar(entradas, destino, duracao_max=args.duracao, progresso=_mostrar_gravando)
    except gravacao.ErroGravacao as e:
        print(f"\nErro: {e}", file=sys.stderr)
        return 1
    print(f"\nGravado: {_relogio(resultado.duracao_s)} em {resultado.pasta}")
    for nome in resultado.faixas_mudas():
        print(f"Aviso: a faixa '{nome}' ficou quase muda. Era pra ter som nela?")
    if not args.transcrever:
        print(f"Para transcrever depois: ata {resultado.pasta}")
        return 0
    args.entrada = str(resultado.pasta)
    return _executar(args)


# --- Entrada principal -------------------------------------------------------

def _executar(args) -> int:
    """Produz a pasta do vídeo para `args.entrada` (URL, arquivo ou pasta de gravação)."""
    comeco = time.perf_counter()
    try:
        destino, dados_fonte, resultado = (_do_youtube if fonte.eh_url(args.entrada) else _do_arquivo)(args)
    except Erro as e:
        print(f"\nErro: {e}", file=sys.stderr)
        return 1
    txt = pasta.gravar(destino, dados_fonte, resultado)
    gasto = time.perf_counter() - comeco
    print(f"Pronto em {_relogio(gasto)} (texto de {resultado.origem}, {resultado.duracao_s:.0f}s de áudio): {txt.parent}")
    if dados_fonte.get("tipo") == "gravacao":
        _apagar_audio(args, Path(args.entrada))
    return 0


def main(argv=None) -> int:
    # Título com emoji num terminal cp1252 não pode derrubar o programa.
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(errors="replace")
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "gravar":
        return _main_gravar(argv[1:])
    return _executar(_argumentos(argv))


if __name__ == "__main__":
    sys.exit(main())
