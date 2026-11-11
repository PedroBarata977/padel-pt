# Portugueses no Padel

Dashboard que acompanha os jogadores portugueses no Premier Padel e no CUPRA FIP Tour (Platinum, Gold, Silver, Bronze e Finals).

O site da FIP está protegido pela Cloudflare, que bloqueia pedidos automáticos vindos de servidores (o GitHub incluído). Por isso o trabalho está dividido em duas partes:

| Parte | Onde corre | Quando | O que faz |
|---|---|---|---|
| FIP | **PC do Pedro** (tarefa agendada do Windows "PadelPT - FIP") | 07:05, 12:05, 17:05, 22:05 (e ao ligar, se falhou uma) | Calendário, inscritos (PDF), quadros, IDs dos torneios → `docs/fip.json`, enviado para o GitHub |
| MatchScorer | GitHub Actions | De hora a hora e sempre que chega um `fip.json` novo | Ordem de jogo, resultados, live → `docs/data.json` |

O dashboard (`docs/index.html`, GitHub Pages) lê `data.json` e volta a lê-lo a cada 60 s.

## O que mostra

| Estado do torneio | O que aparece |
|---|---|
| Em curso | Jogos dos portugueses: ao vivo (sets, pontos, serviço), próximos (campo, ordem, "não antes das…") e resultados. Percurso no quadro. |
| Inscrições fechadas | Portugueses inscritos, parceiro e se estão no quadro principal, na qualificação ou na lista de espera. Quadro quando sair. |
| Inscrições abertas | O torneio. **A FIP não publica inscritos antes do fecho**: se aparecer uma lista, entra automaticamente. |
| Por abrir | Só o torneio. |

## Instalação no PC (Windows, uma vez)

1. Cria um token no GitHub: https://github.com/settings/personal-access-tokens/new
   - Token name: `padel-pc` · Expiration: 366 days
   - Repository access: **Only select repositories** → `padel-pt`
   - Permissions → Repository permissions → **Contents: Read and write**
   - *Generate token* e copia-o (só aparece uma vez).
2. Na pasta `Documentos\padel-pt`, faz duplo clique em **INSTALAR.bat**.
   Instala o Python se faltar, testa o acesso à FIP **a partir do teu PC**, pede o token, envia a primeira recolha e cria a tarefa agendada.
3. Abre https://pedrobarata977.github.io/padel-pt/

Logs: `Documentos\padel-pt\logs\fip.log`. Para correr já sem esperar: Agendador de Tarefas → "PadelPT - FIP" → Executar.
O token expira ao fim de um ano: quando expirar, apaga `github_token.txt` e corre de novo o INSTALAR.bat.

## Quando parte (vai partir)

- **Ponto amarelo** no canto do dashboard = avisos. Aparecem dentro do cartão do torneio (ex.: "PDF inscritos lido mas sem equipas — layout mudou?").
- **Ponto vermelho** = algum site bloqueou pedidos (Cloudflare).
- **"FIP: há N h"** a subir acima de 14 h = o PC esteve desligado ou a tarefa falhou: vê `logs\fip.log`.
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

Correr à mão: `python -m collector.main fip` (PC) · `python -m collector.main live` (GitHub) · `python -m collector.main all` (tudo).
