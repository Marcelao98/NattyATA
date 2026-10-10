# Changelog

## 0.6.0 — 2026-10-10

Gravação do áudio do PC (Windows).

- `gravacao.py` e `ata gravar`: grava o som do PC (loopback WASAPI via
  PyAudioWPatch, extra `.[gravacao]`) e, com `--mic`, o microfone em outra
  faixa. Cada faixa é um `.wav` de 16 kHz mono em `gravacoes/AAAA-MM-DD_HH-MM/`.
- A linha do tempo segue o relógio: quando o Windows não entrega áudio
  (silêncio), a faixa é completada com silêncio, e os horários continuam certos.
- `--transcrever` transcreve ao parar; `ata <pasta-da-gravacao>` transcreve
  depois. As duas faixas viram um texto só, intercalado por horário, com
  `falante` (`eu` / `outros`) em cada segmento e `Eu:` / `Outros:` no `.txt`.
- Depois de transcrever, pergunta se apaga os `.wav` (padrão: guardar);
  `--apagar-audio` e `--manter-audio` pulam a pergunta. Só apaga os `.wav`
  que a própria `ata` criou.
- Aviso quando uma faixa fica quase muda e lembrete de consentimento ao começar.
- `Segmento` ganha `falante` (opcional; fora de gravação nada muda nos arquivos).
- Os agentes passam a registrar quem disse cada coisa quando há `falante`.
- A captura real não tem teste automático (precisa de placa de som no
  Windows): confirmar com `ata gravar --duracao 5`.

## 0.5.0 — 2026-10-10

Passo 4: o Preceptor.

- `.claude/agents/preceptor.md`: subagente que reescreve o vídeo em ordem de
  aprendizado para o nível pedido, com exemplos numéricos conferidos,
  analogias, erros comuns, exercícios com resposta e glossário. Tudo que não
  está no vídeo vem marcado como [acréscimo]; o que está leva o horário.
- Primeiro teste real dos dois agentes: vídeo de notional de opções
  (Escrivão com foco "tudo", Preceptor para iniciante).

## 0.4.0 — 2026-10-10

Lista de termos com proteção contra loop.

- `repeticao.py`: detecta loop do Whisper (texto repetitivo pelo critério de
  compressão do próprio Whisper, eco da lista de termos, frase repetida em
  segmentos seguidos).
- Com `--termos`, o motor refaz só os trechos suspeitos sem a lista e guarda
  cada um em `trechos_refeitos` no `transcricao.json`.
- Aviso quando a lista passa do limite de ~223 tokens que o Whisper usa.
- `termos/mercado-financeiro.txt`: 35 termos de derivativos e opções.

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
