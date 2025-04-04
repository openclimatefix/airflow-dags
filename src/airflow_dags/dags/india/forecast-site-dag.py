"""DAGs to forecast generation for sites."""
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
    "retries": 1,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

india_forecaster = ContainerDefinition(
    name="forecast",
    container_image="docker.io/openclimatefix/india_forecast_app",
    container_tag="1.1.38",
    container_env={
        "NWP_GFS_ZARR_PATH": f"s3://india-nwp-{env}/gfs/data/latest.zarr",
        "NWP_MO_GLOBAL_ZARR_PATH": f"s3://india-nwp-{env}/metoffice/data/latest.zarr",
        "NWP_ECMWF_ZARR_PATH": f"s3://india-nwp-{env}/ecmwf/data/latest.zarr",
    },
    container_secret_env={
        f"{env}/rds/indiadb": ["DB_URL"],
        f"{env}/huggingface/token": ["HUGGINGFACE_TOKEN"],
    },
    container_cpu=1024,
    container_memory=3072,
    domain="india",
)

# hour the forecast can run, not include 7,8,19,20
hours = "0,1,2,3,4,5,6,9,10,11,12,13,14,15,16,17,18,21,22,23"
@dag(
    dag_id="india-forecast-ruvnl",
    description=__doc__,
    schedule=f"0 {hours} * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def ruvnl_forecast_dag() -> None:
    """Create RUVNL forecasts."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    forecast_ruvnl_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="forecast-ruvnl",
        container_def=india_forecaster,
        max_active_tis_per_dag=10,
        env_overrides={
            "SAVE_BATCHES_DIR": f"s3://india-forecast-{env}/RUVNL",
            "USE_SATELLITE": "False",
        },
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. "
            "This would ideally be fixed before for DA actions at 09.00 IST. "
            "No out-of-hours support is required at the moment. "
            "Please see run book for appropriate actions.",
        ),
    )

    latest_only_op >> forecast_ruvnl_op

@dag(
    dag_id="india-forecast-ad",
    description=__doc__,
    schedule="*/15 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def ad_forecast_dag() -> None:
    """Create AD forecasts."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    forecast_ad_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="forecast-ad",
        container_def=india_forecaster,
        env_overrides={
            "CLIENT_NAME": "ad",
            "USE_SATELLITE": "True",
            "SATELLITE_ZARR_PATH": f"s3://india-satellite-{env}/data/latest/iodc_latest.zarr.zip",
            "SAVE_BATCHES_DIR": f"s3://india-forecast-{env}/ad",
        },
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. "
            "No out-of-hours support is required at the moment. "
            "Please see run book for appropriate actions.",
        ),
        max_active_tis_per_dag=10,
    )

    latest_only_op >> forecast_ad_op

ruvnl_forecast_dag()
ad_forecast_dag()
