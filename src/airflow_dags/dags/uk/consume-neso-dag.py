"""Dag to download forecasts produced by NESO."""

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
    "retries": 0,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
    "execution_timeout": dt.timedelta(minutes=45),
}

neso_consumer = ContainerDefinition(
    name="neso-consumer",
    container_image="docker.io/openclimatefix/neso_solar_consumer_api",
    container_tag="1.0.3",
    container_secret_env={
        f"{env}/rds/forecast/": ["DATABASE_URL"],
    },
    domain="uk",
    container_cpu=256,
    container_memory=512,
)

@dag(
    dag_id="uk-neso-consumer",
    description="Get NESO's solar forecast.",
    schedule_interval="0 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def neso_consumer_dag() -> None:
    """DAG to download data from NESO's solar forecast."""
    consume_neso_forecast = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-neso-forecast",
        container_def=neso_consumer,
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. "
            "But its ok, this only used for comparison. "
            "No out of office hours support is required.",
        ),
    )

    consume_neso_forecast

neso_consumer_dag()

