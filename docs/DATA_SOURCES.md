# Fontes de dados, contratos e limitações

## INPE — Programa Queimadas

- Portal oficial: <https://terrabrasilis.dpi.inpe.br/queimadas/portal/>
- Dados abertos: <https://terrabrasilis.dpi.inpe.br/queimadas/portal/pages/secao_downloads/dados-abertos/>
- CSV diário Brasil: <https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil/>
- ZIP anual de satélite de referência/PI: <https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/EstadosBr_sat_ref/PI/>

O sistema usa o padrão de arquivo diário `focos_diario_br_AAAAMMDD.csv` e filtra `estado_id = 22`. O schema validado em novembro de 2026 contém identificador, latitude, longitude, data/hora UTC, satélite, município, código IBGE, estado, dias sem chuva, precipitação, risco INPE, bioma e FRP.

O arquivo diário reúne satélites diferentes. Uma linha é uma detecção, não prova de incêndio, área queimada ou evento único. Para séries comparáveis de longo prazo, o ZIP anual de satélite de referência é preferível. O importador `INPEService.import_file` aceita CSV e ZIP.

## IBGE

- Localidades: <https://servicodados.ibge.gov.br/api/v1/localidades/estados/22/municipios?orderBy=nome>
- Malhas v3: <https://servicodados.ibge.gov.br/api/v3/malhas/estados/22?formato=application/vnd.geo%2Bjson&qualidade=minima&intrarregiao=municipio>

Ambas as respostas são cruzadas por código IBGE. O EcoRadar verifica se a malha contém 224 feições e calcula um centroide para solicitar meteorologia por coordenada. A qualidade mínima reduz o tamanho para uso em dashboard; não é indicada para medições cadastrais.

## INMET

- Dados históricos anuais: <https://portal.inmet.gov.br/dadoshistoricos>
- Catálogo de estações automáticas: <https://apitempo.inmet.gov.br/estacoes/T>
- BDMEP: <https://bdmep.inmet.gov.br/>

Os ZIPs anuais possuem dados horários por estação e podem ser grandes. O comando `python -m services.inmet_service --year ANO` filtra arquivos do Piauí, converte os marcadores oficiais de ausência em nulo e agrega por estação/dia. O INMET informa que dados automáticos são brutos e podem não passar por consistência. Como não há estação em cada município, esses dados não são propagados artificialmente para os 224 municípios.

## Open-Meteo

- Forecast API: <https://open-meteo.com/en/docs>
- Historical Weather API: <https://open-meteo.com/en/docs/historical-weather-api>

Variáveis diárias utilizadas: temperatura média a 2 m, umidade relativa média a 2 m, vento máximo a 10 m, direção dominante e precipitação acumulada. Para datas com atraso superior a cinco dias é usado o endpoint histórico; recortes recentes usam o endpoint de previsão/histórico recente. A origem exata é persistida no campo `source`.

Open-Meteo produz valores em células de grade/reanálise. O valor representa a célula próxima ao centroide municipal, não uma observação pontual dentro de todos os municípios.

## Comportamento diante de falhas

- HTTP possui repetição limitada para erros transitórios e `timeout` configurável;
- arquivo INPE ausente gera aviso com a data;
- lotes Open-Meteo podem falhar isoladamente sem apagar lotes válidos;
- retorno IBGE diferente de 224 gera advertência;
- dados locais legítimos permanecem disponíveis;
- nenhum serviço gera observações substitutas, números aleatórios ou métricas fictícias.
