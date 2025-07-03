"""DAGs to forecast generation for sites."""
import datetime as dt
import os

from airflow.decorators import dag
from airflow.operators.latest_only import LatestOnlyOperator

# from airflow_dags.plugins.callbacks.slack import slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import (
    ContainerDefinition,
    EcsAutoRegisterRunTaskOperator,
)

env = os.getenv("ENVIRONMENT", "development")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    "retries": 1,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

site_forecaster = ContainerDefinition(
    name="forecast-site-nl",
    container_image="ghcr.io/openclimatefix/site-forecast-app",
    container_tag="0.0.21",
    container_env={
        "NWP_ECMWF_ZARR_PATH":f"s3://nowcasting-nwp-{env}/ecmwf-nl/data/latest.zarr",
        "SATELLITE_ZARR_PATH":f"s3://nowcasting-sat-{env}/data/latest/latest.zarr.zip",
    },
    container_secret_env={
        f"{env}/rds/pvsite": ["DB_URL"],
    },
    container_cpu=1024,
    container_memory=6144,
    domain="nl",
)


# TODO run this every hour
@dag(
    dag_id="nl-forecast",
    description=__doc__,
    schedule="0 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def nl_forecast_dag() -> None:
    """Create NL forecasts."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    forecast_nl_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="nl-forecast",
        container_def=site_forecaster,
        max_active_tis_per_dag=10,
        env_overrides={
            #"SAVE_BATCHES_DIR": f"s3://uk-national-forecaster-models-{env}/site_pvnet_batches",
        },
        # on_failure_callback=slack_message_callback(
        #     "⚠️ The task {{ ti.task_id }} failed. "
        #     "Please see run book for appropriate actions.",
        # ),
    )

    latest_only_op >> forecast_nl_op

nl_forecast_dag()

