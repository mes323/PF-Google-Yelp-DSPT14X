import os
import requests
import pandas as pd
from google.cloud import storage
import logging

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\Pc\Documents\datawave-proyecto-final-99ef0bcb5163.json"

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Parámetros de la API y GCS
API_KEY = "17e47fbc1d67e71f5a4d26351e5bd1dc5d08ebd8"
pop_url = "https://api.census.gov/data/2020/dec/pl"
params = {
    "get": "NAME,P1_001N",  # NAME = state name, P1_001N = total population
    "for": "state:*",
    "key": API_KEY
}

GCS_BUCKET = os.environ.get("GCS_BUCKET", "proyecto-datawave-dspt14")
GCS_PATH = os.environ.get("GCS_PATH", "raw/census/")

# Diccionario de áreas
land_area_sq_mi = {
    'Alabama': 50645, 'Alaska': 571052, 'Arizona': 113655, 'Arkansas': 51993,
    'California': 155859, 'Colorado': 103638, 'Connecticut': 4842, 'Delaware': 1949,
    'Florida': 53654, 'Georgia': 57717, 'Hawaii': 6423, 'Idaho': 82645,
    'Illinois': 55513, 'Indiana': 35825, 'Iowa': 55853, 'Kansas': 81759,
    'Kentucky': 39485, 'Louisiana': 43216, 'Maine': 30845, 'Maryland': 9711,
    'Massachusetts': 7801, 'Michigan': 56610, 'Minnesota': 79631, 'Mississippi': 46924,
    'Missouri': 68746, 'Montana': 145550, 'Nebraska': 76814, 'Nevada': 109860,
    'New Hampshire': 8953, 'New Jersey': 7354, 'New Mexico': 121312, 'New York': 47123,
    'North Carolina': 48624, 'North Dakota': 68994, 'Ohio': 40858, 'Oklahoma': 68596,
    'Oregon': 95996, 'Pennsylvania': 44742, 'Rhode Island': 1034, 'South Carolina': 30064,
    'South Dakota': 75807, 'Tennessee': 41233, 'Texas': 261270, 'Utah': 82596,
    'Vermont': 9217, 'Virginia': 39482, 'Washington': 66455, 'West Virginia': 24041,
    'Wisconsin': 54167, 'Wyoming': 97088, 'District of Columbia': 61
}

def get_census_data():
    response = requests.get(pop_url, params=params)
    try:
        data = response.json()
    except ValueError as e:
        logging.error("Error decoding JSON: %s", e)
        return None
    columns = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=columns)
    df["P1_001N"] = df["P1_001N"].astype(int)
    df["land_area"] = df["NAME"].map(land_area_sq_mi)
    df["density"] = df["P1_001N"] / df["land_area"]
    return df

def save_files(df, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    csv_path = os.path.join(dest_dir, "us_census_population_density.csv")
    parquet_path = os.path.join(dest_dir, "us_census_population_density.parquet")
    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)
    return csv_path, parquet_path

def upload_to_gcs(files, bucket_name, gcs_path):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    for file_path in files:
        file_name = os.path.basename(file_path)
        blob_path = os.path.join(gcs_path, file_name).replace("\\", "/")
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(file_path)
        logging.info(f"Archivo subido a GCS: gs://{bucket_name}/{blob_path}")

if __name__ == "__main__":
    # 1. Descarga y procesamiento
    df = get_census_data()
    if df is None:
        logging.error("No se pudo obtener datos del censo.")
        exit(1)
    logging.info("Datos de censo descargados y procesados correctamente.")
    # 2. Guardar archivos
    local_dir = "./census_data_tmp"
    csv_file, parquet_file = save_files(df, local_dir)
    logging.info(f"Archivos guardados localmente: {csv_file}, {parquet_file}")
    # 3. Subir a GCS
    upload_to_gcs([csv_file, parquet_file], GCS_BUCKET, GCS_PATH)
    logging.info("Proceso finalizado exitosamente.")
