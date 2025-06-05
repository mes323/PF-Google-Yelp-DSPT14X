import os
import pandas as pd
from google.cloud import storage

# Configuración rutas
local_json_path = r"C:\Users\jano_\Documents\Proyecto Final Grupal\yelp\review.json"
gcs_bucket_name = "proyecto-datawave-dspt14"
gcs_folder = "raw/Yelp/review/"

# Tamaño de chunk para pandas (200,000 filas)
chunksize = 200000  

# Cliente GCS
storage_client = storage.Client()
bucket = storage_client.bucket(gcs_bucket_name)

def upload_to_gcs(local_file_path, bucket, gcs_path):
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_file_path)
    print(f"Archivo subido a gs://{bucket.name}/{gcs_path}")

def main():
    chunk_num = 0

    for chunk in pd.read_json(local_json_path, lines=True, chunksize=chunksize):
        parquet_local_path = f"temp_reviews_chunk_{chunk_num}.parquet"
        chunk.to_parquet(parquet_local_path, index=False)

        gcs_path = os.path.join(gcs_folder, f"reviews_chunk_{chunk_num}.parquet")
        upload_to_gcs(parquet_local_path, bucket, gcs_path)

        os.remove(parquet_local_path)

        chunk_num += 1

if __name__ == "__main__":
    main()