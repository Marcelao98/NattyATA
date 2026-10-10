# Natty-ATA

Transforma um vídeo do YouTube ou um arquivo de áudio/vídeo em texto. No
YouTube usa a legenda quando existe e você aprova; senão transcreve
localmente com o [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
(modelo `large-v3-turbo`, CPU, int8). Faz parte do ecossistema da Natty, mas é
independente dela: nada de Discord aqui.

## Instalação

Requer Python 3.14 (o mesmo da Natty) e o **ffmpeg** no PATH. Para o
YouTube, recomenda-se também o **Deno** (ou Node 22+): o YouTube exige um
runtime de JavaScript para liberar todos os formatos. Sem ele funciona, mas
com menos formatos e às vezes falha.

```bash
# ffmpeg (abra um terminal novo depois)
winget install Gyan.FFmpeg        # Windows
brew install ffmpeg               # macOS
sudo apt install ffmpeg           # Linux

# Deno (recomendado para o YouTube)
winget install DenoLand.Deno      # Windows

# Tesseract (só para --visual, o texto que aparece na tela)
# Windows: instalador do UB Mannheim (marque o idioma Portuguese)
brew install tesseract tesseract-lang                     # macOS
sudo apt install tesseract-ocr tesseract-ocr-por          # Linux

# projeto
python -m venv .venv
.venv\Scripts\activate            # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e .
```

## Uso

```bash
ata "https://www.youtube.com/watch?v=..."
ata gravacao.opus
```

Cada entrada vira uma pasta em `transcricoes/<nome>/`:

- `fonte.json`: de onde veio (url, título, canal, duração).
- `transcricao.json`: segmentos com horário e a `origem` do texto
  (`legenda-manual`, `legenda-automatica` ou `whisper`).
- `transcricao.txt`: parágrafos separados por linha em branco.

Arquivo local aceita qualquer formato que o ffmpeg abra: `.opus`, `.ogg`,
`.mp3`, `.m4a`, `.wav`, `.mp4`...

### Visual: o que aparece na tela (slides + OCR)

Aula com slide mostra fórmulas e listas que o professor não fala. Com
`--visual`, depois do texto a `ata` acha as trocas de tela, lê o texto de cada
slide com o Tesseract e grava `visual.json` e `frames/` na pasta do vídeo. O
Escrivão e o Preceptor usam isso quando existe.

```bash
ata "https://www.youtube.com/watch?v=..." --visual auto   # mostra um palpite e pergunta
ata "https://www.youtube.com/watch?v=..." --visual aula   # faz direto
ata aula.mp4 --visual aula                                # vídeo local: não baixa nada
```

- **`auto`** mostra quantas trocas de tela há por minuto, quantas palavras por
  tela e o formato, dá um palpite (aula ou não) e pergunta; Enter aceita o
  palpite. Sem terminal, use `aula` ou `nenhum`.
- **O texto sai primeiro.** Se o visual falhar (Tesseract não instalado, erro
  do ffmpeg), o texto já está salvo e a `ata` avisa e sai com código 1.
- **Vídeo:** de URL baixa só a imagem, até 720p (480p deixa o texto pequeno
  demais para o OCR), e apaga depois. Peso de 1 hora em 720p: centenas de MB
  temporários.
- **Câmera do professor:** regiões que mexem o tempo todo são ignoradas, então
  o rosto no canto não vira "troca de slide".
- **`visual.json`:** um slide por linha, com `inicio`, `fim`, `texto`,
  `confianca` (0 a 100, do OCR) e o `frame`. OCR com confiança baixa é tratado
  como duvidoso pelos agentes. Gráfico e imagem não viram texto.
- **Ainda falta** o perfil para vídeo curto com cortes rápidos (TikTok, Shorts).
  O palpite reconhece esse caso e avisa.

### Gravar o áudio do PC (Windows)

Grava o que sai nas caixas (reunião no Meet/Zoom/Teams, aula, live) e,
com `--mic`, o seu microfone em outra faixa:

```bash
pip install -e ".[gravacao]"          # uma vez: a biblioteca de captura (só Windows)

ata gravar --duracao 5                # teste rápido: grava 5 s, deixe algo tocando
ata gravar                            # grava o som do PC até Ctrl+C
ata gravar --mic --transcrever        # PC + microfone; ao parar, já transcreve
ata gravacoes/2026-10-10_14-30        # transcreve depois uma gravação guardada
```

Cada faixa vira um `.wav` de 16 kHz mono (uns 115 MB por hora) em
`gravacoes/AAAA-MM-DD_HH-MM/`: `sistema.wav` e, com `--mic`, `microfone.wav`.
Com as duas faixas o texto sai com quem falou: `Outros:` (o som do PC) e
`Eu:` (o microfone), e cada segmento do `transcricao.json` ganha `falante`.

- **Silêncio:** o Windows não entrega áudio enquanto nada toca. A gravação
  segue o relógio e completa com silêncio, então os horários continuam
  certos. Se uma faixa ficar quase muda, a `ata` avisa no fim.
- **O áudio:** depois de transcrever, a `ata` pergunta se apaga os `.wav`
  (o padrão é guardar). `--apagar-audio` ou `--manter-audio` pulam a pergunta.
- **Dispositivo:** usa o alto-falante e o microfone padrão do Windows. Para
  gravar outro, troque o padrão nas configurações de som.
- **Consentimento:** gravar uma conversa sem avisar os outros participantes
  pode ser ilegal onde você mora. A `ata` lembra disso ao começar.

### YouTube: legenda primeiro

Se o vídeo tem legenda no idioma pedido (a manual do autor antes da
automática do YouTube), a `ata` baixa só a legenda, que leva segundos, e
mostra alguns números e três trechos (começo, meio e fim). Você decide: usar
a legenda ou transcrever com Whisper, que leva minutos. O áudio só é baixado
se você escolher o Whisper, e é apagado depois.

Legenda automática quase sem pontuação e com poucas maiúsculas costuma errar
nomes e termos técnicos; nesse caso, vale o Whisper.

| Flag | Padrão | O que faz |
|---|---|---|
| `--modelo` | `large-v3-turbo` | modelo do faster-whisper (`small`, `base`... se a RAM apertar) |
| `--lang` | `pt` | idioma; `auto` usa o idioma do vídeo ou deixa o Whisper detectar (gerou alucinações em outros idiomas, por isso não é o padrão) |
| `--termos arquivo.txt` | desligado | termos, um por linha (`#` comenta), passados como `hotwords` |
| `--saida pasta` | `transcricoes/` | onde as pastas são criadas |
| `--texto` | `perguntar` | YouTube: `legenda`, `whisper` ou `perguntar` (sem terminal interativo, passe `legenda` ou `whisper`) |
| `--visual` | `nenhum` | `aula` (slides + OCR), `auto` (palpite e pergunta) ou `nenhum`; precisa do Tesseract |

### Lista de termos (`--termos`)

Ajuda o Whisper com palavras que ele costuma errar: termos em inglês, siglas,
nomes próprios. Há uma pronta para mercado financeiro:

```bash
ata "https://www.youtube.com/watch?v=..." --texto whisper --termos termos/mercado-financeiro.txt
```

O faster-whisper coloca a lista como "texto anterior" em toda janela de 30 s,
e com áudio confuso o Whisper às vezes copia a lista ou repete uma frase (já
aconteceu numa sessão real da Natty). Por isso, com `--termos`:

1. **Lista curta.** O Whisper só usa ~223 tokens da lista; acima disso a
   `ata` avisa. Coloque só o que ele erra, não palavras comuns.
2. **Detecção.** Depois de transcrever, procura sinais de loop: texto
   repetitivo demais (o mesmo critério de compressão do Whisper), segmento
   que é quase só termos da lista, ou a mesma frase em segmentos seguidos.
3. **Correção.** Refaz só esses trechos **sem** a lista. O terminal mostra
   quantos foram refeitos, e o `transcricao.json` guarda cada um em
   `trechos_refeitos` (horário, motivo e o texto de antes).

## Onde fica o modelo

O modelo (cerca de 1,5 GB) é baixado na primeira execução para o cache
padrão do Hugging Face (`~/.cache/huggingface`, no Windows
`C:\Users\<você>\.cache\huggingface`), nunca dentro do repositório. Se a
Natty já baixou o mesmo modelo, ele é reaproveitado.

Para mover o cache para outro drive, defina `HF_HOME` antes de rodar:

```powershell
setx HF_HOME "D:\huggingface"      # Windows, vale para terminais novos
```
```bash
export HF_HOME=/mnt/dados/huggingface
```

## Testes

```bash
python -m unittest discover -s tests
```

Rodam com dublês: sem rede, sem modelo, sem ffmpeg e sem yt-dlp.

## Licença

MIT. Ver [LICENSE](LICENSE).
