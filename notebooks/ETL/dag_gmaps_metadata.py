import os
import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from datetime import datetime, timedelta
from google.cloud import storage, bigquery
from google.oauth2 import service_account
from google.auth.transport.requests import Request

# CONFIGURACIÓN
GOOGLE_APPLICATION_CREDENTIALS = '/home/jose/credenciales/datawave-proyecto-final-99ef0bcb5163.json'
PROJECT_ID = 'datawave-proyecto-final'
DATASET_ID = 'gmaps_dataset'
BUCKET_NAME = 'proyecto-datawave-dspt14'
RAW_PREFIX = 'raw/gmaps_metadata/'
PROCESSED_PREFIX = 'processed/gmaps_metadata'
CLOUD_RUN_URL = 'https://transform-metadata-gmap-808937578837.us-central1.run.app'
TABLES_MAP = {
    "gmaps_sites.parquet": "gmaps_sites",
    "gmap_category.parquet": "gmap_category",
    "gmap_category_relacional.parquet": "gmap_category_relacional",
    "gmap_attribute_types.parquet": "gmap_attribute_types",
    "gmap_attribute_values.parquet": "gmap_attribute_values",
    "gmap_attribute_relacional.parquet": "gmap_attribute_relacional",
    "gmap_hours.parquet": "gmap_hours"
}

default_args = {
    'owner': 'datawave',
    'depends_on_past': False,
    'start_date': datetime(2024, 5, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
}

def get_google_openid_token(service_account_path, audience):
    credentials = service_account.IDTokenCredentials.from_service_account_file(
        service_account_path,
        target_audience=audience
    )
    credentials.refresh(Request())
    return credentials.token

def detectar_nuevos_archivos(**context):
    credentials = service_account.Credentials.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS)
    storage_client = storage.Client(credentials=credentials, project=PROJECT_ID)
    blobs = storage_client.list_blobs(BUCKET_NAME, prefix=RAW_PREFIX)
    archivos_raw = [blob.name for blob in blobs if blob.name.endswith('.parquet')]
    
    bq_client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
    query = f"SELECT archivo FROM `{PROJECT_ID}.{DATASET_ID}.gmaps_archivos_procesados`"
    archivos_procesados = [row.archivo for row in bq_client.query(query).result()]
    
    archivos_nuevos = list(set(archivos_raw) - set(archivos_procesados))
    if not archivos_nuevos:
        raise ValueError("No hay archivos nuevos por procesar")
    # Procesa solo el primero para evitar solapamientos
    archivo_a_procesar = archivos_nuevos[0]
    context['ti'].xcom_push(key='archivo_a_procesar', value=archivo_a_procesar)
    return archivo_a_procesar

def invocar_transformacion(**context):
    archivo = context['ti'].xcom_pull(key='archivo_a_procesar')
    input_path = f'gs://{BUCKET_NAME}/{archivo}'
    nombre_salida = archivo.split('/')[-1].replace('.parquet', '')  # Ejemplo: "metadata"
    output_path = f'gs://{BUCKET_NAME}/{PROCESSED_PREFIX}/{nombre_salida}'
    token = get_google_openid_token(GOOGLE_APPLICATION_CREDENTIALS, CLOUD_RUN_URL)
    payload = {"input_path": input_path, "output_path": output_path}
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(CLOUD_RUN_URL, json=payload, headers=headers)
    response.raise_for_status()
    context['ti'].xcom_push(key='output_path', value=output_path)
    return response.text

def cargar_parquet_a_bq(**context):
    output_path = context['ti'].xcom_pull(key='output_path')
    credentials = service_account.Credentials.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS)
    storage_client = storage.Client(credentials=credentials, project=PROJECT_ID)
    prefix = output_path.replace(f'gs://{BUCKET_NAME}/', '')
    blobs = storage_client.list_blobs(BUCKET_NAME, prefix=prefix)
    bq_client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
    for blob in blobs:
        filename = blob.name.split('/')[-1]
        if filename in TABLES_MAP:
            table_id = f"{PROJECT_ID}.{DATASET_ID}.{TABLES_MAP[filename]}"
            parquet_gcs_uri = f"gs://{BUCKET_NAME}/{blob.name}"
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.PARQUET,
                write_disposition="WRITE_TRUNCATE"  # Cambia a WRITE_APPEND si es incremental por particiones
            )
            load_job = bq_client.load_table_from_uri(
                parquet_gcs_uri,
                table_id,
                job_config=job_config
            )
            load_job.result()  # Espera a que termine
    return "Carga a BigQuery completada"

def registrar_archivo(**context):
    from datetime import datetime
    archivo = context['ti'].xcom_pull(key='archivo_a_procesar')
    credentials = service_account.Credentials.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS)
    bq_client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
    table_id = f"{PROJECT_ID}.{DATASET_ID}.gmaps_archivos_procesados"
    rows_to_insert = [{
        "archivo": archivo,
        "fecha_procesado": datetime.utcnow()
    }]
    errors = bq_client.insert_rows_json(table_id, rows_to_insert)
    if errors:
        raise Exception(f"Error insertando archivo procesado: {errors}")
    return "Archivo registrado"

with DAG(
    dag_id='etl_gmaps_incremental_cloudrun_to_bq',
    default_args=default_args,
    schedule='@monthly',
    catchup=False,
    max_active_runs=1,
    tags=["gmaps", "CloudRun", "ETL", "incremental"],
) as dag:

    inicio = DummyOperator(task_id='inicio')

    detectar_nuevo = PythonOperator(
        task_id='detectar_nuevo_archivo',
        python_callable=detectar_nuevos_archivos,
        provide_context=True,
    )

    transformar = PythonOperator(
        task_id='invocar_funcion_transform',
        python_callable=invocar_transformacion,
        provide_context=True,
    )

    cargar_bq = PythonOperator(
        task_id='cargar_parquet_a_bigquery',
        python_callable=cargar_parquet_a_bq,
        provide_context=True,
    )

    registrar = PythonOperator(
        task_id='registrar_archivo_procesado',
        python_callable=registrar_archivo,
        provide_context=True,
    )

    fin = DummyOperator(task_id='fin')

    inicio >> detectar_nuevo >> transformar >> cargar_bq >> registrar >> fin
