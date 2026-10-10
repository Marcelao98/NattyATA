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
