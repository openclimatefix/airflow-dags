"""DAGs to forecast site generation using pvsite forecaster."""

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
    "start_date": dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    "retries": 2,
    "retry_delay": dt.timedelta(minutes=5),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

site_forecaster = ContainerDefinition(
    name="forecast-site",
    container_image="docker.io/openclimatefix/pvsite_forecast",
    container_tag="1.0.29",
    container_env={
        "LOGLEVEL": "DEBUG",
        "NWP_ZARR_PATH": f"s3://nowcasting-nwp-{env}/data-metoffice/latest.zarr",
        "OCF_ENVIRONMENT": env,
    },
    container_secret_env={
        f"{env}/rds/pvsite": ["OCF_PV_DB_URL"],
    },
    domain="uk",
    container_cpu=1024,
    container_memory=4096,
)

sitedb_cleaner = ContainerDefinition(
    name="clean-pvsitedb",
    container_image="docker.io/openclimatefix/pvsite_database_cleanup",
    container_tag="1.0.21",
    container_env={
        "SAVE_DIR": f"s3://uk-site-forecaster-models-{env}/database",
        "LOGLEVEL": "INFO",
        "OCF_ENVIRONMENT": env,
    },
    container_secret_env={
        f"{env}/rds/pvsite": ["DB_URL"],
    },
    container_cpu=256,
    container_memory=512,
)

@dag(
    dag_id="uk-forecast-site",
    description=__doc__,
    schedule="*/15 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def site_forecast_dag() -> None:
    """DAG to forecast site level generation data."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    forecast_sites_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="forecast-sites",
        container_def=site_forecaster,
        on_failure_callback=slack_message_callback(
            "❌ The task {{ ti.task_id }} failed. "
            "Please see run book for appropriate actions. ",
        ),
    )

    latest_only_op >> forecast_sites_op

@dag(
    dag_id="uk-manage-sitedb-cleanup",
    description=__doc__,
    schedule="0 0 * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def clean_site_db_dag() -> None:
    """Clean the sites database."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    database_clean_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="uk-clean-sitedb",
        container_def=sitedb_cleaner,
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed, but it is non-critical. "
            "No out of hours support is required.",
        ),
    )

    latest_only_op >> database_clean_op

site_forecast_dag()
clean_site_db_dag()
