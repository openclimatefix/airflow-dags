"""DAG to clean up airflow logs."""
import datetime as dt
import logging
from datetime import timedelta

from airflow.decorators import dag
from airflow.operators.python import PythonOperator

from airflow_dags.plugins.scripts.remove_old_logs import cleanup_logs

logger = logging.getLogger(__name__)

# Define DAG arguments
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

# Define the DAG, e.g., runs daily at 3 AM
@dag(
    dag_id="india-manage-clean-up-logs",
    description="DAG to clean up old logs.",
    schedule="0 3 * * *",  # 03:00 UTC
    start_date=dt.datetime(2025, 3, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def clean_up_logs_dag() -> None:
    """Run Clean up logs dag."""
    _ = PythonOperator(
        task_id="cleanup_airflow_logs",
        python_callable=cleanup_logs,
    )

# Register both DAGs
clean_up_logs_dag()
