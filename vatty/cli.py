"""CLI fina: traduz argumentos, chama as camadas e pergunta ao usuário. `vatty <url-ou-arquivo>`."""

import argparse
import sys
import tempfile
import textwrap
import time
from pathlib import Path

from . import aula, ata, audio, diarizar, fonte, gravacao, legenda, motor, ocr, pasta, perfis, preprocessar, quadros, visual, vozes
from .audio import ErroDeDecodificacao, FfmpegAusente

PREPROCESSAR_ESCOLHAS = ("perguntar", "sim", "nao")
TEXTO_ESCOLHAS = ("perguntar", "legenda", "whisper")
VISUAL_ESCOLHAS = ("nenhum", "auto", "aula")

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
    """Opções que `vatty` e `vatty gravar` compartilham (o que o Whisper e a pasta de saída precisam)."""
    p.add_argument("--modelo", default=motor.MODELO_PADRAO, help=f"modelo do faster-whisper (padrão: {motor.MODELO_PADRAO})")
    p.add_argument("--lang", default=motor.IDIOMA_PADRAO, help="idioma (padrão: pt; 'auto' usa o do vídeo ou detecta)")
    p.add_argument("--termos", type=Path, nargs="+", action="extend", metavar="ARQUIVO",
                   help="um ou mais arquivos .txt com termos, um por linha (viram hotwords do Whisper; o limite de "
                        "~223 tokens vale para a soma). Ex.: --termos termos/tecnologia-ia.txt termos/girias-brasil.txt")
    p.add_argument("--saida", type=Path, default=Path("transcricoes"), help="pasta de saída (padrão: transcricoes/)")
    p.add_argument("--apagar-audio", dest="apagar_audio", action="store_true", default=None,
                   help="gravação: apaga os .wav depois de transcrever, sem perguntar")
    p.add_argument("--manter-audio", dest="apagar_audio", action="store_false", default=None,
                   help="gravação: guarda os .wav depois de transcrever, sem perguntar")
    p.add_argument("--horario-por-palavra", dest="horario_por_palavra", choices=("auto", "sim", "nao"), default="auto",
                   help="ajusta o início e o fim de cada trecho à primeira e à última palavra (gasta mais tempo). "
                        "'auto' (padrão) liga só em gravação; 'sim' liga sempre; 'nao' desliga")
    p.add_argument("--vad-silencio-ms", dest="vad_silencio_ms", type=int, default=None, metavar="MS",
                   help="experimental: pausa mínima (ms) que corta a fala no filtro de voz do Whisper. "
                        "Sem a opção, fica o padrão do faster-whisper (160)")
    p.add_argument("--preprocessar", choices=PREPROCESSAR_ESCOLHAS, default="perguntar",
                   help="antes do Whisper: corta o ronco grave, tira o ruído e sobe a voz baixa (áudio de WhatsApp, "
                        "celular). 'perguntar' (padrão) mede o áudio e só pergunta se algo estiver ruim; "
                        "'sim' aplica sempre; 'nao' não mede nem mexe. Piora sussurro e áudio com música "
                        "de fundo: nesses casos, 'nao'")
    p.add_argument("--falantes", type=_tipo_falantes, default="nao", metavar="nao|auto|N|perfis",
                   help="separa quem falou (precisa do sherpa-onnx: pip install -e \".[falantes]\"). 'auto' descobre as "
                        "pessoas sozinha; um número (ex.: 5) fixa quantas são e costuma acertar mais; 'perfis' só "
                        "reconhece quem tem perfil cadastrado (vatty perfil --help). Em gravação, só o som do PC. "
                        "Padrão: nao")
    p.add_argument("--perfis", nargs="+", default=None, metavar="NOME",
                   help="com --falantes: usa só esses perfis de voz ('nenhum' não usa nenhum). Sem a opção, usa todos")
    p.add_argument("--ruido-modelo", dest="ruido_modelo", default=None, metavar="NOME_OU_ARQUIVO",
                   help=f"modelo de ruído do arnndn: {', '.join(preprocessar.MODELOS_RUIDO)} (padrão: "
                        f"{preprocessar.MODELO_RUIDO_PADRAO}, baixado na primeira vez) ou o caminho de um .rnnn")


