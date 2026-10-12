"""
Separação de falantes: quem falou quando. Lógica pura, sem modelo e sem arquivo.

Dois fluxos sobre as mesmas peças:
  - agrupar: sem saber quem são. Corta a fala em janelas, tira a "impressão de voz" de cada
    uma (vetor de timbre) e junta as parecidas. Sai "Pessoa 1", "Pessoa 2"...
  - perfis: com a voz já cadastrada (e consentida). Cada janela é comparada com os perfis;
    o que não bate com ninguém é "Desconhecido".
No fluxo agrupar, se houver perfis, os grupos que baterem com um perfil ganham o nome dele.

O modelo de voz entra como parâmetro (`vozes`, ver vozes.py): os testes usam um dublê.
Os limiares abaixo foram medidos só em voz sintética: ajustar com voz real.
"""

from dataclasses import dataclass, replace

import numpy as np

JANELA_S = 2.0           # tamanho de cada janela de fala que vira um vetor
PASSO_S = 1.0            # de quanto em quanto tempo uma janela começa
MINIMO_S = 1.0           # trecho de fala mais curto que isso não vira janela
# Similaridade de cosseno MÉDIA para dois grupos serem a mesma pessoa. Com o CAM++ em voz
# sintética: mesma pessoa p5 ~0,45; pessoas diferentes p95 ~0,31.
LIMITE_AGRUPAR = 0.38
# Para reconhecer um perfil cadastrado (mais exigente: errar o nome é pior que dizer "Pessoa 2").
LIMITE_PERFIL = 0.45
MAX_PARA_AGRUPAR = 1500  # acima disso agrupa uma amostra e coloca o resto no grupo mais próximo
MIN_JANELAS_GRUPO = 3    # em modo automático, grupo menor que isso é ruído e vira do vizinho
JUNTAR_PAUSA_S = 1.0     # turnos da mesma pessoa com pausa menor que isso viram um só
MIN_FALA_PERFIL_S = 10.0  # amostra de perfil com menos fala que isso é curta demais
DESCONHECIDO = "Desconhecido"


@dataclass
class Turno:
    inicio: float
    fim: float
    pessoa: str


@dataclass
class Separacao:
    turnos: list
    info: dict   # vai para o falantes.json


# --- Janelas -----------------------------------------------------------------

def janelas(trechos, janela=JANELA_S, passo=PASSO_S, minimo=MINIMO_S) -> list:
    """[(inicio, fim)] de fala -> [(inicio, fim)] de janelas de até `janela` s, cobrindo cada trecho."""
    saida = []
    for ini, fim in trechos:
        dur = fim - ini
        if dur < minimo:
            continue
        if dur <= janela:
            saida.append((ini, fim))
            continue
        t = ini
        while t + janela < fim:
            saida.append((t, t + janela))
            t += passo
        if fim - (t - passo + janela) > 0.25:
            saida.append((fim - janela, fim))  # a última janela termina no fim do trecho
    return saida


def _normalizar(emb: np.ndarray) -> np.ndarray:
    emb = np.asarray(emb, dtype=np.float32)
    normas = np.linalg.norm(emb, axis=-1, keepdims=True)
    return emb / np.maximum(normas, 1e-9)


# --- Agrupar -----------------------------------------------------------------

def _agrupar_hierarquico(emb: np.ndarray, n_falantes, limite) -> np.ndarray:
    """Agrupamento aglomerativo por média (average linkage) com similaridade de cosseno."""
    n = len(emb)
    sim = emb @ emb.T
    soma = sim.astype(np.float64)        # soma das similaridades entre grupos
    tam = np.ones(n)
    vivo = np.ones(n, dtype=bool)
    grupo = np.arange(n)
    alvo = n_falantes or 1
    while vivo.sum() > alvo:
        media = soma / np.outer(tam, tam)
        media[~vivo, :] = -np.inf
        media[:, ~vivo] = -np.inf
        np.fill_diagonal(media, -np.inf)
        i, j = np.unravel_index(np.argmax(media), media.shape)
        if n_falantes is None and media[i, j] < limite:
            break
        soma[i, :] += soma[j, :]
        soma[:, i] += soma[:, j]
        tam[i] += tam[j]
        vivo[j] = False
        grupo[grupo == j] = i
    _, rotulos = np.unique(grupo, return_inverse=True)
    return rotulos


def _centroides(emb, rotulos) -> np.ndarray:
    return _normalizar(np.array([emb[rotulos == k].mean(axis=0) for k in range(rotulos.max() + 1)]))


