# Monitor de Bids — CFE / Setor Nuclear

Monitora licitações de 8 fontes do setor nuclear e elétrico:
CFE (México), Eletronuclear, INB, CDTN (Brasil), NASA, Dioxitek (Argentina),
CCHEN (Chile) e IAEA (UNGM).

Saídas:

- `CFE_Monitor_Consolidado.xlsx` — base consolidada (estado persistente entre execuções)
- `CFE_Dashboard.html` — dashboard interativo, servido via GitHub Pages
- `status_fontes.json` — contagem por fonte e contador de falhas consecutivas
- `logs/` — log de cada execução (no GitHub Actions, salvo como artifact)

---

## ⚠️ Ação urgente — revogar token vazado

A versão anterior do `cfe_monitor.py` continha um token Personal Access do GitHub
hardcoded. Esse token deve ser **revogado imediatamente** mesmo já tendo saído do
código:

1. Abra <https://github.com/settings/tokens>
2. Localize o token começando com `ghp_Emt7MN5K...` (era o token hardcoded da v5)
3. Clique em **Revoke** / **Delete**
4. Gere um novo token (escopo `repo`) — guarde para configurar como Secret abaixo

---

## Execução automática (GitHub Actions)

O workflow `.github/workflows/monitor.yml` roda 2x por dia (08:00 e 14:00 BRT)
e também pode ser disparado manualmente em **Actions → CFE Monitor → Run workflow**.

### Setup inicial (uma única vez)

1. **Criar Secrets no repositório**
   `Settings → Secrets and variables → Actions → New repository secret`

   | Nome | Valor |
   | --- | --- |
   | `ANTHROPIC_API_KEY` | Sua chave da Anthropic (`sk-ant-api03-...`) |

   Não é necessário criar `GITHUB_TOKEN` — o Actions injeta um automaticamente
   com escopo do repositório.

2. **Habilitar GitHub Pages**
   `Settings → Pages → Source: Deploy from a branch → main / (root)`
   Após o primeiro run, o dashboard fica em
   `https://<seu-usuário>.github.io/<repo>/CFE_Dashboard.html`.

3. **Permitir que o Actions comite no repo**
   `Settings → Actions → General → Workflow permissions → Read and write permissions`.

### Disparo manual

Vá em **Actions → CFE Monitor → Run workflow**. Você pode passar:

- `ini` / `fim` — datas (formato `YYYY-MM-DD`) para um período específico
- `origem` — lista separada por vírgula: `CFE,ETN,INB,CDTN,NASA,DIOXITEK,CCHEN,IAEA`

Sem parâmetros, usa o intervalo padrão (calculado em `calcular_intervalo()`).

### Detecção de scrapers quebrados

A cada execução o script grava `status_fontes.json` com a contagem por fonte.
Quando uma fonte retorna **0 em 3 execuções consecutivas**, o workflow abre
automaticamente uma issue rotulada `scraper-broken` no repositório
(sem duplicar se já houver uma aberta com o mesmo título).

---

## Execução local

```bash
# 1. Clonar o repo
git clone https://github.com/<seu-usuário>/Monitor-de-Bids.git
cd Monitor-de-Bids

# 2. Criar venv e instalar deps
python -m venv .venv
source .venv/bin/activate         # Linux/Mac
# .venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
cp .env.example .env
# Edite .env e preencha ANTHROPIC_API_KEY

# 4. Carregar variáveis e rodar
export $(cat .env | xargs)        # Linux/Mac
python cfe_monitor.py
# ou para um período específico:
python cfe_monitor.py --ini 2026-04-01 --fim 2026-04-08
# ou só uma origem:
python cfe_monitor.py --origem CFE,INB
```

---

## Estrutura de arquivos

```
.
├── .github/workflows/monitor.yml   # Cron 2x ao dia + workflow_dispatch
├── cfe_monitor.py                   # Script principal
├── requirements.txt                 # Dependências Python
├── .env.example                     # Template de variáveis
├── .gitignore
├── README.md
├── CFE_Monitor_Consolidado.xlsx     # Base consolidada (commitada)
├── CFE_Dashboard.html               # Dashboard (commitado, servido via Pages)
└── status_fontes.json               # Contagem + falhas consecutivas
```

---

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Sim | Usada para classificar bids (área e tipo) |
| `GITHUB_TOKEN` | Não | Se setada, usa `publicar_github` (publicação via API). No Actions deixamos vazia — o `git push` do workflow faz a publicação. |
| `LOG_LEVEL` | Não | `DEBUG` / `INFO` / `WARNING` / `ERROR`. Padrão `INFO`. |

---

## Revisões manuais — `revisoes.csv` (novo)

As colunas **Revisão**, **Observação**, **Erro Class.** e **Área Correta** do Excel
são populadas a partir de um arquivo `revisoes.csv` na raiz do repo. O bot carrega
esse CSV em cada run e sobrescreve as 4 colunas para os bids correspondentes.

Vantagens:

- O CSV é texto puro — você edita direto pelo navegador no GitHub (clica no lápis,
  edita uma célula, commita), sem download/upload de Excel
- Suas revisões nunca são sobrescritas pelo bot
- A coluna `erro_classificacao` separa erro real do classificador de decisões
  de negócio (vencido, fora de escopo, valor baixo). Isso será usado pelo
  classificador na fase 3 para aprender com seus feedbacks

### Como editar

1. Abra <https://github.com/RenzoDias/Monitor-de-Bids/blob/main/revisoes.csv>
2. Clique no ícone de lápis (Edit this file)
3. Edite a célula desejada
4. **Commit changes**

### Estrutura do CSV

| Coluna | Valores válidos |
| --- | --- |
| `numero` | número do processo (chave) |
| `revisao` | `✔ Seguido` / `✘ Não seguido` / `👁 Em análise` / `⏸ Aguardando` |
| `observacao` | texto livre |
| `erro_classificacao` | `🔴 Sim - área errada` / `🟢 Não - classificação ok` / vazio |
| `area_correta` | `Nuclear` / `Geração` / `Serviços Gerais` / etc (preencher se erro_classificacao = 🔴) |

## Lookback configurável por fonte (novo)

Fontes esparsas (CDTN, CCHEN, IAEA) agora usam janela de busca mais ampla:
60 dias para CDTN, 30 dias para CCHEN e IAEA. Isso evita falsos positivos no
alerta de "scraper quebrado" e captura bids de órgãos que publicam raramente.
A configuração está em `LOOKBACK_DIAS_FONTE` no topo do `cfe_monitor.py`.

## Roadmap

**Fase 1 (✅ entregue):**

- Token GitHub fora do código
- Execução automática via GitHub Actions (cron 2x ao dia)
- Logging estruturado
- Detecção e alerta de scraper quebrado

**Fase 2 (parcial — em andamento):**

- ✅ Lookback por fonte (CDTN/CCHEN/IAEA)
- ✅ `revisoes.csv` como fonte de verdade para Revisão/Observação
- ✅ Coluna "Erro de Classificação?" no Excel
- ⬜ Modularização do `cfe_monitor.py`
- ⬜ Benchmark de baseline da acurácia

**Fase 3 (em planejamento):**

- Sonnet 4.6 + extended thinking
- Princípios explícitos no prompt (instalação nuclear ≠ item nuclear)
- Few-shot dinâmico a partir da coluna `erro_classificacao`
- Classificação em 2 passadas

**Fase 4 (idealizada):**

- UI de edição inline no dashboard