def _tipo_falantes(valor: str) -> str:
    valor = valor.strip().lower()
    if valor in ("nao", "auto", "perfis") or (valor.isdigit() and int(valor) >= 1):
        return valor
    raise argparse.ArgumentTypeError("use nao, auto, perfis ou o número de pessoas (ex.: 5)")


def _argumentos(argv):
    p = argparse.ArgumentParser(prog="vatty", description="Transcreve um vídeo de uma URL (YouTube, TikTok...), um arquivo de áudio/vídeo "
                                "ou uma gravação. Para gravar o áudio do PC: vatty gravar --help.")
    p.add_argument("entrada", help="URL de vídeo (YouTube, TikTok...), arquivo (.opus, .ogg, .mp3, .m4a, .wav, .mp4...) "
                                   "ou pasta de uma gravação (gravacoes/AAAA-MM-DD_HH-MM)")
    _opcoes_comuns(p)
    p.add_argument("--texto", choices=TEXTO_ESCOLHAS, default="perguntar",
                   help="URL com legenda: usar a legenda, o Whisper, ou perguntar depois de mostrar trechos (padrão)")
    p.add_argument("--visual", choices=VISUAL_ESCOLHAS, default="nenhum",
                   help="extrai também o que aparece na tela (slides + OCR com Tesseract). 'aula' faz direto; "
                        "'auto' mostra um palpite e pergunta; 'nenhum' (padrão) só o texto. Precisa de vídeo e do Tesseract")
    return p.parse_args(argv)


# --- Whisper -----------------------------------------------------------------

def _whisper(caminho, args, idioma):
    hotwords = None
    if args.termos:
        hotwords = motor.combinar_termos(c.read_text(encoding="utf-8") for c in args.termos) or None
    if not motor.modelo_em_cache(args.modelo):
        print(f"Primeira execução com '{args.modelo}': o modelo (cerca de 1,5 GB) vai ser baixado "
              "pro cache do Hugging Face. Isso só acontece uma vez.")
    modo = getattr(args, "horario_por_palavra", "auto")
    palavras = modo == "sim" or (modo == "auto" and getattr(args, "em_gravacao", False))
    try:
        preparo = preprocessar.preparar(
            caminho, getattr(args, "preprocessar", "nao"), perguntar=_perguntar_preprocessar,
            interativo=sys.stdin.isatty(), ruido_modelo=getattr(args, "ruido_modelo", None))
        print("Transcrevendo com Whisper...")
        extras = {"carregar_audio": preparo.carregar_audio} if preparo.carregar_audio else {}
        resultado = motor.transcrever(caminho, modelo=args.modelo, idioma=idioma, hotwords=hotwords,
                                      palavras=palavras, vad_silencio_ms=getattr(args, "vad_silencio_ms", None),
                                      progresso=_mostrar_progresso, **extras)
    except (FileNotFoundError, FfmpegAusente, ErroDeDecodificacao) as e:
        raise Erro(str(e)) from e
    resultado.preprocessamento = preparo.info
    print()
    for aviso in resultado.avisos:
        print(f"Aviso: {aviso}")
    if resultado.refeitos:
        print(f"{len(resultado.refeitos)} trecho(s) com sinal de loop refeito(s) sem os termos:")
        for r in resultado.refeitos:
            print(f"  [{_relogio(r['inicio'])}-{_relogio(r['fim'])}] {r['motivo']}")
    return resultado


