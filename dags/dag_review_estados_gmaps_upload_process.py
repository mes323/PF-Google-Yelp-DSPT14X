
import os
import glob
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from datetime import datetime
import requests
from google.cloud import storage

# CONFIG
BUCKET_NAME = 'proyecto-datawave-dspt14'
LOCAL_FOLDER = '/home/airflow/gcs/data/review_estados_bulk'  # Montado desde D:\tmp\review_estados_bulk
GCS_TARGET_FOLDER = 'raw/review_estados/'
CLOUD_RUN_URL = 'https://review-gmaps-808937578837.us-central1.run.app'
BQ_OUTPUT_TABLE = 'datawave-proyecto-final.gmaps_dataset.review_estados'
TELEGRAM_TOKEN = '7873627738:AAHUP9zFmZOKRLFyCpOeHd_5W2L5Ye17HfQ'
TELEGRAM_CHAT_ID = '1027595159'

default_args = {
    'owner': 'data_engineer',
    'start_date': datetime(2025, 6, 16),
    'retries': 1,
}

def upload_files_to_gcs():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    files = glob.glob(os.path.join(LOCAL_FOLDER, '*.json'))

    for file_path in files:
        file_name = os.path.basename(file_path)
        blob_path = f"{GCS_TARGET_FOLDER}{file_name}"
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(file_path)
        print(f"Subido: {file_path} → gs://{BUCKET_NAME}/{blob_path}")

def call_cloud_run_for_each_file():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blobs = bucket.list_blobs(prefix=GCS_TARGET_FOLDER)

    for blob in blobs:
        if not blob.name.endswith('.json'):
            continue

        payload = {
            "input_path": blob.name,
            "bucket": BUCKET_NAME,
            "output_table": BQ_OUTPUT_TABLE
        }
        response = requests.post(CLOUD_RUN_URL, json=payload)
        if response.status_code != 200:
            raise Exception(f"Error al procesar {blob.name}: {response.text}")
        else:
            print(f"Procesado correctamente: {blob.name}")

def enviar_telegram_mensaje():
    mensaje = "✅ DAG Finalizado: dag_review_estados_gmaps_upload_process"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': mensaje}
    response = requests.post(url, data=payload)
    if response.status_code != 200:
        raise Exception(f"Error al enviar mensaje de Telegram: {response.text}")

with DAG(
    dag_id='dag_review_estados_gmaps_upload_process',
    default_args=default_args,
    schedule_interval=None,
    catchup=False,
    tags=['gmaps', 'review_estados', 'cloud_run', 'bigquery']
) as dag:

    start = EmptyOperator(task_id='start')

    upload_task = PythonOperator(
        task_id='upload_reviews_to_gcs',
        python_callable=upload_files_to_gcs
    )

    process_task = PythonOperator(
        task_id='process_reviews_with_cloud_run',
        python_callable=call_cloud_run_for_each_file
    )

    notify_task = PythonOperator(
        task_id='send_telegram_notification',
        python_callable=enviar_telegram_mensaje
    )

    end = EmptyOperator(task_id='end')

    start >> upload_task >> process_task >> notify_task >> end
