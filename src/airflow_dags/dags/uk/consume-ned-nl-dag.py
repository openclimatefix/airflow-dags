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
    container_image="docker.io/openclimatefix/solar_consumer",
    container_tag="1.1.1",
    container_secret_env={
        f"{env}/rds/pvsite": ["DB_URL"],
        f"{env}/consumer/nednl": ["APIKEY_NEDNL"],
    },
    container_env={
        "COUNTRY": "nl",
        "SAVE_METHOD": "site-db",
        "ENVIRONMENT": env,
    },
    domain="nl",
    container_cpu=256,
    container_memory=512,
)

@dag(
    dag_id="nl-consume-ned-nl",
    description="Get Ned NL's solar generation.",
    schedule="0 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def ned_nl_consumer_dag() -> None:
    """DAG to download data from Ned NL's solar generation."""
    EcsAutoRegisterRunTaskOperator(
        airflow_task_id="nl-consume-ned-nl-generation",
        container_def=neso_consumer,
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. "
            "But its ok, this only used for comparison. "
            "No out of office hours support is required.",
        ),
    )

ned_nl_consumer_dag()

