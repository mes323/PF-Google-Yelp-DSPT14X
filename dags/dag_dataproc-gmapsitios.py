from airflow import DAG
from airflow.providers.google.cloud.operators.dataproc import DataprocSubmitJobOperator
from airflow.providers.google.cloud.sensors.gcs import GCSObjectExistenceSensor
from airflow.utils.dates import days_ago

PROJECT_ID = 'datawave-proyecto-final'
REGION = 'us-central1'
CLUSTER_NAME = 'cluster-8fb4'

# Rutas en GCS
gcs_json_path = 'gs://proyecto-datawave-dspt14/raw/gmaps_metadata/'
gcs_parquets_output_path = 'gs://proyecto-datawave-dspt14/processed/gmaps/parquets/'
gcs_parquet_final_path = 'gs://proyecto-datawave-dspt14/processed/gmaps/df_placesGmaps.parquet/'

# Rutas a los scripts en GCS
script_json_to_parquet = 'gs://proyecto-datawave-dspt14/scr/dataproc/conversor_jsontoparquet.py'
script_concat_to_gcs = 'gs://proyecto-datawave-dspt14/scr/dataproc/concatenar_parquet.py'
script_etl_metadata = 'gs://proyecto-datawave-dspt14/scr/dataproc/etl_metadata.py'

default_args = {
    'start_date': days_ago(1),
}

with DAG(
    dag_id='etl_gmaps_completo_composer',
    default_args=default_args,
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    tags=['etl', 'gmaps', 'dataproc'],
) as dag:

    t1_convert_json = DataprocSubmitJobOperator(
        task_id='convertir_json_a_parquet',
        job={
            "reference": {"project_id": PROJECT_ID},
            "placement": {"cluster_name": CLUSTER_NAME},
            "pyspark_job": {
                "main_python_file_uri": script_json_to_parquet,
                "args": [gcs_json_path, gcs_parquets_output_path],
            },
        },
        region=REGION,
        project_id=PROJECT_ID,
    )

    t2_concatenar = DataprocSubmitJobOperator(
        task_id='concatenar_parquet_y_subir_gcs',
        job={
            "reference": {"project_id": PROJECT_ID},
            "placement": {"cluster_name": CLUSTER_NAME},
            "pyspark_job": {
                "main_python_file_uri": script_concat_to_gcs,
                "args": [gcs_parquets_output_path, gcs_parquet_final_path],
            },
        },
        region=REGION,
        project_id=PROJECT_ID,
    )

    t3_sensor_gcs = GCSObjectExistenceSensor(
        task_id='esperar_parquet_en_gcs',
        bucket='proyecto-datawave-dspt14',
        object='processed/gmaps/df_placesGmaps.parquet/_SUCCESS',
        timeout=600,
        poke_interval=30,
        mode='reschedule',
    )

    t4_etl_final = DataprocSubmitJobOperator(
        task_id='submit_gmaps_etl',
        job={
            "reference": {"project_id": PROJECT_ID},
            "placement": {"cluster_name": CLUSTER_NAME},
            "pyspark_job": {
                "main_python_file_uri": script_etl_metadata,
                "args": [gcs_parquet_final_path],
            },
        },
        region=REGION,
        project_id=PROJECT_ID,
    )

    t1_convert_json >> t2_concatenar >> t3_sensor_gcs >> t4_etl_final
