"""Segmentos do Whisper -> parágrafos de texto."""

# Segmentos seguidos com pausa menor que isso viram um parágrafo só (o Whisper
# corta em pedaços de ~7-10s, e frases saíam partidas).
PAUSA_PARAGRAFO_S = 2.0


def juntar_em_paragrafos(segmentos, pausa_max: float = PAUSA_PARAGRAFO_S) -> list:
    """
    [Segmento(inicio, fim, texto)] -> [texto do parágrafo], juntando segmentos
    consecutivos quando a pausa entre o fim de um e o começo do outro é menor
    que `pausa_max`. Pausa maior abre parágrafo novo. Texto vazio é ignorado.
    """
    paragrafos = []
    ultimo_fim = None
    for seg in sorted(segmentos, key=lambda s: s.inicio):
        texto = seg.texto.strip()
        if not texto:
            continue
        if paragrafos and seg.inicio - ultimo_fim < pausa_max:
            paragrafos[-1] = f"{paragrafos[-1]} {texto}"
        else:
            paragrafos.append(texto)
        ultimo_fim = seg.fim
    return paragrafos


def formatar(paragrafos: list) -> str:
    """Parágrafos separados por linha em branco."""
    return "\n\n".join(paragrafos) + "\n" if paragrafos else ""
