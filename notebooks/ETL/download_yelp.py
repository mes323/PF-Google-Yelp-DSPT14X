import os
import subprocess
import logging
from google.cloud import storage

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\Pc\Documents\datawave-proyecto-final-99ef0bcb5163.json"


# === CONFIGURACIÓN GENERAL ===

FOLDER_URL = "https://drive.google.com/drive/folders/1TI-SsMnZsNP6t930olEEWbBQdo_yuIZF"
DEST_DIR = "/tmp/yelp_bulk"

# Intenta leer el bucket y ruta de destino desde variables de entorno (Composer recomienda esto)
GCS_BUCKET = os.environ.get("GCS_BUCKET", "proyecto-datawave-dspt14")
GCS_PATH = os.environ.get("GCS_PATH", "raw/users/")

# Si prefieres, puedes descomentar para leer desde Airflow Variables:
# from airflow.models import Variable
# GCS_BUCKET = Variable.get("GCS_BUCKET", default_var="tu-bucket-gcs")
# GCS_PATH = Variable.get("GCS_PATH", default_var="raw/gmaps_metadata/")

os.makedirs(DEST_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def download_with_gdown(folder_url, dest_dir):
    """
    Descarga todos los archivos de una carpeta pública de Google Drive usando gdown.
    """
    try:
        cmd = f"gdown --folder --continue --output {dest_dir} {folder_url}"
        logging.info(f"Descargando archivos desde {folder_url} a {dest_dir} ...")
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        logging.info("Descarga completada.")
        logging.debug(result.stdout)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error al descargar los archivos: {e.stderr}")
        raise

def upload_files_to_gcs(local_dir, bucket_name, gcs_path):
    """
    Sube todos los archivos de un directorio local a una ruta en un bucket de GCS.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    archivos_subidos = []
    for file_name in os.listdir(local_dir):
        local_file = os.path.join(local_dir, file_name)
        if os.path.isfile(local_file):
            blob_path = os.path.join(gcs_path, file_name)
            blob = bucket.blob(blob_path)
            blob.upload_from_filename(local_file)
            archivos_subidos.append(blob_path)
            logging.info(f"Archivo subido a GCS: gs://{bucket_name}/{blob_path}")
    return archivos_subidos

if __name__ == "__main__":
    # Paso 1: Descargar archivos
    download_with_gdown(FOLDER_URL, DEST_DIR)
    archivos_descargados = os.listdir(DEST_DIR)
    logging.info(f"Archivos descargados: {archivos_descargados}")

    # Paso 2: Subir a GCS
    logging.info(f"Subiendo archivos a GCS bucket {GCS_BUCKET} en ruta {GCS_PATH} ...")
    upload_files_to_gcs(DEST_DIR, GCS_BUCKET, GCS_PATH)
    logging.info("Subida a GCS completada.")