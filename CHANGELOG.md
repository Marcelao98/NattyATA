# Changelog

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
