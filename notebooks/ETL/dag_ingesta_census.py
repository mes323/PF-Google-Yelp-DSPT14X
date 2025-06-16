from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'datawave',
    'depends_on_past': False,
    'start_date': datetime(2024, 5, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
}

with DAG(
    'ingesta_censo_to_gcs',
    default_args=default_args,
    schedule_interval='@monthly',  # Modifica si quieres otra frecuencia
    catchup=False,
    max_active_runs=1,
    tags=["censo", "GCS", "automatizacion"]
) as dag:

    inicio = BashOperator(
        task_id='inicio',
        bash_command='echo "Inicio del flujo de ingesta de datos de censo"',
    )

    descargar_datos_censo = BashOperator(
        task_id='descargar_datos_censo',
        bash_command='python3 /mnt/c/Airflow/dags/scripts/script_census_to_gcs.py',
        env={
            'GOOGLE_APPLICATION_CREDENTIALS': 'C:/Users/Pc/Documents/datawave-proyecto-final-99ef0bcb5163.json',
            'GCS_BUCKET': 'proyecto-datawave-dspt14',
            'GCS_PATH': 'raw/census/'
        },
    )

    fin = BashOperator(
        task_id='fin',
        bash_command='echo "Fin del flujo de ingesta de datos de censo"',
    )

    inicio >> descargar_datos_censo >> fin
