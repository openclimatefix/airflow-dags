"""DAG to download and process NWP data from various sources."""


import datetime as dt
import os

from airflow.decorators import dag
from airflow.operators.bash import BashOperator
from airflow.operators.latest_only import LatestOnlyOperator

from airflow_dags.plugins.callbacks.slack import slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import (
    ContainerDefinition,
    EcsAutoRegisterRunTaskOperator,
)
from airflow_dags.plugins.scripts.s3 import determine_latest_zarr

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 1,
    "concurrency": 10,
    "max_active_tasks": 10,
}

env = os.getenv("ENVIRONMENT", "development")

nwp_consumer = ContainerDefinition(
    name="nwp-consumer",
    container_image="ghcr.io/openclimatefix/nwp-consumer",
    container_tag="1.1.9",
    container_env={
        "CONCURRENCY": "false",
        "LOGLEVEL": "DEBUG",
    },
    container_secret_env={
        f"{env}/data/nwp-consumer": [
            "ECMWF_REALTIME_S3_ACCESS_KEY",
            "ECMWF_REALTIME_S3_ACCESS_SECRET",
            "METOFFICE_API_KEY",
        ],
    },
    container_command=["consume"],
    container_cpu=512,
    container_memory=1024,
)

def update_operator(provider: str) -> BashOperator:
    """BashOperator to update the API with the latest downloaded data."""
    file: str = f"s3://nowcasting-nwp-{env}/data-metoffice/latest.zarr/.zattrs"
    if provider == "ecmwf":
        file = f"s3://nowcasting-nwp-{env}/ecmwf/data/latest.zarr/.zattrs"
    url: str = "http://api-dev.quartz.solar" if env == "development" else "http://api.quartz.solar"
    command: str = f'curl -X GET "{url}/v0/solar/GB/update_last_data?component=nwp&file={file}"'
    return BashOperator(
        task_id=f"update-api-{provider}",
        bash_command=command,
    )

@dag(
    dag_id="uk-consume-nwp",
    description=__doc__,
    schedule="10,25,40,55 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def nwp_consumer_dag() -> None:
    """DAG to download and process NWP data."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    consume_metoffice_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-metoffice-nwp",
        container_def=nwp_consumer,
        env_overrides={
            "MODEL_REPOSITORY": "metoffice-datahub",
            "MODEL": "um-ukv-2km",
            "METOFFICE_ORDER_ID": "uk-12params-42steps",
            "ZARRDIR": f"s3://nowcasting-nwp-{env}/data-metoffice",
        },
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. "
            "This is non-critical; the forecast will move to ECMWF-only, "
            "Metoffice status link is "
            "<https://datahub.metoffice.gov.uk/support/service-status|here> "
            "No out of office hours support is required, "
            "but please log in an incident log. ",
        ),
    )

    consume_ecmwf_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-ecmwf-nwp",
        container_def=nwp_consumer,
        env_overrides={
            "MODEL_REPOSITORY": "ecmwf-realtime",
            "ECMWF_REALTIME_S3_BUCKET": "ocf-ecmwf-production",
            "ECMWF_REALTIME_S3_REGION": "eu-west-1",
            "ZARRDIR": f"s3://nowcasting-nwp-{env}/ecmwf/data",
        },
        on_failure_callback=slack_message_callback(
            "❌ The task {{ ti.task_id }} failed. "
            "The forecast will continue running until it runs out of data. "
            "ECMWF status link is <https://status.ecmwf.int/|here> "
            "Please see run book for appropriate actions. ",
        ),
    )

    rename_zarr_ecmwf_op = determine_latest_zarr.override(
        task_id="rename-latest-ecmwf-data",
    )(bucket=f"nowcasting-nwp-{env}", prefix="ecmwf/data")

    rename_zarr_metoffice_op = determine_latest_zarr.override(
        task_id="rename-latest-metoffice-data",
    )(bucket=f"nowcasting-nwp-{env}", prefix="data-metoffice")

    call_api_update_metoffice_op = update_operator(provider="metoffice")
    call_api_update_ecmwf_op = update_operator(provider="ecmwf")

    latest_only_op >> consume_metoffice_op >> rename_zarr_metoffice_op >> call_api_update_metoffice_op
    latest_only_op >> consume_ecmwf_op >> rename_zarr_ecmwf_op >> call_api_update_ecmwf_op

nwp_consumer_dag()
