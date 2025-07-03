"""DAG to download and process NWP data from various sources."""

import datetime as dt
import os

from airflow.decorators import dag
from airflow.operators.latest_only import LatestOnlyOperator

from airflow_dags.plugins.callbacks.slack import slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import (
    ContainerDefinition,
    EcsAutoRegisterRunTaskOperator,
)
from airflow_dags.plugins.scripts.s3 import determine_latest_zarr

env = os.getenv("ENVIRONMENT", "development")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 1,
    "concurrency": 10,
    "max_active_tasks": 10,
}

nwp_consumer = ContainerDefinition(
    name="nwp-consumer",
    container_image="ghcr.io/openclimatefix/nwp-consumer",
    container_tag="1.1.10",
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
    domain="india",
)


@dag(
    dag_id="india-consume-nwp",
    description=__doc__,
    schedule="0 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def nwp_consumer_dag() -> None:
    """DAG to download and process NWP data."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    consume_ecmwf_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-ecmwf-nwp",
        container_def=nwp_consumer,
        env_overrides={
            "MODEL_REPOSITORY": "ecmwf-realtime",
            "MODEL": "hres-ifs-india",
            "ECMWF_REALTIME_S3_BUCKET": "ocf-ecmwf-production",
            "ECMWF_REALTIME_S3_REGION": "eu-west-1",
            "ZARRDIR": f"s3://india-nwp-{env}/ecmwf/data",
        },
        max_active_tis_per_dag=10,
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. 🇮🇳 "
            "The forecast will continue running until it runs out of data. "
            "ECMWF status link is <https://status.ecmwf.int/|here>. "
            "No out-of-hours support is required at the moment. "
            "Please see run book for appropriate actions.",
        ),
    )

    consume_gfs_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-gfs-nwp",
        container_def=nwp_consumer,
        max_active_tis_per_dag=10,
        env_overrides={
            "MODEL_REPOSITORY": "gfs",
            "ZARRDIR": f"s3://india-nwp-{env}/gfs/data",
        },
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. 🇮🇳 "
            "The forecast will continue running until it runs out of data. "
            "GFS status link is "
            "<https://www.nco.ncep.noaa.gov/pmb/nwprod/prodstat/|here>. "
            "No out-of-hours support is required at the moment. "
            "Please see run book for appropriate actions.",
        ),
    )

    consume_metoffice_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-metoffice-nwp",
        container_def=nwp_consumer,
        max_active_tis_per_dag=10,
        env_overrides={
            "MODEL_REPOSITORY": "metoffice-datahub",
            "METOFFICE_ORDER_ID": "india-11params-54steps",
            "ZARRDIR": f"s3://india-nwp-{env}/metoffice/data",
        },
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. 🇮🇳 "
            "The forecast will continue running until it runs out of data. "
            "Metoffice status link is "
            "<https://datahub.metoffice.gov.uk/support/service-status|here>. "
            "No out-of-hours support is required at the moment. "
            "Please see run book for appropriate actions.",
        ),
    )

    rename_zarr_metoffice = determine_latest_zarr.override(
        task_id="rename-latest-metoffice-data",
    )(bucket=f"india-nwp-{env}", prefix="metoffice/data")

    rename_zarr_ecmwf = determine_latest_zarr.override(
        task_id="rename-latest-ecmwf-data",
    )(bucket=f"india-nwp-{env}", prefix="ecmwf/data")

    rename_zarr_gfs = determine_latest_zarr.override(
        task_id="rename-latest-gfs-data",
    )(bucket=f"india-nwp-{env}", prefix="gfs/data")

    latest_only_op >> consume_ecmwf_op >> rename_zarr_ecmwf
    latest_only_op >> consume_gfs_op >> rename_zarr_gfs
    latest_only_op >> consume_metoffice_op >> rename_zarr_metoffice


nwp_consumer_dag()
