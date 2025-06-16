from pyspark.sql import SparkSession

def main():
    spark = SparkSession.builder.appName("ParquetToBigQuery").getOrCreate()

    input_path = "gs://proyecto-datawave-dspt14/raw/Yelp/review/*.parquet"

    df = spark.read.parquet(input_path)

    bigquery_table = "datawave-proyecto-final.yelp_dataset.review"

    df.write.format("bigquery") \
        .option("writeMethod", "direct") \
        .mode("append") \
        .save(bigquery_table)

    spark.stop()

if __name__ == "__main__":
    main()
