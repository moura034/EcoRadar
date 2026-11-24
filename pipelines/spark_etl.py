"""ETL batch com PySpark para histórico de focos, clima e municípios.

O Spark é iniciado apenas por este comando e encerrado ao final. O dashboard lê
Parquet/SQLite e, portanto, não mantém JVM ativa durante a navegação.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from config.settings import settings
from database.db import EcoRadarDatabase
from services.ibge_service import IBGEService
from services.inpe_service import INPEService
from services.weather_service import WeatherService


def _spark_session():
    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise RuntimeError(
            "PySpark não está instalado. Execute `pip install -r requirements.txt` e configure Java 17."
        ) from exc
    return (
        SparkSession.builder.appName("EcoRadar-ETL")
        .master("local[2]")
        .config("spark.driver.memory", "2g")
        .config("spark.executor.memory", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.default.parallelism", "4")
        .config("spark.sql.session.timeZone", settings.timezone)
        .getOrCreate()
    )


def run_etl(start: date, end: date, output_dir: Path | None = None) -> dict:
    if end < start:
        raise ValueError("A data final deve ser igual ou posterior à inicial.")
    output_dir = output_dir or settings.processed_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    ibge_result = IBGEService().fetch_municipalities()
    if ibge_result.data.empty:
        raise RuntimeError("Não foi possível extrair municípios do IBGE: " + "; ".join(ibge_result.issues))
    fire_result = INPEService().fetch_daily(start, end, persist_raw=True)
    weather_result = WeatherService().fetch_daily(ibge_result.data, start, end)
    if weather_result.data.empty:
        raise RuntimeError("Não foi possível extrair meteorologia: " + "; ".join(weather_result.issues))

    database = EcoRadarDatabase()
    database.upsert_municipalities(ibge_result.data)
    database.upsert_fire_spots(fire_result.data)
    database.upsert_weather(weather_result.data)

    spark = _spark_session()
    spark.sparkContext.setLogLevel("WARN")
    try:
        from pyspark.sql import functions as F
        from pyspark.sql.types import (
            DoubleType,
            IntegerType,
            LongType,
            StringType,
            StructField,
            StructType,
            TimestampType,
        )

        municipality_pdf = ibge_result.data[
            ["ibge_code", "name", "latitude", "longitude"]
        ].rename(columns={"ibge_code": "municipality_id", "name": "municipality"})
        municipality_sdf = spark.createDataFrame(municipality_pdf)

        weather_pdf = weather_result.data.copy()
        weather_pdf["observed_date"] = pd.to_datetime(weather_pdf["observed_date"]).dt.date
        weather_sdf = spark.createDataFrame(weather_pdf)

        fire_schema = StructType(
            [
                StructField("id", StringType(), False),
                StructField("latitude", DoubleType(), True),
                StructField("longitude", DoubleType(), True),
                StructField("observed_at", TimestampType(), True),
                StructField("satellite", StringType(), True),
                StructField("municipality", StringType(), True),
                StructField("state", StringType(), True),
                StructField("municipality_id", LongType(), True),
                StructField("state_id", IntegerType(), True),
                StructField("days_without_rain", DoubleType(), True),
                StructField("precipitation_mm", DoubleType(), True),
                StructField("inpe_fire_risk", DoubleType(), True),
                StructField("biome", StringType(), True),
                StructField("frp", DoubleType(), True),
                StructField("source", StringType(), True),
            ]
        )
        fire_pdf = fire_result.data.copy()
        for column in ("municipality_id", "state_id"):
            fire_pdf[column] = pd.to_numeric(fire_pdf[column], errors="coerce").astype("Int64")
        fire_pdf = fire_pdf.where(pd.notna(fire_pdf), None)
        fire_sdf = spark.createDataFrame(fire_pdf.to_dict("records"), schema=fire_schema)
        fire_sdf = (
            fire_sdf.filter(F.col("state_id") == settings.state_code)
            .filter(F.col("observed_at").isNotNull())
            .dropDuplicates(["id"])
            .withColumn("observed_date", F.to_date("observed_at"))
        )

        fire_daily = fire_sdf.groupBy("municipality_id", "observed_date").agg(
            F.countDistinct("id").alias("fire_count"),
            F.avg("frp").alias("mean_frp"),
            F.countDistinct("satellite").alias("satellite_count"),
        )
        weather_daily = weather_sdf.groupBy("municipality_id", "observed_date").agg(
            F.avg("temperature_c").alias("temperature_c"),
            F.avg("humidity_pct").alias("humidity_pct"),
            F.avg("wind_speed_kmh").alias("wind_speed_kmh"),
            F.avg("wind_direction_deg").alias("wind_direction_deg"),
            F.sum("precipitation_mm").alias("precipitation_mm"),
            F.first("source", ignorenulls=True).alias("weather_source"),
        )
        integrated = (
            weather_daily.join(fire_daily, ["municipality_id", "observed_date"], "left")
            .join(municipality_sdf, "municipality_id", "left")
            .fillna({"fire_count": 0, "satellite_count": 0})
            .select(
                "municipality_id", "municipality", "observed_date", "latitude", "longitude",
                "temperature_c", "humidity_pct", "wind_speed_kmh", "wind_direction_deg",
                "precipitation_mm", "fire_count", "mean_frp", "satellite_count", "weather_source",
            )
        )

        fire_path = output_dir / "fire_spots.parquet"
        daily_path = output_dir / "municipality_daily.parquet"
        fire_sdf.write.mode("overwrite").partitionBy("observed_date").parquet(str(fire_path))
        integrated.write.mode("overwrite").partitionBy("observed_date").parquet(str(daily_path))

        summary = {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "municipalities": municipality_sdf.count(),
            "fire_spots": fire_sdf.count(),
            "municipality_daily_rows": integrated.count(),
            "fire_parquet": str(fire_path),
            "integrated_parquet": str(daily_path),
            "issues": ibge_result.issues + fire_result.issues + weather_result.issues,
        }
        (output_dir / "etl_report.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return summary
    finally:
        spark.stop()


def main() -> None:
    today = date.today()
    parser = argparse.ArgumentParser(description="ETL PySpark do EcoRadar.")
    parser.add_argument("--start", type=date.fromisoformat, default=today - timedelta(days=6))
    parser.add_argument("--end", type=date.fromisoformat, default=today)
    parser.add_argument("--output", type=Path, default=settings.processed_dir)
    args = parser.parse_args()
    print(json.dumps(run_etl(args.start, args.end, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
