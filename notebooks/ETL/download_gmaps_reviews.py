import os
import subprocess
import logging
import re
from google.cloud import storage

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\Pc\Documents\datawave-proyecto-final-99ef0bcb5163.json"

# === CONFIGURACIÓN GENERAL ===

FOLDER_URL = "https://drive.google.com/drive/folders/19QNXr_BcqekFNFNYlKd0kcTXJ0Zg7lI6"
DEST_DIR = "d:/tmp/review_estados_bulk"  # Usa tu ruta local preferida (Windows usa 'd:/tmp' en vez de '/tmp')
FAILED_FILE = os.path.join(DEST_DIR, "failed_downloads.txt")

GCS_BUCKET = os.environ.get("GCS_BUCKET", "proyecto-datawave-dspt14")
GCS_PATH = os.environ.get("GCS_PATH", "raw/reviews/")

os.makedirs(DEST_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def download_with_gdown(folder_url, dest_dir):
    """
    Descarga todos los archivos de una carpeta pública de Google Drive usando gdown.
    Intenta descargar todos los archivos posibles y detecta los que fallan por cuota.
    """
    try:
        cmd = f"gdown --folder --continue --remaining-ok --output {dest_dir} {folder_url}"
        logging.info(f"Descargando archivos desde {folder_url} a {dest_dir} ...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = result.stdout + result.stderr
        logging.info("Descarga terminada. Analizando resultados...")
        # Detecta archivos fallidos
        failed_files = re.findall(
            r"You may still be able to access the file from the browser:\s+https://drive\.google\.com/uc\?id=([^\s]+)",
            output
        )
        if failed_files:
            logging.warning(f"Archivos con cuota excedida o fallo de descarga: {failed_files}")
            # Guarda en archivo de texto para reintentar después
            with open(FAILED_FILE, "w") as f:
                for fileid in failed_files:
                    f.write(f"{fileid}\n")
        else:
            logging.info("No se detectaron archivos fallidos por cuota excedida.")
        return failed_files
    except Exception as e:
        logging.error(f"Error al descargar los archivos: {str(e)}")
        return []

def list_downloaded_files(dest_dir):
    """
    Lista los archivos realmente descargados.
    """
    archivos = []
    for root, dirs, files in os.walk(dest_dir):
        for file in files:
            if file.endswith('.json'):
                archivos.append(os.path.join(root, file))
    return archivos

def upload_files_to_gcs(file_list, bucket_name, gcs_path):
    """
    Sube los archivos especificados a GCS.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    archivos_subidos = []
    for local_file in file_list:
        file_name = os.path.relpath(local_file, start=DEST_DIR).replace("\\", "/")
        blob_path = os.path.join(gcs_path, file_name).replace("\\", "/")
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(local_file)
        archivos_subidos.append(blob_path)
        logging.info(f"Archivo subido a GCS: gs://{bucket_name}/{blob_path}")
    return archivos_subidos

def retry_failed_downloads(dest_dir):
    """
    Reintenta descargar archivos fallidos a partir de la lista 'failed_downloads.txt'.
    """
    if not os.path.exists(FAILED_FILE):
        logging.info("No hay archivos fallidos para reintentar.")
        return
    with open(FAILED_FILE, "r") as f:
        file_ids = [line.strip() for line in f if line.strip()]
    if not file_ids:
        logging.info("No hay archivos fallidos para reintentar.")
        return

    still_failed = []
    for fileid in file_ids:
        url = f"https://drive.google.com/uc?id={fileid}"
        output_file = os.path.join(dest_dir, f"{fileid}.json")
        try:
            cmd = f"gdown {url} -O {output_file}"
            logging.info(f"Reintentando descarga de {fileid} ...")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(output_file):
                logging.info(f"Descarga exitosa: {output_file}")
            else:
                logging.warning(f"Descarga fallida para {fileid}")
                still_failed.append(fileid)
        except Exception as e:
            logging.error(f"Error al reintentar descarga de {fileid}: {str(e)}")
            still_failed.append(fileid)
    # Actualiza la lista de fallidos
    with open(FAILED_FILE, "w") as f:
        for fileid in still_failed:
            f.write(f"{fileid}\n")
    if still_failed:
        logging.warning(f"Aún fallan estos archivos: {still_failed}")
    else:
        logging.info("¡Todos los archivos fallidos se descargaron exitosamente!")

if __name__ == "__main__":
    # Paso 1: Descargar archivos
    failed_files = download_with_gdown(FOLDER_URL, DEST_DIR)
    archivos_descargados = list_downloaded_files(DEST_DIR)
    logging.info(f"Total archivos descargados correctamente: {len(archivos_descargados)}")
    logging.info(f"Archivos descargados:\n" + "\n".join(archivos_descargados))
    if failed_files:
        logging.warning(f"Total archivos fallidos: {len(failed_files)}")
        logging.warning(f"IDs de archivos fallidos: {failed_files}")

    # Paso 2: Subir los archivos descargados a GCS
    logging.info(f"Subiendo archivos a GCS bucket {GCS_BUCKET} en ruta {GCS_PATH} ...")
    upload_files_to_gcs(archivos_descargados, GCS_BUCKET, GCS_PATH)
    logging.info("Subida a GCS completada.")

    # Paso 3: (Opcional) Reintentar descargas fallidas
    # Puedes llamar a esta función cuando quieras reintentar los archivos fallidos:
    # retry_failed_downloads(DEST_DIR)