"""Dag to download PV generation data."""

import datetime as dt
import os

from airflow.decorators import dag
from airflow.operators.latest_only import LatestOnlyOperator

from airflow_dags.plugins.callbacks.slack import slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import (
    ContainerDefinition,
    EcsAutoRegisterRunTaskOperator,
)

env = os.getenv("ENVIRONMENT", "development")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

pv_consumer = ContainerDefinition(
    name="pv-consumer",
    container_image="docker.io/openclimatefix/pvconsumer",
    container_tag="2.2.1",
    container_env={
        "PROVIDER": "solar_sheffield_passiv",
        "LOGLEVEL": "INFO",
    },
    container_secret_env={
        f"{env}/rds/pvsite": ["DB_URL"],
        f"{env}/data/solar-sheffield": [
            "SS_USER_ID",
            "SS_KEY",
            "SS_URL",
        ],
    },
    container_cpu=256,
    container_memory=512,
)


@dag(
    dag_id="uk-consume-pv",
    description=__doc__,
    schedule="*/5 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def pv_consumer_dag() -> None:
    """Fetch PV generation data."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    consume_pv_passiv_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-passiv-pv-data",
        container_def=pv_consumer,
        max_active_tis_per_dag=10,
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. 🇬🇧 "
            "But its ok, this isnt needed for any production services. "
            "No out of office hours support is required.",
        ),
    )

    latest_only_op >> consume_pv_passiv_op


pv_consumer_dag()
