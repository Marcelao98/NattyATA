"""Segmentos do Whisper -> parágrafos de texto."""

# Segmentos seguidos com pausa menor que isso viram um parágrafo só (o Whisper
# corta em pedaços de ~7-10s, e frases saíam partidas).
PAUSA_PARAGRAFO_S = 2.0

# Parágrafo não passa disso (do começo do 1º segmento ao fim do último): quem
# fala sem pausa viraria um bloco enorme. A legenda automática do YouTube não
# tem pausa nenhuma; num vídeo de 15 min saiu um parágrafo de 2.877 palavras.
DURACAO_MAX_PARAGRAFO_S = 60.0

# Como o `falante` do segmento aparece no começo do parágrafo (gravação com duas faixas).
ROTULOS = {"eu": "Eu", "outros": "Outros"}


def juntar_em_paragrafos(
    segmentos,
    pausa_max: float = PAUSA_PARAGRAFO_S,
    duracao_max: float = DURACAO_MAX_PARAGRAFO_S,
) -> list:
    """
    [Segmento(inicio, fim, texto)] -> [texto do parágrafo], juntando segmentos
    consecutivos quando a pausa entre o fim de um e o começo do outro é menor
    que `pausa_max`. Pausa maior, ou o parágrafo passar de `duracao_max`
    segundos, abre parágrafo novo. Texto vazio é ignorado.
    """
    paragrafos = []
    comeco = ultimo_fim = falante_atual = None
    for seg in sorted(segmentos, key=lambda s: s.inicio):
        texto = seg.texto.strip()
        if not texto:
            continue
        falante = getattr(seg, "falante", None)
        mesmo_falante = falante == falante_atual
        if paragrafos and mesmo_falante and seg.inicio - ultimo_fim < pausa_max and seg.fim - comeco <= duracao_max:
            paragrafos[-1] = f"{paragrafos[-1]} {texto}"
        else:
            # Quem fala só aparece quando há mais de uma faixa; sem falante, nada muda.
            rotulo = f"{ROTULOS.get(falante, falante)}: " if falante else ""
            paragrafos.append(f"{rotulo}{texto}")
            comeco = seg.inicio
        falante_atual = falante
        ultimo_fim = seg.fim
    return paragrafos


def formatar(paragrafos: list) -> str:
    """Parágrafos separados por linha em branco."""
    return "\n\n".join(paragrafos) + "\n" if paragrafos else ""
