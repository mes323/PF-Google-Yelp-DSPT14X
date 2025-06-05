from pyspark.sql import SparkSession
import sys

input_parquet_folder = sys.argv[1]  
output_parquet_path = sys.argv[2]   

spark = SparkSession.builder.appName("ConcatenarParquets").getOrCreate()

# Leer todos los archivos parquet en la carpeta de entrada
df = spark.read.parquet(input_parquet_folder + "/*.parquet")

# Escribir el parquet concatenado en la ruta de salida
df.write.mode("overwrite").parquet(output_parquet_path)

spark.stop()

print(f"Parquets concatenados y guardados en {output_parquet_path}")
