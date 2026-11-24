# Roteiro de demonstração — 8 a 10 minutos

## 1. Abertura (45 s)

“O EcoRadar é uma plataforma acadêmica de Big Data para integrar focos de calor, meteorologia e limites municipais no Piauí. O diferencial não é apenas visualizar: é manter rastreabilidade das fontes e separar observação de estimativa.”

Mostre o logotipo, o slogan e o aviso de honestidade dos dados.

## 2. Sincronização (1 min)

Selecione sete dias e clique em **Sincronizar fontes oficiais**. Explique:

- INPE: pontos de focos detectados por satélite;
- IBGE: 224 municípios e malhas;
- Open-Meteo: cobertura meteorológica complementar;
- INMET: importação batch de estações oficiais.

Abra “Estado das fontes”. Se uma fonte falhar, destaque que o sistema mostra a indisponibilidade em vez de inventar valores.

## 3. Dashboard (1 min)

Apresente focos, municípios atingidos, risco alto/crítico, clima médio e município de maior índice. Diga explicitamente que o maior risco é uma heurística preventiva.

Mostre evolução diária, distribuição de risco e os dois rankings visuais.

## 4. Mapa (1 min 30 s)

Explique as camadas:

- polígonos coloridos: risco estimado;
- círculos: foco observado pelo INPE.

Clique em um município e em um ponto. Use o filtro municipal e a camada de focos.

## 5. Ranking e histórico (1 min)

Pesquise um município, filtre classes e altere a ordenação. Depois mostre séries diária/mensal e a relação entre temperatura, umidade e focos. Reforce que correlação visual não prova causalidade.

## 6. Big Data (1 min)

Mostre `pipelines/spark_etl.py` ou o relatório `data/processed/etl_report.json`. Explique Extract/Transform/Load, deduplicação, junção por código IBGE, particionamento Parquet e por que Spark não fica ligado no dashboard.

## 7. IA responsável (1 min 30 s)

Mostre os pesos do índice heurístico e a regra de indisponibilidade. Na aba supervisionada:

- se não houver modelo, destaque que o sistema se recusa a fabricar métricas;
- se houver, mostre corte temporal, precisão, recall, F1 e matriz de confusão.

Explique o alvo “foco no dia seguinte” e o uso de atributos defasados para evitar vazamento.

## 8. Alertas e encerramento (1 min)

Ajuste o limite, gere alertas e mostre fatores/origem/histórico. Termine:

“O EcoRadar já funciona de ponta a ponta e foi preparado para incorporar seca, enchente e outros riscos. O próximo passo científico é calibrar a metodologia com eventos e área queimada validados.”

## Perguntas prováveis

- **É previsão de incêndio?** Não; a versão atual oferece índice heurístico, claramente rotulado. O modelo supervisionado só é exibido após validação.
- **Um foco é um incêndio?** Não; é uma detecção em um pixel de satélite.
- **Por que Open-Meteo?** Para cobertura uniforme; estações INMET não existem em todos os municípios.
- **Por que PySpark?** Para escalar o histórico, as junções e agregações; o painel operacional lê Parquet/SQLite.
- **Há dados fictícios?** Não. Falhas viram ausências e avisos.
