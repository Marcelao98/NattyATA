# Changelog

## 0.3.0 — 2026-10-10

Passo 3: o Escrivão.

- `.claude/agents/escrivao.md`: subagente que lê a pasta do vídeo e escreve
  `pontos-chave-<foco>.md`, fiel ao vídeo, com horário e link de cada ponto.
- `fonte.json` ganha os capítulos que o autor marcou e a descrição do vídeo.
- `transcricao.json` com um segmento por linha, para os agentes lerem por
  faixas.
- CLAUDE.md: quem pergunta ao usuário é a conversa principal (subagente não
  conversa); um arquivo por foco; limitação do que só aparece na tela.

## 0.2.0 — 2026-10-10

Passo 2: YouTube, com legenda antes do Whisper.

- `fonte.py`: lê metadados e legendas com o yt-dlp, baixa só a legenda ou só
  o áudio (apagado depois).
- `legenda.py`: escolhe a legenda (manual antes da automática; da automática
  só a original, nunca a traduzida), lê o .vtt sem as linhas repetidas da
  legenda automática e calcula indicadores e trechos para o usuário julgar.
- A CLI mostra os trechos e pergunta: legenda ou Whisper. `--texto` pula a
  pergunta.
- `pasta.py`: cada entrada vira `transcricoes/<nome>/` com `fonte.json`,
  `transcricao.json` (com `origem`) e `transcricao.txt`.
- Parágrafo tem no máximo 60 s (`DURACAO_MAX_PARAGRAFO_S`): fala sem pausa
  virava um bloco só.

## 0.1.0 — 2026-10-10

Passo 1: motor de transcrição extraído do Escriba da Natty.

- `audio.py`: decodifica qualquer áudio/vídeo com ffmpeg (PCM f32le, mono,
  16 kHz) para array numpy; erro claro se o ffmpeg não estiver no PATH.
- `motor.py`: carrega o `large-v3-turbo` (CPU, int8) uma vez só e transcreve
  com `language="pt"`, `vad_filter=True`, `condition_on_previous_text=False`;
  `hotwords` só com arquivo de termos. Devolve segmentos e metadados, com
  callback de progresso.
- `texto.py`: junta segmentos em parágrafos quando a pausa é menor que
  `PAUSA_PARAGRAFO_S` (2 s).
- CLI `ata <arquivo>` com `--modelo`, `--lang`, `--termos` e `--saida`.