def _separar_falantes(caminho, resultado, args, criar_vozes=None, carregar=audio.carregar) -> None:
    """
    Roda a separação de falantes sobre o áudio e põe `pessoa` nos segmentos. Qualquer falha vira aviso:
    o texto já está pronto e não pode se perder por causa disso.
    """
    pedido = getattr(args, "falantes", "nao")
    if pedido == "nao":
        return
    modo, n_falantes = ("perfis", None) if pedido == "perfis" else ("agrupar", None if pedido == "auto" else int(pedido))
    try:
        voz = (criar_vozes or vozes.Vozes)()
        escolhidos = getattr(args, "perfis", None)
        if escolhidos and [e.lower() for e in escolhidos] == ["nenhum"]:
            cadastrados, avisos = {}, []
        else:
            cadastrados, avisos = perfis.carregar(voz.nome, so_nomes=escolhidos)
        for aviso in avisos:
            print(f"Aviso: {aviso}")
        if modo == "perfis" and not cadastrados:
            raise ValueError("--falantes perfis precisa de pelo menos um perfil (vatty perfil criar --help).")
        print("Separando os falantes..." if modo == "agrupar" else "Reconhecendo as vozes cadastradas...")
        amostras, _ = carregar(caminho)
        separacao = diarizar.separar(amostras, voz, modo, n_falantes=n_falantes, perfis=cadastrados)
    except (vozes.VozesIndisponiveis, ValueError, FileNotFoundError, FfmpegAusente, ErroDeDecodificacao) as e:
        print(f"Aviso: sem separação de falantes: {e}")
        return
    resultado.segmentos = diarizar.atribuir(resultado.segmentos, separacao.turnos)
    resultado.falantes = {**separacao.info, "turnos": [
        {"inicio": round(t.inicio, 2), "fim": round(t.fim, 2), "pessoa": t.pessoa} for t in separacao.turnos]}
    for p in separacao.info["pessoas"]:
        print(f"  {p['pessoa']}: {_relogio(p['fala_s'])}{' (perfil)' if p['perfil'] else ''}")
    if not separacao.turnos:
        print("Aviso: não achei fala para separar.")


def _perguntar_preprocessar(diagnostico) -> bool:
    """Enter aceita a recomendação (aplicar), como no `--visual auto`."""
    while True:
        try:
            resposta = input("Aplicar o pré-processamento (tirar ronco e ruído, subir a voz)? [S/n] ").strip().lower()
        except EOFError:
            raise Erro("cancelado")
        if resposta in ("", "s", "sim"):
            return True
        if resposta in ("n", "nao", "não"):
            return False


# --- Legenda -----------------------------------------------------------------

def _mostrar_legenda(escolha, segmentos, duracao, plataforma="YouTube") -> None:
    tipo = f"automática do {plataforma}" if escolha.automatica else "manual (escrita pelo autor)"
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

DICA_IMITAR_NAVEGADOR = ('Dica: este site exige imitar um navegador. Atualize as dependências: '
                         'pip install -e . (ou pip install -U "yt-dlp[default,curl-cffi]")')


def _erro_download(e) -> str:
    texto = str(e)
    if "mpersonat" in texto or "Unexpected response from webpage request" in texto:
        texto += f"\n{DICA_IMITAR_NAVEGADOR}"
    return f"não consegui ler/baixar o vídeo: {texto}"


def _do_youtube(args):
    """
    URL de vídeo (YouTube, TikTok, o que o yt-dlp suportar) -> (pasta, fonte.json, resultado).
    Legenda primeiro, Whisper se o usuário quiser. A página é lida UMA vez (`fonte.Sessao`): o TikTok
    recusa a segunda leitura, então o áudio sai do mesmo `info` e da mesma instância.
    """
    try:
        from yt_dlp.utils import DownloadError
    except ImportError:  # pragma: no cover
        DownloadError = RuntimeError

    sessao = fonte.Sessao(args.entrada)
    args.sessao = sessao  # o --visual reaproveita (ver _fazer_visual)
    try:
        print("Lendo o vídeo...")
        video = sessao.inspecionar()
        print(f"{video.plataforma}: {video.titulo} ({_relogio(video.duracao_s)})")
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
        with tempfile.TemporaryDirectory(prefix="vatty-") as tmp:
            if escolha:
                vtt = sessao.baixar_legenda(escolha.chave, escolha.automatica, Path(tmp))
                segmentos = legenda.ler_vtt(vtt.read_text(encoding="utf-8"))
                decisao = args.texto
                if decisao == "perguntar":
                    _mostrar_legenda(escolha, segmentos, video.duracao_s, video.plataforma)
                    decisao = _perguntar()
                if decisao == "legenda":
                    if getattr(args, "falantes", "nao") != "nao":
                        print("Aviso: com a legenda não há áudio baixado; para separar falantes use --texto whisper.")
                    resultado = legenda.para_resultado(segmentos, video.url, video.duracao_s, lang, escolha)
                    return destino, video.para_json(), resultado
            print("Baixando o áudio...")
            arquivo_audio = sessao.baixar_audio(Path(tmp))
            idioma = None if args.lang == "auto" else args.lang
            resultado = _whisper(arquivo_audio, args, idioma)
            _separar_falantes(arquivo_audio, resultado, args)
            resultado.fonte = video.url
            # o áudio some junto com a pasta temporária: só o texto fica
            return destino, video.para_json(), resultado
    except DownloadError as e:
        raise Erro(_erro_download(e)) from e


