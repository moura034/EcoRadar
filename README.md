# EcoRadar

**Inteligência que antecipa riscos.**

EcoRadar é uma aplicação acadêmica funcional de monitoramento de focos de calor e estimativa de risco de incêndio nos 224 municípios do Piauí. O sistema integra dados reais do INPE, IBGE, INMET e Open-Meteo, mantém cache local em SQLite, oferece processamento histórico com PySpark e só habilita métricas de aprendizado de máquina quando existe histórico suficiente para avaliação temporal legítima.

> O EcoRadar não confirma incêndios. Um foco é uma detecção por satélite e o índice municipal é uma estimativa heurística preventiva. A interface identifica essas duas informações separadamente.

## Funcionalidades

- dashboard com indicadores válidos, fontes e data de atualização;
- mapa municipal interativo com malha IBGE, risco e focos INPE;
- ranking pesquisável e ordenável dos 224 municípios;
- séries diária e mensal, comparação municipal e relações clima × focos;
- índice heurístico explicável, com indisponibilidade explícita quando faltam dados;
- Random Forest opcional com divisão temporal, matriz de confusão e métricas persistidas;
- central de alertas internos com histórico e fatores contribuintes;
- ETL PySpark para limpeza, deduplicação, integração e gravação em Parquet;
- importador batch dos ZIPs anuais oficiais do INMET;
- SQLite, tratamento de falhas, cache em disco e testes automatizados.

## 1. Pré-requisitos no Windows

1. Instale o **Python 3.11 ou 3.12** em [python.org](https://www.python.org/downloads/windows/) e marque `Add Python to PATH`.
2. Para o ETL PySpark, instale um **JDK 17** (por exemplo, Eclipse Temurin) e configure `JAVA_HOME`.
3. Git é opcional, mas recomendado.

Verifique:

```powershell
python --version
java -version
```

## 2. Criar o ambiente virtual

Abra o PowerShell na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Se a política do PowerShell bloquear a ativação, execute apenas na sessão atual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 3. Instalar as dependências

```powershell
pip install -r requirements.txt
```

O GeoPandas é utilizado quando análises geoespaciais adicionais são necessárias. O mapa principal usa Folium e a malha GeoJSON oficial do IBGE.

## 4. Configuração

As fontes públicas não exigem chave de API. Para alterar caminhos ou limites:

```powershell
Copy-Item .env.example .env
```

As variáveis podem ser definidas no ambiente. O código nunca grava credenciais.

## 5. Iniciar o dashboard

```powershell
streamlit run app.py
```

Na primeira execução, clique em **Sincronizar fontes oficiais**. O período interativo é limitado a 31 dias para evitar dezenas de downloads nacionais do INPE. Se uma fonte estiver fora do ar, a aplicação registra o erro e mantém qualquer cache legítimo já existente; nenhum valor substituto é inventado.

## 6. Executar o ETL PySpark

Para um intervalo curto:

```powershell
python -m pipelines.spark_etl --start 2026-11-01 --end 2026-11-07
```

O pipeline usa `local[2]`, 2 GB de memória de driver e oito partições de shuffle, configuração adequada para um notebook Windows. Ele encerra o Spark ao final. Os resultados ficam em:

- `data/processed/fire_spots.parquet/`;
- `data/processed/municipality_daily.parquet/`;
- `data/processed/etl_report.json`.

Para anos inteiros, prefira baixar/importar arquivos anuais e adaptar o estágio Extract, evitando milhares de requisições diárias. A limitação atual está documentada em [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## 7. Importar dados históricos do INMET

O INMET publica ZIPs anuais grandes, com dados horários por estação. A importação é deliberadamente batch:

```powershell
python -m services.inmet_service --year 2025
```

O arquivo agregado por estação/dia é salvo em `data/raw/inmet/`. A Open-Meteo complementa a cobertura municipal porque estações INMET não existem em todos os 224 municípios.

## 8. Treinar o modelo supervisionado

Depois de formar um histórico integrado:

```powershell
python -m models.risk_classifier --input data/processed/municipality_daily.parquet
```

O treinamento é recusado quando houver menos de 2.000 linhas válidas, menos de 30 datas ou apenas uma classe. O corte de teste usa as datas finais, nunca uma divisão aleatória. O alvo é a ocorrência de ao menos um foco INPE no município no dia seguinte. Os atributos históricos são deslocados (`shift(1)`), prevenindo vazamento do próprio dia-alvo.

Artefatos válidos são salvos em `data/models/` e passam a aparecer na página de IA.

## 9. Executar os testes

```powershell
pytest
```

Opcionalmente:

```powershell
python -m compileall .
```

## Estrutura

```text
ecoradar/
├── app.py                         # navegação, filtros e sincronização
├── assets/ecoradar-logo.svg       # identidade vetorial original
├── components/                    # UI, estado e gráficos
├── config/settings.py             # configuração e URLs oficiais
├── database/db.py                 # SQLite e upserts idempotentes
├── models/
│   ├── risk_index.py              # índice heurístico explicável
│   └── risk_classifier.py         # Random Forest temporal
├── views/                         # seis páginas funcionais via st.navigation
├── pipelines/spark_etl.py         # ETL PySpark → Parquet
├── services/                      # INPE, IBGE, INMET, clima e orquestração
├── tests/                         # testes unitários
├── data/                          # cache local, Parquet e modelos
└── docs/                          # documentação acadêmica e demonstração
```

## Fontes e honestidade dos dados

- **INPE Programa Queimadas:** CSVs oficiais diários. Arquivos diários podem conter múltiplos satélites; o painel os denomina “detecções/focos observados”, não eventos únicos de incêndio.
- **IBGE:** API de Localidades e Malhas, UF 22. A aplicação valida a presença dos 224 municípios.
- **INMET:** catálogo de estações e ZIPs anuais oficiais. Dados de estação são pontuais e podem conter falhas identificadas pelo próprio Instituto.
- **Open-Meteo:** dados diários por coordenada, usados para cobertura homogênea dos municípios; o endpoint histórico ou de previsão é escolhido conforme a data.

Detalhes, links e limitações: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Documentação acadêmica

- [Arquitetura e metodologia](docs/ACADEMIC.md)
- [Fontes de dados e limitações](docs/DATA_SOURCES.md)
- [Roteiro de demonstração](docs/DEMO_SCRIPT.md)
- [Relatório de implementação e testes](docs/IMPLEMENTATION_REPORT.md)

## Licença e uso

Projeto acadêmico. Respeite as licenças e condições de atribuição de cada fonte. Para decisões operacionais, confirme os dados nos portais oficiais e junto às autoridades ambientais.