def agrupar(emb, n_falantes: int | None = None, limite: float = LIMITE_AGRUPAR) -> np.ndarray:
    """
    Vetores (n, d) -> rótulo de grupo por janela, numerados pela ordem em que aparecem.
    `n_falantes` fixo ajuda muito; sem ele, o corte é o `limite` de similaridade.
    """
    emb = _normalizar(emb)
    n = len(emb)
    if n == 0:
        return np.zeros(0, dtype=int)
    if n == 1:
        return np.zeros(1, dtype=int)
    if n_falantes is not None:
        n_falantes = max(1, min(int(n_falantes), n))
    amostra = np.arange(n) if n <= MAX_PARA_AGRUPAR else np.linspace(0, n - 1, MAX_PARA_AGRUPAR).astype(int)
    rotulos_amostra = _agrupar_hierarquico(emb[amostra], n_falantes, limite)
    cent = _centroides(emb[amostra], rotulos_amostra)
    rotulos = np.argmax(emb @ cent.T, axis=1)          # cada janela vai para o grupo mais próximo
    if n_falantes is None:
        rotulos = _absorver_pequenos(emb, rotulos)
    return _pela_ordem_de_aparicao(rotulos)


def _absorver_pequenos(emb, rotulos) -> np.ndarray:
    """Grupos com menos de MIN_JANELAS_GRUPO janelas são ruído: vão para o grupo mais parecido."""
    while True:
        ids, contagem = np.unique(rotulos, return_counts=True)
        if len(ids) < 2 or contagem.min() >= MIN_JANELAS_GRUPO:
            return rotulos
        pequeno = ids[np.argmin(contagem)]
        resto = [k for k in ids if k != pequeno]
        cent = _normalizar(np.array([emb[rotulos == k].mean(axis=0) for k in resto]))
        centro_pequeno = _normalizar(emb[rotulos == pequeno].mean(axis=0))
        rotulos = np.where(rotulos == pequeno, resto[int(np.argmax(cent @ centro_pequeno))], rotulos)


def _pela_ordem_de_aparicao(rotulos) -> np.ndarray:
    ordem = {}
    for r in rotulos:
        ordem.setdefault(int(r), len(ordem))
    return np.array([ordem[int(r)] for r in rotulos], dtype=int)


# --- Perfis ------------------------------------------------------------------

def reconhecer(emb, perfis: dict, limite: float = LIMITE_PERFIL) -> list:
    """Vetores (n, d) e {nome: vetor} -> nome do perfil mais parecido por janela (None se nenhum passa)."""
    if not perfis:
        return [None] * len(emb)
    nomes = list(perfis)
    sim = _normalizar(emb) @ _normalizar(np.array([perfis[n] for n in nomes])).T
    melhor = np.argmax(sim, axis=1)
    return [nomes[j] if sim[i, j] >= limite else None for i, j in enumerate(melhor)]


def nomear_grupos(emb, rotulos, perfis: dict, limite: float = LIMITE_PERFIL) -> dict:
    """{grupo: nome do perfil}. Um perfil só nomeia um grupo (o mais parecido); abaixo do limite, ninguém."""
    if not perfis or len(rotulos) == 0:
        return {}
    nomes = list(perfis)
    sim = _centroides(_normalizar(emb), np.asarray(rotulos)) @ _normalizar(np.array([perfis[n] for n in nomes])).T
    pares = sorted(((sim[g, p], g, p) for g in range(sim.shape[0]) for p in range(sim.shape[1])), reverse=True)
    usados_g, usados_p, nomeados = set(), set(), {}
    for valor, g, p in pares:
        if valor < limite:
            break
        if g not in usados_g and p not in usados_p:
            nomeados[g] = nomes[p]
            usados_g.add(g)
            usados_p.add(p)
    return nomeados


# --- Turnos ------------------------------------------------------------------

def _suavizar(jan, pessoas) -> list:
    """Uma janela isolada, entre duas vizinhas coladas da mesma pessoa, é troca falsa: acompanha as vizinhas."""
    saida = list(pessoas)
    for i in range(1, len(jan) - 1):
        colada = jan[i][0] - jan[i - 1][0] <= PASSO_S + 1e-6 and jan[i + 1][0] - jan[i][0] <= PASSO_S + 1e-6
        if colada and pessoas[i - 1] == pessoas[i + 1] != pessoas[i]:
            saida[i] = pessoas[i - 1]
    return saida


def montar_turnos(jan, pessoas) -> list:
    """
    Janelas (inicio, fim) e a pessoa de cada uma -> [Turno]. Entre duas janelas vizinhas de pessoas
    diferentes, a troca é no meio da parte em que elas se sobrepõem.
    """
    if not jan:
        return []
    pessoas = _suavizar(jan, pessoas)
    turnos = []
    for (ini, fim), pessoa in zip(jan, pessoas):
        ultimo = turnos[-1] if turnos else None
        if ultimo and ultimo.pessoa == pessoa and ini - ultimo.fim < JUNTAR_PAUSA_S:
            ultimo.fim = max(ultimo.fim, fim)
            continue
        comeco = ini
        if ultimo and ini < ultimo.fim:                      # pessoa diferente sobrepondo: troca no meio
            comeco = (ini + ultimo.fim) / 2
            ultimo.fim = comeco
        turnos.append(Turno(comeco, fim, pessoa))
    return [t for t in turnos if t.fim > t.inicio]


