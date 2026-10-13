# Testes com mídia real

Diário dos testes da Vatty com áudio e vídeo de verdade: o que foi rodado, o que deu certo, o que
quebrou e o que mudou por causa disso. Os testes automáticos usam dublês; é aqui que fica a prova
com o mundo real. Uma entrada por teste, a mais nova em cima.

---

## A fazer — Gravação da tela com o áudio (0.16.0, ainda não rodado)

Feito e testado só com dublês. Precisa de um Windows com ffmpeg e Tesseract no PATH e o extra
`[gravacao]`. Anotar o resultado de cada passo aqui, numa entrada nova com a data.

**1. A tela grava e para direito (1 min).**
`vatty gravar --tela --duracao 20`. Deixe uma janela com texto grande na tela.
- Aparece o aviso de privacidade e a linha `tela: tela inteira (2 quadros por segundo)`?
- A pasta `gravacoes/<data>/` tem `sistema.wav`, `tela.mp4` e `gravacao.json`?
- O `tela.mp4` abre no player, tem uns 20 s e o texto dá para ler?
- Anotar: tamanho do `tela.mp4` (MB por minuto), resolução, se apareceu o aviso
  "o ffmpeg não disse quando gravou o primeiro quadro" (`inicio_aproximado: true` no `gravacao.json`).

**2. Ctrl+C no meio.** `vatty gravar --tela` e pare com Ctrl+C depois de uns 30 s.
- O `tela.mp4` fecha e abre no player? (o ffmpeg não pode morrer junto com o Ctrl+C)
- Sobrou algum `ffmpeg.exe` rodando no Gerenciador de Tarefas? Não pode sobrar.

**3. Uma janela só.** `vatty gravar --tela-janela "<título exato>" --duracao 20` (ex.: o PowerPoint).
- Grava só a janela? E com um título que não existe, a CLI dá erro claro e não deixa pasta vazia?
- Feche a janela no meio da gravação: aparece "a gravação da tela parou antes do fim"?

**4. Sincronia (o mais importante).** Um vídeo ou slides com troca em horários conhecidos e fala
junto, por exemplo um vídeo do YouTube com slides em tela cheia, ou você trocando slides e dizendo
"slide dois" na hora da troca: `vatty gravar --mic --tela --transcrever --manter-tela --manter-audio`
por 3 a 5 minutos.
- Para 5 trocas de slide, compare o `inicio` no `visual.json` com o `[mm:ss]` da fala que anuncia a troca no
  `transcricao.txt`. Anotar a diferença de cada uma (o esperado é até ~1 s).
- Anotar o `sincronia.deslocamento_s` do `visual.json` e os `inicios` do `gravacao.json`. O deslocamento
  esperado é negativo e pequeno (a tela abre antes do áudio, uns 0,5 a 2 s).
- Se a diferença for constante (todas adiantadas ou atrasadas no mesmo tanto), a conta do início da tela está
  errada; se crescer com o tempo, é deriva do relógio (anotar a diferença no começo e no fim).

**5. Limpeza.** Repetir o passo 4 sem `--manter-tela` e com `--apagar-audio`.
- No fim, a pasta da gravação sumiu e a pasta do vídeo tem `visual.json` e `frames/`?

**6. Falha do visual.** Tire o Tesseract do PATH só nesse terminal e rode `vatty gravar --tela --transcrever --duracao 20`.
- A CLI sai com código 1, o texto fica salvo e a pasta da gravação (áudio e tela) continua lá?
- Ponha o Tesseract de volta e rode o comando que ela sugeriu (`vatty gravacoes/<pasta> --visual aula`).

**7. Peso.** Durante o passo 4, olhar o uso de CPU do `ffmpeg.exe` e se o áudio falhou ou picotou.

---

## 2026-10-12 — Vídeo curto do TikTok (51 s, vertical, legenda animada na tela)

**Comando:** `vatty <arquivo>.mp4 --visual aula --falantes auto --preprocessar nao --lang pt`
(o vídeo foi baixado à mão com `yt-dlp`; ver "URL do TikTok" abaixo).

**Texto: ótimo.** Whisper em 45 s (texto + falantes), fala clara, sem erro visível em 47 s de
monólogo. A única falha foi no fim, com a música de saída: *"Beauty and Star"*.

