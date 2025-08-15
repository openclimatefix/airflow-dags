"""DAG to consume satellite data."""

import datetime as dt
import os

from airflow.decorators import dag
from airflow.operators.latest_only import LatestOnlyOperator

from airflow_dags.plugins.callbacks.slack import get_task_link, slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import (
    ContainerDefinition,
    EcsAutoRegisterRunTaskOperator,
)
from airflow_dags.plugins.scripts.s3 import extract_latest_zarr

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

sat_consumer = ContainerDefinition(
    name="satellite-consumer",
    container_image="ghcr.io/openclimatefix/satellite-consumer",
    container_tag="0.3.0",
    container_env={
        "LOGLEVEL": "DEBUG",
        "SATCONS_COMMAND": "consume",
        "SATCONS_ICECHUNK": "true",
        "SATCONS_SATELLITE": "iodc",
        "SATCONS_VALIDATE": "false", # TODO
        "SATCONS_RESOLUTION": "3000",
        "SATCONS_WINDOW_MINS": "120",
        "SATCONS_NUM_WORKERS": "1",
        "SATCONS_CROP_REGION": "INDIA",
    },
    container_secret_env={
        f"{env}/data/satellite-consumer": [
            "EUMETSAT_CONSUMER_KEY",
            "EUMETSAT_CONSUMER_SECRET",
        ],
    },
    domain="india",
    container_cpu=1024,
    container_memory=5120,
    container_storage=30,
)

satellite_consumer_old = ContainerDefinition(
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
            "API_KEY",
            "API_SECRET",
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
        container_def=satellite_consumer_old,
        max_active_tis_per_dag=10,
        on_failure_callback=slack_message_callback(
            f"⚠️🇮🇳 The {get_task_link()}  failed."
            "The EUMETSAT status link for the IODC satellite is "
            "here <https://masif.eumetsat.int/ossi/webpages/level2.html?"
            "ossi_level2_filename=seviri_iodc.html|here> "
            "and the general EUMETSAT status link is <https://uns.eumetsat.int/uns/|here>. "
            "No out-of-hours support is required at the moment. "
            "Please see run book for appropriate actions.",
        ),
    )

    consume_iodc_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-iodc",
        container_def=sat_consumer,
        env_overrides={
            "SATCONS_TIME": "{{"
            + "(data_interval_start - macros.timedelta(minutes=210))"
            + ".strftime('%Y-%m-%dT%H:%M')"
            + "}}",
            "SATCONS_WORKDIR": f"s3://india-satellite-{env}/iodc",
        },
        task_concurrency=1,
    )
    extract_latest_iodc_op = extract_latest_zarr(
        bucket=f"india-satellite-{env}",
        prefix="iodc/data/iodc_india3000m.icechunk",
        window_mins=120,
        cadence_mins=15,
    )

    latest_only_op >> consume_sat_op
    latest_only_op >> consume_iodc_op >> extract_latest_iodc_op


sat_consumer_dag()
