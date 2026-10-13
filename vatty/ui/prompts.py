"""
"Copiar prompt": monta o texto que a pessoa cola em qualquer chatbot (Claude, ChatGPT...) junto da
transcrição. Não chama nada: é só texto. Lógica pura.
"""

AVISO = ("Este texto vai para a IA em que você colar. A transcrição em si foi feita no seu computador, "
         "mas daqui para frente depende do serviço que você usar.")

REGRAS = ("Regras: use só o que está na transcrição, não invente nada. Cite o horário [mm:ss] de cada ponto. "
          "Trechos marcados com [?] são incertos (o Whisper não teve confiança): trate com cautela e liste os "
          "mais importantes no fim. Pessoas aparecem como 'Pessoa N' ou pelo nome dado; não adivinhe nomes.")

MODELOS = {
    "pontos_chave": ("Pontos-chave", "Extraia os pontos-chave desta transcrição, em tópicos, na ordem em que aparecem."),
    "resumo": ("Resumo em níveis", "Faça o resumo em três níveis: uma linha, um parágrafo e uma página."),
    "ata": ("Ata", "Escreva a ata desta reunião com as seções: Resumo, Decisões, Tarefas (responsável | tarefa | prazo | "
                   "horário), Pendências e Dúvidas da transcrição. Seja o mais curto possível e não decida o que a "
                   "reunião não decidiu."),
    "cartoes": ("Flashcards", "Crie flashcards de estudo com este conteúdo no formato 'P: pergunta' e 'R: resposta', "
                              "um por ideia importante, com o horário de onde saiu."),
    "explicar": ("Explicar com calma", "Explique o conteúdo de forma didática, na ordem em que se aprende: pré-requisitos, "
                                       "intuição antes da fórmula, exemplos e exercícios com resposta. Marque o que é "
                                       "acréscimo seu e o que veio da transcrição."),
    "pericia": ("Achar bugs", "Esta é a gravação de alguém testando um programa. Liste, com horário e evidência: bugs "
                              "(gravidade alta, média ou baixa), onde a pessoa esperou, passos repetidos e o "
                              "comportamento do programa (ação -> resposta). No fim, os passos para reproduzir o bug "
                              "mais grave. Não copie senha, token nem dado pessoal: escreva [oculto]."),
}
LIMITE_CARACTERES = 400_000


def tipos() -> list:
    return [{"tipo": k, "nome": v[0]} for k, v in MODELOS.items()]


def montar(tipo: str, titulo: str, transcricao: str, origem: str | None = None, foco: str | None = None) -> str:
    if tipo not in MODELOS:
        raise KeyError(tipo)
    _, tarefa = MODELOS[tipo]
    cabeca = [tarefa]
    if foco and foco.strip():
        cabeca.append(f"Foco: {foco.strip()[:200]}")
    cabeca.append(REGRAS)
    if origem == "legenda-automatica":
        cabeca.append("Origem do texto: legenda automática do YouTube. Nomes e termos técnicos podem estar errados.")
    corpo = transcricao.strip()
    if len(corpo) > LIMITE_CARACTERES:
        corpo = corpo[:LIMITE_CARACTERES] + "\n[... transcrição cortada por ser muito longa ...]"
    return "\n\n".join(cabeca + [f"Título: {titulo}", "Transcrição:", corpo])
