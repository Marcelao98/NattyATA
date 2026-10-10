# Natty-ATA

Motor que transforma um arquivo de áudio em texto (faster-whisper). Parte do
ecossistema da Natty, mas independente: não importa nada do natty-bot e não
tem Discord.

## Princípios

- **Lógica pura separada da casca.** `audio.py`, `motor.py` e `texto.py` têm
  a lógica; `cli.py` só traduz argumentos e imprime. Nada de regra de negócio
  na CLI.
- **Testes com dublês.** `unittest`, sem rede, sem modelo real, sem ffmpeg
  real. Dependências externas entram como parâmetro (`carregar_audio`,
  `obter_modelo`, `executar`, `achar`) para o teste trocar.
- **Nenhum modelo no repositório.** Pesos ficam no cache do Hugging Face
  (`HF_HOME` move o cache).
- **Parâmetros provados na sessão real não mudam sem motivo:** `language="pt"`,
  `vad_filter=True`, `condition_on_previous_text=False`, `hotwords` desligado
  por padrão, áudio passado como array (nunca o caminho).
- Código, comentários e mensagens em português.

## Comandos

```bash
python -m unittest discover -s tests
ata arquivo.opus
```