def _do_gravacao(args, pasta_audio: Path):
    """Pasta de gravação (sistema.wav e/ou microfone.wav) -> um texto só, com `falante`."""
    faixas = gravacao.faixas_na_pasta(pasta_audio)
    if not faixas:
        raise Erro(f"não achei sistema.wav nem microfone.wav em {pasta_audio}")
    idioma = None if args.lang == "auto" else args.lang
    args_faixa = argparse.Namespace(**{**vars(args), "em_gravacao": True})
    resultados = {}
    for nome, caminho in faixas.items():
        print(f"Faixa '{nome}'...")
        resultados[nome] = _whisper(caminho, args_faixa, idioma)
        if nome == "sistema":  # o microfone já é uma pessoa só ("eu")
            _separar_falantes(caminho, resultados[nome], args)
    if getattr(args, "falantes", "nao") != "nao" and "sistema" not in faixas:
        print("Aviso: --falantes só se aplica ao som do PC (sistema.wav); esta gravação não tem essa faixa.")
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
    _separar_falantes(caminho, resultado, args)
    dados = {"tipo": "arquivo", "caminho": str(caminho.resolve()), "titulo": caminho.stem,
             "duracao_s": resultado.duracao_s}
    return args.saida / pasta.slug(caminho.stem), dados, resultado


# --- Visual (perfil aula) ----------------------------------------------------

def _progresso_visual(fase):
    ultimo = [-1]

    def mostrar(atual, total):
        porcento = int(atual / total * 100) if total else 100
        if porcento != ultimo[0]:  # só quando o número muda: um quadro por segundo seria muito texto
            ultimo[0] = porcento
            print(f"\r  {fase} {porcento:3d}%", end="", flush=True)
    return mostrar


def _mostrar_palpite(ind: dict, perfil: str, motivo: str) -> None:
    print("\nO que a tela mostra:")
    print(f"  {ind['trocas']} trocas de tela ({ind['trocas_por_min']} por minuto), "
          f"uma a cada {_relogio(ind['tempo_medio_s'])} em média")
    print(f"  {ind['palavras_por_tela']} palavras por tela (lidas em poucas amostras)")
    print(f"  formato: {'vertical' if ind['vertical'] else 'horizontal'}")
    print(f"Palpite: {perfil} ({motivo})")
    if perfil == "corte":
        print("  O perfil 'corte' (vídeo curto, com cortes rápidos) ainda não existe: só aula por enquanto.")


def _confirmar_aula(perfil: str) -> bool:
    padrao = perfil == "aula"
    try:
        resposta = input(f"Extrair os slides com OCR? [{'S/n' if padrao else 's/N'}] ").strip().lower()
    except EOFError:
        raise Erro("cancelado")
    return padrao if not resposta else resposta in ("s", "sim", "y", "yes")


def _lang_visual(args, dados_fonte) -> str | None:
    if args.lang != "auto":
        return args.lang
    return (dados_fonte.get("idioma") or "")[:2] or None


def _fazer_visual(args, destino: Path, dados_fonte: dict) -> None:
    idiomas = ocr.idiomas_para(_lang_visual(args, dados_fonte))
    exe = ocr.verificar(idiomas)  # antes de baixar qualquer coisa
    with tempfile.TemporaryDirectory(prefix="vatty-visual-") as tmp:
        if fonte.eh_url(args.entrada):
            print("\nBaixando o vídeo (só a imagem, até 720p)...")
            sessao = getattr(args, "sessao", None)  # a mesma leitura do texto: o TikTok recusa a segunda
            video = (sessao.baixar_video(Path(tmp)) if sessao
                     else fonte.baixar_video(dados_fonte.get("url") or args.entrada, Path(tmp)))
        else:
            video = Path(args.entrada)
        print("Procurando as trocas de tela...")
        deteccao = aula.detectar(video, progresso=_progresso_visual("tela"))
        print()
        if not deteccao.slides:
            raise Erro("não achei nenhuma tela no vídeo")
        if deteccao.truncado:
            print(f"Aviso: passou de {visual.MAX_SLIDES} trocas de tela; só as primeiras ficam.")
        if args.visual == "auto":
            ind, (perfil, motivo) = aula.palpite(video, deteccao, tmp, idiomas=idiomas, exe=exe)
            _mostrar_palpite(ind, perfil, motivo)
            if not _confirmar_aula(perfil):
                print("Visual pulado.")
                return
        print(f"Lendo o texto de {len(deteccao.slides)} slide(s) com o Tesseract...")
        dados = aula.montar(video, deteccao, destino, idiomas=idiomas, exe=exe, progresso=_progresso_visual("slides"),
                            parametros={"intervalo_s": visual.INTERVALO_S, "limiar_mudanca": visual.LIMIAR_MUDANCA,
                                        "max_slides": visual.MAX_SLIDES, "escolha": args.visual})
        print()
    caminho = pasta.gravar_visual(destino, dados)
    print(f"Visual: {len(dados['eventos'])} slide(s) em {caminho.parent} (visual.json e frames/).")


