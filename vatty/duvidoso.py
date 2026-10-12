"""
Trechos duvidosos: segmentos em que o próprio Whisper não está confiante.

Usa os números que o faster-whisper já devolve por segmento (sem LLM, sem custo):
- `avg_logprob`: confiança média dos tokens (quanto mais negativo, pior);
- `no_speech_prob`: chance de o trecho nem ser fala (música, ruído);
- `compression_ratio`: texto muito repetitivo (sinal de loop).

Os limites são os padrões do próprio Whisper e AINDA NÃO foram calibrados com áudio real
(ver docs/testes-reais.md). Lógica pura.
"""

LOGPROB_MIN = -1.0
SEM_FALA_MAX = 0.6
COMPRESSAO_MAX = 2.4

MARCA = "[?]"


def motivo(logprob, sem_fala, compressao):
    """
    Por que o segmento é duvidoso (texto curto) ou None se parece bom. Número ausente (None)
    é ignorado: legenda do YouTube, por exemplo, não tem nenhum.
    """
    razoes = []
    if logprob is not None and logprob < LOGPROB_MIN:
        razoes.append(f"confianca {logprob:.2f}")
    if sem_fala is not None and sem_fala > SEM_FALA_MAX:
        razoes.append(f"talvez sem fala {sem_fala:.2f}")
    if compressao is not None and compressao > COMPRESSAO_MAX:
        razoes.append(f"repeticao {compressao:.1f}")
    return ", ".join(razoes) or None


def do_segmento_bruto(bruto):
    """`motivo` para um segmento bruto do faster-whisper (campos ausentes contam como ausentes)."""
    return motivo(getattr(bruto, "avg_logprob", None), getattr(bruto, "no_speech_prob", None),
                  getattr(bruto, "compression_ratio", None))


def contar(segmentos) -> int:
    return sum(1 for s in segmentos if getattr(s, "duvidoso", None))
