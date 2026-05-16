# spotifyweb2 — patch v4 (Spotify-like polish)

Arquivo: `spotifyweb2.html` (origem: `ContaTreino/Spotify/spotifyweb2`).
100% do código original preservado. Alterações somente aditivas/cirúrgicas:

## CSS (final do `<style>`)
- Cards de **Artistas** uniformes, circulares e responsivos (≥ 800px / ≤ 800px / ≤ 380px).
  Corrige o avatar gigante estourando a coluna no mobile.
- Play button do artista centralizado sobre o avatar (estilo Spotify).
- Badges por tipo: `cb-single` (verde), `cb-ep` (âmbar), `cb-compile` (azul), `cb-album` (existente).
- Grade da Discografia (`#ap-alb-grid`) com 2 colunas no mobile e `minmax(180px,1fr)` no desktop.

## JS
- `albumKind(a)`: detecta tipo via `record_type` da Deezer; fallback heurístico
  (`nb_tracks ≤ 2` → Single, `3–6` → EP, `7+` → Álbum).
- `albumSubMeta(a)`: gera legenda `ano · N faixas` (singular/plural).
- Discografia agora usa esses helpers — badge e contagem de faixas corretos.
- **Enriquecimento lazy**: após renderizar a discografia, o front busca
  `/album/{id}` em paralelo (4 conexões) só para álbuns sem `record_type`/`nb_tracks`
  e atualiza badge + legenda sem travar a UI.
- Busca (aba **Álbuns**) também usa `albumKind/albumSubMeta`.

Nada de lógica de player/queue/auth foi tocada.
