# Documentação acadêmica — EcoRadar

## 1. Problema abordado

O Piauí possui forte variação sazonal de chuva, temperatura e umidade. A vigilância ambiental precisa combinar detecções de focos com contexto meteorológico e territorial; consultar cada fonte isoladamente dificulta a priorização municipal. O EcoRadar organiza essas informações sem transformar detecção por satélite em confirmação de incêndio e sem tratar um índice experimental como previsão validada.

## 2. Objetivos

### Objetivo geral

Construir uma plataforma de Big Data capaz de extrair, integrar, armazenar e visualizar dados ambientais reais para apoiar a análise preventiva de risco de incêndio nos 224 municípios do Piauí.

### Objetivos específicos

- coletar focos oficiais do INPE e malhas/códigos do IBGE;
- agregar meteorologia de estações INMET e cobertura complementar Open-Meteo;
- padronizar schemas, datas, identificadores e unidades;
- manter uma camada analítica em Parquet e uma camada operacional em SQLite;
- produzir visualizações interativas e alertas claramente rotulados;
- criar uma heurística explicável para uso imediato;
- permitir treinamento supervisionado temporal quando houver histórico suficiente;
- preparar expansão para seca, inundação e outras ameaças.

## 3. Tecnologias

Python coordena a aplicação. Pandas/NumPy tratam dados operacionais; PySpark executa o ETL histórico; SQLite mantém o estado local; Parquet reduz leitura e armazenamento; Streamlit implementa a interface; Plotly e Folium entregam gráficos/mapas; scikit-learn implementa o Random Forest; Requests integra APIs; GeoPandas fica disponível para análises geoespaciais avançadas.

## 4. Arquitetura

```text
INPE ─────────┐
IBGE ─────────┼─> services/ ─> validação/cache bruto ─> PySpark ETL ─> Parquet
INMET ────────┤                         │                              │
Open-Meteo ───┘                         └─────────────> SQLite <───────┘
                                                           │
                                   risco/alertas/modelo <──┤
                                                           │
                                       Streamlit/Plotly/Folium
```

As integrações retornam dados e uma lista de impedimentos. O orquestrador persiste atualizações por fonte. A interface consulta somente SQLite, portanto não inicia Spark e não depende de uma chamada externa em cada navegação.

## 5. Processo ETL

### Extract

- download dos CSVs diários publicados pelo INPE;
- consulta das APIs de Localidades e Malhas do IBGE;
- consulta diária por coordenada à Open-Meteo;
- download batch opcional de ZIP anual do INMET.

### Transform

- conversão de campos e nomes para um schema canônico;
- filtragem pelo código estadual 22;
- timestamps em formato ISO e datas para agregação;
- remoção de duplicidades por identificador INPE;
- agregação de focos e meteorologia por município/dia;
- junção pelo código IBGE;
- validação explícita de dados ausentes.

### Load

- dados operacionais com upsert em SQLite;
- histórico particionado por data em Parquet;
- relatório JSON com contagens e falhas.

PySpark é adequado ao crescimento do histórico e às junções/agrupamentos distribuídos. No modo local usa dois núcleos e limites de memória, e não é carregado pelo dashboard.

## 6. Classificação de risco

### Índice heurístico v1

O índice soma contribuições normalizadas: umidade (25), temperatura (20), precipitação (20), vento (15), focos dos 30 dias anteriores (15) e sazonalidade (5). A pontuação varia entre 0 e 100. As classes são: baixo (`<30`), moderado (`30–54,9`), alto (`55–74,9`) e crítico (`≥75`).

Esse método é declarativo e não possui calibração epidemiológica ou operacional; por isso a UI sempre o identifica como heurístico. Temperatura, umidade, vento ou precipitação ausentes tornam a pontuação indisponível.

### Random Forest opcional

O alvo é `foco no dia seguinte = 1`. Os atributos incluem clima do dia, latitude/longitude, sazonalidade senoidal e contagens históricas defasadas. O treino usa datas iniciais e o teste usa os 20% finais, evitando aleatoriedade temporal. Rolagens de focos usam `shift(1)`, impedindo que o próprio dia predito entre como atributo.

O sistema salva acurácia, precisão, recall, F1, ROC-AUC, matriz de confusão, prevalência das classes e importâncias. Se os critérios mínimos falham, nenhum modelo ou métrica é criado.

## 7. Gráficos e mapa

- linha/área diária: contagem de registros INPE por data;
- barras mensais: soma dos registros reais do recorte;
- ranking: agregado municipal com clima médio e precipitação acumulada;
- dispersões: média meteorológica estadual versus total diário de focos;
- coroplético: classe heurística associada à geometria IBGE;
- pontos: coordenadas exatas presentes no CSV INPE.

O mapa usa camadas diferentes para risco estimado e foco observado.

## 8. Alertas

Alertas são gerados quando a pontuação ultrapassa o limite configurado. O registro armazena município, classe, pontuação, data de referência, fatores, fontes e status. A combinação município/data/classe é única, tornando a operação idempotente. O alerta é preventivo e não equivale a incêndio confirmado.

## 9. Limitações

- um CSV diário nacional pode ser grande e conter detecções de diferentes satélites;
- satélites distintos podem observar a mesma área; não há deduplicação científica de eventos;
- Open-Meteo é reanálise/previsão em grade, não uma estação dentro de cada município;
- estações INMET não cobrem todos os municípios e dados brutos podem ter falhas;
- a heurística não foi calibrada contra área queimada ou laudos de ocorrência;
- a versão local não envia SMS, e-mail ou alertas a autoridades;
- o treinamento demanda histórico consistente que não acompanha o repositório.

## 10. Evoluções futuras

- usar eventos de fogo/área queimada como alvo mais robusto;
- integrar risco oficial do INPE e imagens de satélite;
- calibrar limiares por validação temporal e espacial;
- banco espacial PostGIS e orquestração Airflow/Dagster;
- detecção de drift e monitoramento do modelo;
- previsão de seca, enchente e qualidade do ar;
- perfis de acesso, auditoria e alertas externos autorizados.