def atribuir(segmentos, turnos, folga_s: float = 1.0) -> list:
    """
    Cada segmento do Whisper fica com a pessoa que mais falou durante ele. Sem sobreposição,
    pega o turno mais próximo se estiver a menos de `folga_s`; senão fica sem pessoa.
    Um segmento inteiro vai para uma pessoa só (se houver troca no meio dele, vence quem falou mais).
    """
    saida = []
    for seg in segmentos:
        tempo = {}
        for t in turnos:
            comum = min(seg.fim, t.fim) - max(seg.inicio, t.inicio)
            if comum > 0:
                tempo[t.pessoa] = tempo.get(t.pessoa, 0.0) + comum
        if tempo:
            pessoa = max(tempo, key=tempo.get)
        else:
            perto = [(max(t.inicio - seg.fim, seg.inicio - t.fim), t.pessoa) for t in turnos]
            distancia, nome = min(perto, default=(None, None))
            pessoa = nome if distancia is not None and distancia <= folga_s else None
        saida.append(replace(seg, pessoa=pessoa))
    return saida


# --- Orquestração ------------------------------------------------------------

def separar(amostras, vozes, modo: str, n_falantes: int | None = None, perfis: dict | None = None,
            limite_agrupar: float = LIMITE_AGRUPAR, limite_perfil: float = LIMITE_PERFIL) -> Separacao:
    """
    modo 'agrupar': descobre as pessoas (e dá o nome de quem tiver perfil). modo 'perfis': só reconhece
    quem está cadastrado. `vozes` tem `nome`, `trechos_de_fala(amostras)` e `embutir(amostras, janelas)`.
    """
    if modo not in ("agrupar", "perfis"):
        raise ValueError(f"modo desconhecido: {modo}")
    perfis = perfis or {}
    if modo == "perfis" and not perfis:
        raise ValueError("o modo 'perfis' precisa de pelo menos um perfil cadastrado")
    trechos = vozes.trechos_de_fala(amostras)
    jan = janelas(trechos)
    emb = _normalizar(vozes.embutir(amostras, jan)) if jan else np.zeros((0, 1), dtype=np.float32)

    if modo == "perfis":
        nomes = [n or DESCONHECIDO for n in reconhecer(emb, perfis, limite_perfil)]
    else:
        rotulos = agrupar(emb, n_falantes, limite_agrupar)
        nomeados = nomear_grupos(emb, rotulos, perfis, limite_perfil)
        rotulo_de, proximo = {}, 1
        for g in range(int(rotulos.max()) + 1 if len(rotulos) else 0):
            if g in nomeados:
                rotulo_de[g] = nomeados[g]
            else:
                rotulo_de[g] = f"Pessoa {proximo}"
                proximo += 1
        nomes = [rotulo_de[int(g)] for g in rotulos]

    turnos = montar_turnos(jan, nomes)
    fala = {}
    for t in turnos:
        fala[t.pessoa] = fala.get(t.pessoa, 0.0) + (t.fim - t.inicio)
    info = {
        "modo": modo,
        "modelo_voz": getattr(vozes, "nome", None),
        "falantes_pedidos": n_falantes,
        "perfis_usados": sorted(perfis),
        "pessoas": [{"pessoa": p, "fala_s": round(s, 1), "perfil": p in perfis}
                    for p, s in sorted(fala.items(), key=lambda kv: -kv[1])],
        "limites": {"agrupar": limite_agrupar, "perfil": limite_perfil},
    }
    return Separacao(turnos=turnos, info=info)


def vetor_de_perfil(amostras, vozes) -> tuple:
    """
    Áudio de UMA pessoa falando -> (vetor médio, info). Levanta ValueError se a amostra tiver pouca fala
    ou parecer ter mais de uma voz (coerência baixa).
    """
    trechos = vozes.trechos_de_fala(amostras)
    fala = sum(f - i for i, f in trechos)
    if fala < MIN_FALA_PERFIL_S:
        raise ValueError(f"só {fala:.0f} s de fala na amostra; preciso de pelo menos {MIN_FALA_PERFIL_S:.0f} s "
                         "(20 a 30 s é o ideal, só a pessoa falando, sem música).")
    emb = _normalizar(vozes.embutir(amostras, janelas(trechos)))
    media = _normalizar(emb.mean(axis=0))
    coerencia = float(np.mean(emb @ media))
    if coerencia < 0.5:
        raise ValueError(f"a amostra parece ter mais de uma voz ou muito ruído (coerência {coerencia:.2f}). "
                         "Grave só a pessoa falando, num lugar quieto.")
    return media, {"fala_s": round(fala, 1), "janelas": len(emb), "coerencia": round(coerencia, 2)}
