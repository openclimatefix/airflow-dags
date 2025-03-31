"""DAG to consume satellite data."""

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
    "retries": 0,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
    "execution_timeout": dt.timedelta(minutes=45),
}

satellite_consumer = ContainerDefinition(
    name="satellite-consumer",
    container_image="docker.io/openclimatefix/satip",
    container_tag="2.12.9",
    container_env={
        "SAVE_DIR": f"s3://india-satellite-{env}/data",
        "SAVE_DIR_NATIVE": f"s3://india-satellite-{env}/raw",
        "USE_IODC": "True",
        "HISTORY": "75 minutes",
    },
    container_secret_env={
        f"{env}/data/satellite-consumer": [
            "API_KEY", "API_SECRET",
        ],
    },
    container_cpu=1024,
    container_memory=5120,
    domain="india",
)

@dag(
    dag_id="india-consume-satellite",
    description=__doc__,
    schedule="*/5 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def sat_consumer_dag() -> None:
    """DAG to consume satellite data."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    consume_sat_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-sat-iodc",
        container_def=satellite_consumer,
        max_active_tis_per_dag=10,
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. "
            "EUMETSAT status links are <https://uns.eumetsat.int/uns/|here> "
            "and <https://masif.eumetsat.int/ossi/webpages/level2.html?"
            "ossi_level2_filename=seviri_iodc.html|here>. "
            "No out-of-hours support is required at the moment. "
            "Please see run book for appropriate actions.",
        ),
    )

    latest_only_op >> consume_sat_op

sat_consumer_dag()