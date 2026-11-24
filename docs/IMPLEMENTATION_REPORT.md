# Relatório de implementação

Data da entrega: 16 de novembro de 2026.

## Etapa 1 — Fundação

### Arquivos principais

`app.py`, `.streamlit/config.toml`, `config/settings.py`, `database/db.py`, `components/*`, `assets/ecoradar-logo.svg`, `.env.example`, `.gitignore`, `requirements.txt` e `pyproject.toml`.

### Funcionalidades

- identidade escura responsiva, logotipo SVG original e navegação global;
- configuração central e variáveis de ambiente;
- SQLite com WAL, índices, chaves únicas e upserts idempotentes;
- filtros globais de período e estado das fontes.

## Etapa 2 — Dados reais

### Arquivos principais

`services/inpe_service.py`, `services/ibge_service.py`, `services/inmet_service.py`, `services/weather_service.py` e `services/dashboard_service.py`.

### Funcionalidades

- CSVs oficiais diários e importação CSV/ZIP do INPE;
- 224 municípios e 224 geometrias oficiais do IBGE;
- meteorologia municipal complementar Open-Meteo em lotes;
- catálogo e importador dos ZIPs anuais oficiais de estações INMET;
- repetição HTTP limitada, timeout, persistência de origem e erros explícitos.

### Verificação ao vivo

Sincronização de 16/11/2026: 224 municípios, 3 focos no Piauí, 224 registros meteorológicos, 224 avaliações de risco e zero alertas acima do limiar padrão. Nenhuma integração reportou erro.

## Etapa 3 — Dashboard

### Arquivos principais

`views/dashboard.py`, `views/mapa.py`, `views/municipios.py` e `views/historico.py`.

### Funcionalidades

- seis indicadores com supressão de valores inválidos;
- quatro grupos de gráficos Plotly e filtros de período;
- mapa Folium com coroplético, popups, cluster de focos e camadas;
- ranking dos 224 municípios com busca, filtro, ordenação e CSV;
- séries diária/mensal, comparação municipal e clima × focos.

## Etapa 4 — Big Data

### Arquivo principal

`pipelines/spark_etl.py`.

### Funcionalidades

- extração pelas integrações reais;
- Spark `local[2]`, 2 GB de driver e oito partições;
- filtragem, deduplicação, agregação diária e junção municipal;
- Parquet particionado por data e relatório JSON;
- encerramento da JVM antes de iniciar o dashboard.

### Limite de verificação

O módulo compilou, mas o job Spark não foi iniciado durante o QA porque o host temporário não possuía PySpark/JDK configurados inicialmente. A execução está documentada e deve ser validada no notebook Windows após instalar Java 17 e `requirements.txt`.

## Etapa 5 — Inteligência artificial

### Arquivos principais

`models/risk_index.py`, `models/risk_classifier.py` e `views/inteligencia_artificial.py`.

### Funcionalidades

- índice heurístico explicável, limitado a 0–100 e indisponível sem clima essencial;
- Random Forest com classes balanceadas;
- alvo “foco no dia seguinte”, atributos históricos defasados e corte temporal;
- métricas, matriz de confusão, importâncias e persistência somente após dados mínimos;
- nenhum modelo ou métrica fictícia acompanha a entrega.

## Etapa 6 — Alertas

### Arquivo principal

`views/alertas.py` e tabelas `alerts`/`risk_snapshots` em `database/db.py`.

### Funcionalidades

- limiar configurável na interface;
- município, nível, horário, fatores, origem, status e histórico;
- chave única para evitar alertas duplicados;
- aviso explícito de que alerta estimado não confirma incêndio.

## Etapa 7 — Finalização

### Arquivos principais

`tests/*`, `README.md`, `docs/ACADEMIC.md`, `docs/DATA_SOURCES.md` e `docs/DEMO_SCRIPT.md`.

### Testes e QA

- `pytest`: **11 testes aprovados de 11**;
- `compileall`: concluído sem erro;
- integração ao vivo: INPE, IBGE, Open-Meteo, SQLite, risco e alertas;
- navegador desktop: seis rotas validadas;
- navegador móvel 390 × 844: sidebar automática, métricas empilhadas e conteúdo legível;
- mapa-base alterado para OpenStreetMap após o QA detectar que CartoDB passou a exigir chave.

## Comandos de verificação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
streamlit run app.py
```

ETL e modelo:

```powershell
python -m pipelines.spark_etl --start 2026-11-01 --end 2026-11-07
python -m models.risk_classifier --input data/processed/municipality_daily.parquet
```

## Pendências científicas, não funcionais

- formar histórico longo com satélite de referência e clima consistente;
- executar/calibrar o Random Forest antes de considerá-lo operacional;
- validar limiares contra eventos ou área queimada confirmada;
- executar o job PySpark no notebook-alvo com Java 17;
- decidir uma estratégia de atribuição espacial das estações INMET sem extrapolar artificialmente para municípios não cobertos.
