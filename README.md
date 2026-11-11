# Portugueses no Padel

Dashboard que acompanha os jogadores portugueses no Premier Padel e no CUPRA FIP Tour (Platinum, Gold, Silver, Bronze e Finals).

- **De hora a hora**, um robô do GitHub (GitHub Actions) lê o padelfip.com e o widget MatchScorer Live e escreve `docs/data.json`.
- **O dashboard** (`docs/index.html`) é uma página estática, publicada pelo GitHub Pages, que lê esse ficheiro e volta a lê-lo a cada 60 segundos.
- Custo: zero. Repositório público = minutos de Actions ilimitados e Pages grátis.

## O que mostra

| Estado do torneio | O que aparece |
|---|---|
| Em curso | Jogos dos portugueses: ao vivo (sets, pontos, serviço), próximos (campo, ordem, "não antes das…") e resultados. Percurso no quadro. |
| Inscrições fechadas | Portugueses inscritos, parceiro e se estão no quadro principal, na qualificação ou na lista de espera. Quadro quando sair. |
| Inscrições abertas | O torneio. **A FIP não publica inscritos antes do fecho**: se aparecer uma lista, entra automaticamente. |
| Por abrir | Só o torneio. |

## Instalação (uma vez, ~15 min)

1. Cria uma conta em https://github.com (grátis).
2. Cria um repositório novo: botão **New** → nome `padel-pt` → **Public** → *Create repository*.
3. Na página do repositório: **Add file → Upload files** → arrasta **todo o conteúdo** desta pasta → *Commit changes*.
   - ⚠ No Mac/Windows a pasta `.github` costuma ficar escondida e não é enviada. Confirma no repositório se existe `.github/workflows/update.yml`. Se não existir: separador **Actions** → *set up a workflow yourself* → nome `update.yml` → cola o conteúdo do ficheiro → *Commit*.
4. **Settings → Actions → General → Workflow permissions** → *Read and write permissions* → *Save*.
5. **Settings → Pages** → *Source: Deploy from a branch* → Branch `main`, pasta `/docs` → *Save*.
6. Separador **Actions** → *Atualizar dados* → **Run workflow**. Espera 2–5 min até ficar verde ✔.
7. Abre `https://O-TEU-UTILIZADOR.github.io/padel-pt/`. Para ver o ecrã com dados de exemplo: `.../padel-pt/?demo`.

## Quando parte (vai partir)

- **Ponto amarelo** no canto do dashboard = avisos. Aparecem dentro do cartão do torneio (ex.: "PDF inscritos lido mas sem equipas — layout mudou?").
- **Ponto vermelho** = o site bloqueou pedidos (Cloudflare). Se acontecer em mais de metade das corridas durante uma semana, passamos o recolhedor para o teu computador.
- **Banner "mais de 3 horas"** = o robô falhou. Vê **Actions**, abre a corrida a vermelho e copia o erro para o Claude.
- O GitHub também te manda email quando uma corrida falha.

## Estrutura

```
collector/          recolhedor Python
  fip.py            calendário, página do evento, AJAX (inscritos/quadros)
  matchscorer.py    ordem de jogo, resultados e live score
  draws.py          quadros
  entrylist.py      listas de inscritos em PDF (a parte mais frágil)
  main.py           orquestra e escreve docs/data.json
docs/index.html     dashboard
docs/data.json      dados (gerado de hora a hora)
data/pdf_cache.json PDFs já lidos (só relê quando a FIP publica nova versão)
tests/              testes com amostras reais de 11/11/2026
```

Correr à mão (com Python 3.11+): `pip install -r requirements.txt && python -m pytest -q && python -m collector.main --verbose`
