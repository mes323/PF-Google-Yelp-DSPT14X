from pyspark.sql import SparkSession
import sys

# Rutas desde argumentos
input_path = sys.argv[1]     # ej. gs://.../gmaps_metadata/
output_path = sys.argv[2]    # ej. gs://.../processed/gmaps/parquets/

# Inicializar Spark
spark = SparkSession.builder.appName("JSON_to_Parquet").getOrCreate()

# Leer todos los JSON en la carpeta
df = spark.read.json(input_path + "*.json")

# Escribir como Parquet
df.write.mode("overwrite").parquet(output_path)

spark.stop()