**Falantes: certo.** Pessoa 1 (0:47) é o apresentador; a "Pessoa 2" (0:04) é o fim com música.

**Visual (`aula`): nada.** 0 slides. O vídeo é um rosto falando com legenda animada palavra por
palavra. O perfil `aula` procura uma tela que muda e depois fica parada, e a máscara de movimento
trata a legenda como "região que mexe o tempo todo". Era o esperado: este é o caso do perfil
`corte`, que ainda não existe. A legenda na tela repete a fala, então não se perdeu conteúdo.
O Tesseract com `--psm 11` (texto esparso) leu `parcele.ele nunca` num quadro; com o modo padrão,
não leu nada. Se o `corte` for feito, ele precisa do `--psm 11`.

**O que quebrou no caminho**

1. **URL do TikTok.** O yt-dlp precisa do `curl_cffi` para se passar por navegador (sem ele:
   `Unexpected response from webpage request`). Com ele instalado, o vatty lê os dados do vídeo,
   mas o TikTok barra a segunda requisição, a do download do áudio (`Unable to extract universal data
   for rehydration`, duas vezes seguidas). Baixar direto com `python -m yt_dlp <url>` funciona.
   A fonte também grava `"tipo": "youtube"` e imprime "Lendo o vídeo no YouTube..." para qualquer URL.
2. **`--preprocessar perguntar` sem terminal.** O diagnóstico recomendou (ruído, ronco), fez a
   pergunta e, sem quem respondesse, saiu com `Erro: cancelado`. O `--texto` recusa `perguntar`
   sem terminal e pede a flag explícita; o `--preprocessar` deveria fazer o mesmo.
3. **Tesseract fora do PATH.** Está instalado (winget, `C:\Program Files\Tesseract-OCR`, com `por` e
   `eng`), mas o instalador não põe no PATH. Funcionou depois de pôr à mão no terminal.

**A fazer:** fonte aceitar TikTok (uma requisição só, ou baixar o vídeo e ler o áudio dele;
`tipo` certo) **[feito na 0.14.0: `fonte.Sessao` lê a página uma vez, `curl-cffi` é dependência, `tipo: "url"` +
`plataforma`; provado só com extrator falso, falta rodar numa URL de TikTok de verdade]**; `--preprocessar` pedir a flag sem terminal; perfil `corte` com `--psm 11`.

---

## 2026-10-12 — Conversa sussurrada com música de fundo (2:51, .ogg)

O pior caso possível: amigos sussurrando, música com letra em inglês ("Time", do Pink Floyd) o tempo
todo, português e inglês misturados.

**Travamento do pré-processamento (corrigido em `54a2356`).** Com `--preprocessar sim`, o ffmpeg
ficava rodando para sempre. Causa: no ffmpeg 9.0.2, qualquer filtro depois do `arnndn`
(`speechnorm`, `dynaudnorm`) às vezes trava ou dá segfault. Com o `arnndn` por último: 10 de 10
rodadas sem falha.

**Comparação** (mesmo modelo e opções; muda só o pré-processamento e o VAD):

| Variante | Palavras | Até onde chega |
|---|---|---|
| pré-processamento + VAD padrão | ~70 | 1:14 de 2:51 |
| **sem pré-processamento + VAD padrão** | **189** | **fim** |
| pré-processamento + VAD tolerante (`threshold=0.3`, `min_speech_duration_ms=100`) | 2 | — |
| sem pré-processamento + VAD tolerante | 182 | fim |

**Conclusões**

- O pré-processamento (`speechnorm` + `arnndn`) piora sussurro e música: o RNNoise trata o sussurro
  como ruído. Ficou registrado no CLAUDE.md e no `--help`. Ainda não foi testado no caso para o qual foi
  feito (voz baixa de WhatsApp).
- O VAD padrão não era o problema; o tolerante empata e pula um pouco mais de música.
- Com `--lang pt`, o Whisper **traduziu a letra da música** para o português ("you missed the
  starting gun" virou "você perdeu o tiro de partida"). Quem lê pensa que alguém disse aquilo. Só a
  separação de voz e música (Demucs) resolveria; não foi testada.
- O diagnóstico não viu problema: a música, num volume constante, foi medida como "fundo".
- Falantes: 4 grupos, com a música provavelmente contada como uma "pessoa".
