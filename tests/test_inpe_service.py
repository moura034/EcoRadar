from services.inpe_service import INPEService


def test_parse_current_inpe_schema_and_filter_piaui():
    content = """id,lat,lon,data_hora_gmt,satelite,municipio,estado,pais,municipio_id,estado_id,pais_id,numero_dias_sem_chuva,precipitacao,risco_fogo,bioma,frp
pi-1,-5.091,-42.803,2026-11-16 10:00:00,AQUA_M-T,TERESINA,PIAUÍ,Brasil,2211001,22,33,10,0.0,0.8,Caatinga,15.2
ce-1,-3.72,-38.54,2026-11-16 10:10:00,AQUA_M-T,FORTALEZA,CEARÁ,Brasil,2304400,23,33,2,1.0,0.2,Caatinga,4.2
""".encode()
    result = INPEService.parse_csv(content)
    assert len(result) == 1
    assert result.iloc[0]["id"] == "pi-1"
    assert result.iloc[0]["municipality_id"] == 2211001
    assert result.iloc[0]["source"] == "INPE Programa Queimadas"


def test_parse_generates_stable_id_when_source_has_none():
    content = """lat,lon,data_hora_gmt,satelite,municipio,estado,municipio_id,estado_id
-5.0,-42.0,2026-11-16 10:00:00,AQUA_M-T,TERESINA,PIAUÍ,2211001,22
""".encode()
    first = INPEService.parse_csv(content)
    second = INPEService.parse_csv(content)
    assert first.iloc[0]["id"] == second.iloc[0]["id"]
