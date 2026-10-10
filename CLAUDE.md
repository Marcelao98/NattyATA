# Natty-ATA

Ferramenta que transforma vídeos e áudios (primeiro do YouTube) em material
útil: transcrição, pontos-chave, explicações didáticas. Parte do ecossistema
da Natty, mas independente: não importa nada do natty-bot e não tem Discord.

## Arquitetura

Duas metades com uma fronteira clara entre elas:

```
CÓDIGO (Python, determinístico)
  URL do YouTube
    ├─ tem legenda e o usuário aprovou os trechos? ─► Legenda ─┐
    └─ senão ─► baixa áudio ─► Motor (Whisper) ────────────────┤
  arquivo local ─► Motor (Whisper) ────────────────────────────┤
                                                               ▼
                                       Texto ─► pasta do vídeo (transcricoes/<slug>/)
─────────────────────────────────────────────────────────────────┼──────────────
AGENTES (LLM, sob demanda)                                       ├─► Escrivão  ─► pontos-chave.md
                                                                 ├─► Preceptor ─► didatico.md
                                                                 └─► (outros no futuro)
```

**Regra central: só vira agente o que exige julgamento.** Baixar, decodificar,
transcrever e formatar é código comum, testável e sem custo de LLM. Os agentes
nunca baixam nem transcrevem; o código nunca resume nem interpreta.

### A pasta do vídeo é o contrato

Cada fonte vira uma pasta em `transcricoes/<slug>/`. É a única coisa que as
duas metades compartilham:

| Arquivo | Quem escreve | Conteúdo |
|---|---|---|
| `fonte.json` | Fonte | url, título, canal, duração, data, id do vídeo |
| `transcricao.json` | Legenda ou Motor | segmentos `{inicio, fim, texto}` + metadados (`origem`, modelo, idioma) |
| `transcricao.txt` | Texto | parágrafos separados por linha em branco |
| `pontos-chave.md` | Escrivão | ver abaixo |
| `didatico.md` | Preceptor | ver abaixo |

`origem` diz de onde veio o texto: `legenda-manual`, `legenda-automatica` ou
`whisper`. Os agentes leem esse campo para saber o quanto confiar em nomes e
termos técnicos.

O áudio baixado é temporário e apagado depois da transcrição (não guardar
mídia). Os agentes citam trechos pelo horário (`[12:34]`), que vem do
`transcricao.json`; num vídeo do YouTube o horário vira link `&t=754s`.

### Legenda primeiro, Whisper se o usuário quiser

Para URL do YouTube, a primeira coisa é olhar se o vídeo tem legenda no idioma
pedido (`--lang`). Baixar só a legenda leva segundos; transcrever com Whisper
leva minutos. Então:

1. **Sem legenda** → baixa o áudio e transcreve com Whisper.
2. **Com legenda** → baixa só a legenda (sem áudio), preferindo a manual
   (escrita pelo autor) à automática do YouTube.
3. **O usuário decide a qualidade.** O terminal mostra o tipo da legenda
   (manual ou automática), alguns indicadores calculados e 3 trechos de ~30 s
   (começo, meio e fim), e pergunta: usar a legenda ou transcrever com
   Whisper. Os indicadores são só dica (ex.: proporção de pontuação e
   maiúsculas, marcas como `[Música]`); a decisão é sempre do usuário.
4. Escolheu Whisper → só então baixa o áudio.

A legenda vira os mesmos segmentos `{inicio, fim, texto}` do Motor, então
`texto.py` e os agentes não sabem nem precisam saber de onde veio. A legenda
automática do YouTube repete linhas (texto "rolando"); o parser remove as
repetições.

Flag `--texto perguntar|legenda|whisper` (padrão `perguntar`) para pular a
pergunta. Sem terminal interativo, `perguntar` não é permitido: a CLI pede a
flag explícita em vez de escolher sozinha.

### Camada de código (`natty_ata/`)

- `fonte.py`: URL do YouTube → `fonte.json`, legendas disponíveis, download
  da legenda ou do áudio via `yt-dlp`. Arquivo local passa direto.
- `legenda.py`: legenda (.vtt) → segmentos; escolha manual × automática;
  amostras e indicadores para o usuário julgar. Lógica pura, sem perguntar
  nada (quem pergunta é a CLI).
- `audio.py`: arquivo → array float32 mono 16 kHz via ffmpeg.
- `motor.py`: array → segmentos (faster-whisper `large-v3-turbo`, CPU, int8).
- `texto.py`: segmentos → parágrafos.
- `cli.py`: casca fina. `ata <url-ou-arquivo>` produz a pasta do vídeo.

### Camada de agentes (`.claude/agents/`)

Subagentes do Claude Code. Cada um lê a pasta do vídeo e escreve um `.md`
nela. São chamados conforme a necessidade, nunca em cadeia automática.

- **Escrivão**: registro fiel. Antes de começar, pergunta ao usuário em que
  focar (ex.: "só as decisões", "os argumentos contra X", "tudo"). Extrai
  pontos-chave, definições, números, nomes e afirmações, cada um com o
  horário de onde veio. Não acrescenta conhecimento de fora e não explica:
  se o vídeo não diz, o Escrivão não diz. Sinaliza trechos que a transcrição
  provavelmente errou.
- **Preceptor**: didática. Pega um conteúdo difícil (ex.: uma aula densa de
  matemática) e reconstrói em ordem de aprendizado: pré-requisitos, intuição
  antes da fórmula, exemplos, analogias, exercícios com resposta. Pode usar
  conhecimento de fora, mas marca o que é acréscimo dele e o que é do vídeo.
  Pergunta o nível do usuário se não estiver claro.

Os dois papéis são separados de propósito: um é fiel ao vídeo, o outro é
livre para ensinar. Misturar os dois num agente só faz o resumo inventar e a
explicação ficar presa ao texto.

Novos agentes entram como novos arquivos em `.claude/agents/` e novos `.md`
na pasta do vídeo, sem mexer no código (ex.: um que gera flashcards, um que
compara dois vídeos).

## Princípios

- **Lógica pura separada da casca.** `cli.py` só traduz argumentos e imprime.
- **Testes com dublês.** `unittest`, sem rede, sem modelo, sem ffmpeg, sem
  yt-dlp reais. Dependências externas entram como parâmetro para o teste trocar.
- **Nenhum modelo nem mídia no repositório.** Pesos ficam no cache do Hugging
  Face (`HF_HOME` move o cache); `transcricoes/` é ignorada pelo git.
- **Nenhuma chamada de LLM no pacote Python.** O LLM vive só nos agentes.
- **Parâmetros provados na sessão real não mudam sem motivo:** `language="pt"`,
  `vad_filter=True`, `condition_on_previous_text=False`, `hotwords` desligado
  por padrão, áudio passado como array (nunca o caminho).
- Código, comentários, mensagens e agentes em português.

## Roteiro

1. Motor de transcrição de arquivo local. **(feito)**
2. Fonte YouTube (`yt-dlp`): legenda primeiro com aprovação do usuário,
   Whisper como alternativa; pasta do vídeo, `transcricao.json`.
3. Escrivão.
4. Preceptor.

## Comandos

```bash
python -m unittest discover -s tests
ata arquivo.opus
```
