"""DAG to produce forecasts of cloud movement.

Uses data from the satellite consumer to predict future cloud patterns.
"""

import datetime as dt
import os

from airflow.decorators import dag

from airflow_dags.plugins.callbacks.slack import slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import (
    ContainerDefinition,
    EcsAutoRegisterRunTaskOperator,
)

env = os.getenv("ENVIRONMENT", "development")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": dt.datetime(2025, 2, 1, tzinfo=dt.UTC),
    "retries": 2,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

cloudcasting_app = ContainerDefinition(
    name="cloudcasting-forecast",
    container_image="ghcr.io/openclimatefix/cloudcasting-app",
    container_tag="0.0.7",
    container_env={
        "OUTPUT_PREDICTION_DIRECTORY": f"s3://nowcasting-sat-{env}/cloudcasting_forecast",
        "SATELLITE_ZARR_PATH": f"s3://nowcasting-sat-{env}/data/latest/latest.zarr.zip",
        "LOGLEVEL": "INFO",
    },
    domain="uk",
    container_memory=4096,
    container_cpu=1024,
)

@dag(
    dag_id="uk-cloudcasting",
    description=__doc__,
    schedule="20,50 * * * *",
    default_args=default_args,
    catchup=False,
)
def cloudcasting_dag() -> None:
    """Dag to forecast upcoming cloud patterns."""
    cloudcasting_forecast = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="run_cloudcasting_app",
        container_def=cloudcasting_app,
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed,"
            " but its ok. The cloudcasting is currently not critical. "
            "No out of hours support is required.",
        ),
    )

    cloudcasting_forecast

cloudcasting_dag()

