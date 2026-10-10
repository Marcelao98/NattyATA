# Natty-ATA

Transforma um arquivo de áudio ou vídeo em texto, localmente, com o
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) (modelo
`large-v3-turbo`, CPU, int8). Faz parte do ecossistema da Natty, mas é
independente dela: nada de Discord aqui.

## Instalação

Requer Python 3.14 (o mesmo da Natty) e o **ffmpeg** no PATH.

```bash
# ffmpeg (abra um terminal novo depois)
winget install Gyan.FFmpeg        # Windows
brew install ffmpeg               # macOS
sudo apt install ffmpeg           # Linux

# projeto
python -m venv .venv
.venv\Scripts\activate            # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e .
```

## Uso

```bash
ata gravacao.opus
```

Grava `transcricoes/gravacao.txt`, com parágrafos separados por linha em
branco, e mostra o progresso no terminal. Aceita qualquer formato que o
ffmpeg abra: `.opus`, `.ogg`, `.mp3`, `.m4a`, `.wav`, `.mp4`...

| Flag | Padrão | O que faz |
|---|---|---|
| `--modelo` | `large-v3-turbo` | modelo do faster-whisper (`small`, `base`... se a RAM apertar) |
| `--lang` | `pt` | idioma; `auto` deixa o Whisper detectar (gerou alucinações em outros idiomas, por isso não é o padrão) |
| `--termos arquivo.txt` | desligado | termos, um por linha (`#` comenta), passados como `hotwords` |
| `--saida pasta` | `transcricoes/` | pasta onde o `.txt` é gravado |

Use `--termos` com cuidado: uma lista longa de nomes já causou um loop de
repetição numa sessão real.

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

Rodam com dublês: sem rede, sem modelo e sem ffmpeg.
