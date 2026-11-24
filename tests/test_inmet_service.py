from services.inmet_service import INMETService


def test_parse_inmet_station_file():
    content = """REGIAO:;NE;
UF:;PI;
ESTACAO:;TERESINA;
CODIGO (WMO):;A312;
LATITUDE:;-5,034;
LONGITUDE:;-42,801;
ALTITUDE:;74,36;
DATA DE FUNDACAO:;22/09/2006;
Data;Hora UTC;PRECIPITAÇÃO TOTAL, HORÁRIO (mm);TEMPERATURA DO AR - BULBO SECO, HORÁRIA (°C);UMIDADE RELATIVA DO AR, HORÁRIA (%);VENTO, VELOCIDADE HORÁRIA (m/s);
2025/01/01;0000 UTC;0,0;28,0;60;2,0;
2025/01/01;0100 UTC;1,0;27,0;65;3,0;
""".encode("latin-1")
    metadata, frame = INMETService._metadata_and_frame(content)
    assert metadata["UF"] == "PI"
    assert metadata["CODIGO (WMO)"] == "A312"
    assert len(frame) == 2