def _visual(args, destino: Path, dados_fonte: dict) -> int:
    """Roda o visual depois do texto. Se falhar, o texto já está salvo: avisa e sai com código 1."""
    try:
        from yt_dlp.utils import DownloadError
    except ImportError:  # pragma: no cover
        DownloadError = RuntimeError
    try:
        _fazer_visual(args, destino, dados_fonte)
    except (Erro, ocr.ErroOcr, quadros.ErroDeVideo, FfmpegAusente, FileNotFoundError, RuntimeError, DownloadError) as e:
        print(f"\nErro no visual: {e}\nO texto já está salvo em {destino}.", file=sys.stderr)
        return 1
    return 0


# --- Gravação ----------------------------------------------------------------

def _argumentos_gravar(argv):
    p = argparse.ArgumentParser(
        prog="vatty gravar",
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
        print(f"Para transcrever depois: vatty {resultado.pasta}")
        return 0
    args.entrada = str(resultado.pasta)
    return _executar(args)


# --- Entrada principal -------------------------------------------------------

def _executar(args) -> int:
    """Produz a pasta do vídeo para `args.entrada` (URL, arquivo ou pasta de gravação)."""
    comeco = time.perf_counter()
    visual_pedido = getattr(args, "visual", "nenhum")
    if visual_pedido == "auto" and not sys.stdin.isatty():
        print("\nErro: --visual auto precisa de um terminal para perguntar. Use --visual aula ou --visual nenhum.",
              file=sys.stderr)
        return 1
    try:
        destino, dados_fonte, resultado = (_do_youtube if fonte.eh_url(args.entrada) else _do_arquivo)(args)
    except Erro as e:
        _fechar_sessao(args)
        print(f"\nErro: {e}", file=sys.stderr)
        return 1
    try:
        return _concluir(args, comeco, visual_pedido, destino, dados_fonte, resultado)
    finally:
        _fechar_sessao(args)


def _fechar_sessao(args) -> None:
    sessao = getattr(args, "sessao", None)
    if sessao is not None:
        sessao.fechar()


def _concluir(args, comeco, visual_pedido, destino, dados_fonte, resultado) -> int:
    txt = pasta.gravar(destino, dados_fonte, resultado)
    gasto = time.perf_counter() - comeco
    print(f"Pronto em {_relogio(gasto)} (texto de {resultado.origem}, {resultado.duracao_s:.0f}s de áudio): {txt.parent}")
    if dados_fonte.get("tipo") == "gravacao":
        if visual_pedido != "nenhum":
            print("Aviso: --visual não se aplica a uma gravação de áudio.")
        _apagar_audio(args, Path(args.entrada))
    elif visual_pedido != "nenhum":
        return _visual(args, destino, dados_fonte)
    return 0


# --- Perfis de voz -----------------------------------------------------------

def _argumentos_perfil(argv):
    p = argparse.ArgumentParser(
        prog="vatty perfil",
        description="Perfis de voz: a impressão de voz de quem consentiu em ser reconhecido. Guarda só o vetor, "
                    f"nunca o áudio, em {perfis.pasta_perfis()} (VATTY_PERFIS muda).")
    sub = p.add_subparsers(dest="comando", required=True)
    c = sub.add_parser("criar", help="cria o perfil de uma pessoa a partir de um áudio só dela falando (20 a 30 s)")
    c.add_argument("nome")
    c.add_argument("amostra", type=Path, help="áudio com SÓ essa pessoa falando, num lugar quieto")
    c.add_argument("--consentimento", action="store_true",
                   help="confirma que a pessoa foi avisada e concordou (sem isso, a Vatty pergunta)")
    c.add_argument("--substituir", action="store_true", help="refaz um perfil que já existe")
    sub.add_parser("listar", help="mostra os perfis cadastrados")
    a = sub.add_parser("apagar", help="apaga o perfil de uma pessoa")
    a.add_argument("nome")
    return p.parse_args(argv)


def _confirmar_consentimento() -> bool:
    if not sys.stdin.isatty():
        return False
    print(perfis.TEXTO_CONSENTIMENTO)
    try:
        return input("Confirma? [s/N] ").strip().lower() in ("s", "sim", "y", "yes")
    except EOFError:
        return False


def _main_perfil(argv, criar_vozes=None, carregar=audio.carregar) -> int:
    args = _argumentos_perfil(argv)
    try:
        if args.comando == "listar":
            lista = perfis.listar()
            if not lista:
                print("Nenhum perfil cadastrado.")
            for d in lista:
                print(f"{d['nome']}  (modelo {d['modelo_voz']}, consentimento em {d['consentimento']})")
        elif args.comando == "apagar":
            perfis.apagar(args.nome)
            print(f"Perfil '{args.nome}' apagado.")
        else:
            if not (args.consentimento or _confirmar_consentimento()):
                raise Erro("sem o consentimento da pessoa não se cria perfil de voz "
                           "(confirme com --consentimento ou respondendo 's' quando eu perguntar).")
            voz = (criar_vozes or vozes.Vozes)()
            amostras, _ = carregar(args.amostra)
            vetor, info = diarizar.vetor_de_perfil(amostras, voz)
            perfis.criar(args.nome, vetor, voz.nome, consentimento=True, info=info, substituir=args.substituir)
            print(f"Perfil '{args.nome}' criado ({info['fala_s']:.0f} s de fala, coerência {info['coerencia']}). "
                  "O áudio da amostra não foi guardado.")
    except (Erro, perfis.PerfilErro, ValueError, vozes.VozesIndisponiveis, FileNotFoundError, FfmpegAusente,
            ErroDeDecodificacao) as e:
        print(f"\nErro: {e}", file=sys.stderr)
        return 1
    return 0


# --- Ata de reunião ----------------------------------------------------------

def _argumentos_ata(argv):
    p = argparse.ArgumentParser(
        prog="vatty ata",
        description="Monta o .docx/.pdf da ata que o Secretário escreveu (ata-*.md na pasta do vídeo). "
                    "Sem custo de tokens: o título, a data, a duração e os participantes vêm dos arquivos da pasta.")
    p.add_argument("pasta", type=Path, help="pasta do vídeo (transcricoes/<nome>)")
    p.add_argument("--arquivo", help="qual ata-*.md usar (padrão: a mais recente)")
    p.add_argument("--formato", nargs="+", choices=tuple(ata.FORMATOS), default=["docx"],
                   help="docx, pdf ou os dois (padrão: docx)")
    p.add_argument("--nomes", nargs="+", metavar="'Pessoa 1=Ana'",
                   help="troca os rótulos 'Pessoa N' pelos nomes (só no documento final)")
    p.add_argument("--titulo", help="título da ata (padrão: 'Ata: <título da fonte>')")
    return p.parse_args(argv)


def _main_ata(argv) -> int:
    args = _argumentos_ata(argv)
    try:
        arquivos = ata.gerar(args.pasta, args.arquivo, args.formato, ata.ler_nomes(args.nomes), args.titulo)
    except ata.AtaErro as e:
        print(f"\nErro: {e}", file=sys.stderr)
        return 1
    for arquivo in arquivos:
        print(f"Ata pronta: {arquivo}")
    return 0


def main(argv=None) -> int:
    # Título com emoji num terminal cp1252 não pode derrubar o programa. `line_buffering`: com a saída
    # redirecionada (arquivo, outro programa) o Python guarda o texto num buffer e parece travado.
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(errors="replace", line_buffering=True)
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "gravar":
        return _main_gravar(argv[1:])
    if argv and argv[0] == "ata":
        return _main_ata(argv[1:])
    if argv and argv[0] == "perfil":
        return _main_perfil(argv[1:])
    return _executar(_argumentos(argv))


if __name__ == "__main__":
    sys.exit(main())
