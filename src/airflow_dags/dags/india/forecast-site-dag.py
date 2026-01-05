"""DAGs to forecast generation for sites."""

import datetime as dt
import os

from airflow.decorators import dag
from airflow.operators.latest_only import LatestOnlyOperator

from airflow_dags.plugins.callbacks.slack import Urgency, get_slack_message_callback
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
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

india_forecaster = ContainerDefinition(
    name="forecast",
    container_image="docker.io/openclimatefix/india_forecast_app",
    container_tag="1.2.2",
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

ad_forecaster = ContainerDefinition(
    name="forecast-ad",
    container_image="ghcr.io/openclimatefix/site-forecast-app",
    container_tag="1.2.0",
    container_env={
        "NWP_MO_GLOBAL_ZARR_PATH": f"s3://india-nwp-{env}/metoffice/data/latest.zarr",
        "NWP_ECMWF_ZARR_PATH": f"s3://india-nwp-{env}/ecmwf/data/latest.zarr",
        "SATELLITE_ZARR_PATH": f"s3://india-satellite-{env}/iodc/data/latest.zarr.zip",
        "CLIENT_NAME": "ad",
        "COUNTRY": "india",
    },
    container_secret_env={
        f"{env}/rds/indiadb": ["DB_URL"],
        f"{env}/huggingface/token": ["HUGGINGFACE_TOKEN"],
    },
    container_cpu=1024,
    container_memory=3072,
    domain="india",
)

ruvnl_forecaster_v2 = ContainerDefinition(
    name="forecast-ruvnl-v2",
    container_image="ghcr.io/openclimatefix/site-forecast-app",
    container_tag="add-gencast-support" if env=="development" else "1.2.0",
    container_env={
        "NWP_MO_GLOBAL_ZARR_PATH": f"s3://india-nwp-{env}/metoffice/data/latest.zarr",
        "NWP_ECMWF_ZARR_PATH": f"s3://india-nwp-{env}/ecmwf/data/latest.zarr",
        "SATELLITE_ZARR_PATH": f"s3://india-satellite-{env}/iodc/data/latest.zarr.zip",
        "NWP_GENCAST_GCS_BUCKET_PATH": "gs://weathernext/126478713_1_0/zarr/126478713_2024_to_present/",
        "NWP_GENCAST_ZARR_PATH": "/tmp/nwp_gencast_out.zarr", # noqa: S108
        "CLIENT_NAME": "ruvnl",
        "COUNTRY": "india",
    },
    container_secret_env={
        f"{env}/rds/indiadb": ["DB_URL"],
        f"{env}/huggingface/token": ["HUGGINGFACE_TOKEN"],
        # TODO add gcs credentials secrets here or need to mount a volume?
    },
    container_cpu=1024,
    container_memory=3072,
    domain="india",
)

@dag(
    dag_id="india-forecast-ruvnl",
    description=__doc__,
    schedule="0 * * * *",
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
        on_failure_callback=get_slack_message_callback(
            country="in",
            additional_message_context=(
                "This would ideally be fixed before for DA actions at 09.00 IST. "
            ),
            urgency=Urgency.SUBCRITICAL,
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
            # TODO check if this is acyually used
            "SATELLITE_ZARR_PATH": f"s3://india-satellite-{env}/iodc/data/latest.zarr.zip",
            "SAVE_BATCHES_DIR": f"s3://india-forecast-{env}/ad",
        },
        on_failure_callback=get_slack_message_callback(country="in", urgency=Urgency.SUBCRITICAL),
        max_active_tis_per_dag=10,
    )

    forecast_ad_v2_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="forecast-ad-v2",
        container_def=ad_forecaster,
        env_overrides={
            "SAVE_BATCHES_DIR": f"s3://india-forecast-{env}/ad-v2",
        },
        on_failure_callback=get_slack_message_callback(
            country="in",
            urgency=Urgency.SUBCRITICAL,
        ),
        max_active_tis_per_dag=10,
    )

    latest_only_op >> [forecast_ad_op, forecast_ad_v2_op]

@dag(
    dag_id="india-forecast-ruvnl-v2",
    description=__doc__,
    schedule="0 * * * *",
    start_date=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def ruvnl_forecast_v2_dag() -> None:
    """Create RUVNL forecasts."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    forecast_ruvnl_v2_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="forecast-ruvnl-v2",
        container_def=ruvnl_forecaster_v2,
        env_overrides={
            "CLIENT_NAME": "ruvnl",
            "USE_SATELLITE": "False",
            "SAVE_BATCHES_DIR": f"s3://india-forecast-{env}/RUVNL-v2",
        },
        on_failure_callback=get_slack_message_callback(country="in", urgency=Urgency.SUBCRITICAL),
        max_active_tis_per_dag=10,
    )

    latest_only_op >> forecast_ruvnl_v2_op


ruvnl_forecast_dag()
ad_forecast_dag()
ruvnl_forecast_v2_dag()
