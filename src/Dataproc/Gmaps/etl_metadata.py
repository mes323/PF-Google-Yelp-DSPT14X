import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    explode, col, trim, lower,
    udf, row_number, create_map, lit, size, collect_list, concat_ws, array_sort
)
from pyspark.sql.window import Window
from pyspark.sql.types import ArrayType, StringType
import ast
import re

spark = SparkSession.builder \
    .appName("GmapsMetadataProcessing") \
    .config("spark.jars.packages", "com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.30.0") \
    .getOrCreate()

def cargar_datos_parquet(spark, path_parquet: str):
    df = spark.read.parquet(path_parquet)
    return df.drop("relative_results", "state")

def convertir_a_lista_udf(col_value):
    if col_value is None:
        return []
    if isinstance(col_value, (list, tuple)):
        return list(col_value)
    if isinstance(col_value, str):
        try:
            valor = ast.literal_eval(col_value)
            return valor if isinstance(valor, list) else [valor]
        except Exception:
            return [col_value]
    return [str(col_value)]

convertir_a_lista_pyspark = udf(convertir_a_lista_udf, ArrayType(StringType()))

def crear_tablas_categorias_pyspark(df):
    df_temp = df.select("gmap_id", convertir_a_lista_pyspark(col("category")).alias("category"))
    df_temp = df_temp.withColumn("category", explode("category"))
    df_temp = df_temp.withColumn("category", trim(col("category")))
    df_temp = df_temp.filter(~(lower(col("category")) == "nan"))
    df_temp = df_temp.filter(col("category") != "")

    df_categories = df_temp.select("category").distinct().withColumnRenamed("category", "category_name")
    window_spec = Window.orderBy("category_name")
    df_categories = df_categories.withColumn("category_id", row_number().over(window_spec))

    df_gmap_category = df_temp.join(
        df_categories,
        df_temp["category"] == df_categories["category_name"],
        "inner"
    ).select("gmap_id", "category_id")

    return df_categories, df_gmap_category

def procesar_misc_pyspark(df):
    misc_cols = df.schema["MISC"].dataType.names
    exprs = []
    for c in misc_cols:
        exprs.append(lit(c))
        exprs.append(col(f"MISC.{c}"))

    df = df.withColumn("MISC_map", create_map(*exprs))
    df_exp = df.select("gmap_id", explode("MISC_map").alias("attribute_type", "attribute_values"))
    df_exp = df_exp.filter((col("attribute_values").isNotNull()) & (size(col("attribute_values")) > 0))
    df_exp = df_exp.withColumn("attribute_value", explode("attribute_values"))

    window_type = Window.orderBy("attribute_type")
    df_attribute_types = df_exp.select("attribute_type").distinct() \
        .withColumn("attribute_type_id", row_number().over(window_type))

    window_value = Window.orderBy("attribute_value")
    df_attribute_values = df_exp.select("attribute_value").distinct() \
        .withColumn("attribute_value_id", row_number().over(window_value))

    df_relacional = df_exp \
        .join(df_attribute_types, "attribute_type", "inner") \
        .join(df_attribute_values, "attribute_value", "inner") \
        .select("gmap_id", "attribute_type_id", "attribute_value_id")

    return df_attribute_types, df_attribute_values, df_relacional

def parsear_horarios_pyspark(row):
    hours = row["hours"]
    gmap_id = row["gmap_id"]
    resultado = []

    if not hours:
        return resultado

    for val in hours:
        if not val or len(val) != 2:
            continue
        day, time_str = val[0], val[1].strip().lower()
        if time_str == 'closed':
            continue
        if time_str == 'open 24 hours':
            resultado.append((gmap_id, day, '00:00', '23:59'))
            continue

        match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)[–-](\d{1,2})(?::(\d{2}))?\s*(am|pm)', time_str)
        if match:
            h1, m1, p1, h2, m2, p2 = match.groups()
            m1 = m1 or '00'
            m2 = m2 or '00'
            open_hour = (int(h1) % 12) + (12 if p1 == 'pm' else 0)
            close_hour = (int(h2) % 12) + (12 if p2 == 'pm' else 0)
            resultado.append((gmap_id, day, f"{open_hour:02d}:{m1}", f"{close_hour:02d}:{m2}"))

    return resultado

def agrupar_horarios(spark, df):
    rdd = df.select("gmap_id", "hours").rdd.flatMap(parsear_horarios_pyspark)
    df_horarios = spark.createDataFrame(rdd, ["gmap_id", "day", "open_time", "close_time"])

    df_agrupado = df_horarios.groupBy("gmap_id", "open_time", "close_time") \
        .agg(
            concat_ws(", ", array_sort(collect_list("day"))).alias("days")
        ) \
        .select("gmap_id", "days", "open_time", "close_time") \
        .orderBy("gmap_id", "open_time")

    return df_agrupado

if __name__ == "__main__":
    input_path = sys.argv[1]  # input_path desde parámetro

    project = "datawave-proyecto-final"
    dataset = "gmaps_dataset"

    df = cargar_datos_parquet(spark, input_path)

    # Categorías
    df_categories, df_gmap_category = crear_tablas_categorias_pyspark(df)
    df_categories.write.format("bigquery") \
        .option("table", f"{project}.{dataset}.gmap_category") \
        .option("temporaryGcsBucket", "dataproc-temp-us-central1-808937578837-ynvkdv8p") \
        .mode("overwrite") \
        .save()
    df_gmap_category.write.format("bigquery") \
        .option("table", f"{project}.{dataset}.gmap_category_relacional") \
        .option("temporaryGcsBucket", "dataproc-temp-us-central1-808937578837-ynvkdv8p") \
        .mode("overwrite") \
        .save()
    df = df.drop("category")

    # MISC
    df_attribute_types, df_attribute_values, df_relacional = procesar_misc_pyspark(df)
    df_attribute_types.write.format("bigquery") \
        .option("table", f"{project}.{dataset}.gmap_attribute_types") \
        .option("temporaryGcsBucket", "dataproc-temp-us-central1-808937578837-ynvkdv8p") \
        .mode("overwrite") \
        .save()
    df_attribute_values.write.format("bigquery") \
        .option("table", f"{project}.{dataset}.gmap_attribute_values") \
        .option("temporaryGcsBucket", "dataproc-temp-us-central1-808937578837-ynvkdv8p") \
        .mode("overwrite") \
        .save()
    df_relacional.write.format("bigquery") \
        .option("table", f"{project}.{dataset}.gmap_attribute_relacional") \
        .option("temporaryGcsBucket", "dataproc-temp-us-central1-808937578837-ynvkdv8p") \
        .mode("overwrite") \
        .save()
    df = df.drop("MISC")

    # Horarios con agrupación
    df_hours = agrupar_horarios(spark, df)
    df_hours.write.format("bigquery") \
        .option("table", f"{project}.{dataset}.gmap_hours") \
        .option("temporaryGcsBucket", "dataproc-temp-us-central1-808937578837-ynvkdv8p") \
        .mode("overwrite") \
        .save()
    df = df.drop("hours")

    # Sitios Gmap
    df.write.format("bigquery") \
        .option("table", f"{project}.{dataset}.gmap_sites") \
        .option("temporaryGcsBucket", "dataproc-temp-us-central1-808937578837-ynvkdv8p") \
        .mode("overwrite") \
        .save()

    spark.stop()
