# Testes com mídia real

Diário dos testes da Vatty com áudio e vídeo de verdade: o que foi rodado, o que deu certo, o que
quebrou e o que mudou por causa disso. Os testes automáticos usam dublês; é aqui que fica a prova
com o mundo real. Uma entrada por teste, a mais nova em cima.

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
