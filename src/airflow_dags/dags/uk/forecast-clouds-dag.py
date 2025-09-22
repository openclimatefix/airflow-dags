"""DAGs to produce forecasts of satellite imagery and score them against the ground truths.

Uses data from the satellite consumer to predict future satellite images.
"""

import datetime as dt
import os

from airflow.decorators import dag

from airflow_dags.plugins.callbacks.slack import get_task_link, slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import (
    ContainerDefinition,
    EcsAutoRegisterRunTaskOperator,
)

env = os.getenv("ENVIRONMENT", "development")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": dt.datetime(2025, 2, 1, tzinfo=dt.UTC),
    "retries": 2,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

PREDICTION_SAVE_DIRECTORY = f"s3://nowcasting-sat-{env}/cloudcasting_forecast"

cloudcasting_inference = ContainerDefinition(
    name="cloudcasting-inference",
    container_image="ghcr.io/openclimatefix/cloudcasting-app",
    container_tag="1.0.0",
    container_command=["inference"],
    container_env={
        "PREDICTION_SAVE_DIRECTORY": PREDICTION_SAVE_DIRECTORY,
        "SATELLITE_ZARR_PATH": f"s3://nowcasting-sat-{env}/rss/data/latest.zarr.zip",
        "SATELLITE_15_ZARR_PATH": f"s3://nowcasting-sat-{env}/odegree/data/latest.zarr.zip",
        "LOGLEVEL": "INFO",
    },
    domain="uk",
    container_memory=4096,
    container_cpu=1024,
)


@dag(
    dag_id="uk-forecast-clouds",
    description=__doc__,
    schedule="12,42 * * * *",
    default_args=default_args,
    catchup=False,
)
def cloudcasting_inference_dag() -> None:
    """Dag to run the satellite forecast."""
    EcsAutoRegisterRunTaskOperator(
        airflow_task_id="run-cloudcasting-inference",
        container_def=cloudcasting_inference,
        on_failure_callback=slack_message_callback(
            f"⚠️🇬🇧 The {get_task_link()} failed, "
            "but its ok. The cloudcasting is currently not critical. "
            "No out of hours support is required.",
        ),
    )


cloudcasting_metrics = ContainerDefinition(
    name="cloudcasting-metrics",
    container_image="ghcr.io/openclimatefix/cloudcasting-app",
    container_tag="1.0.0",
    container_command=["metrics"],
    container_env={
        "PREDICTION_SAVE_DIRECTORY": PREDICTION_SAVE_DIRECTORY,
        "SATELLITE_ICECHUNK_ARCHIVE": f"s3://nowcasting-sat-{env}/rss/data/rss_uk3000m.icechunk",
        "METRIC_ZARR_PATH": f"s3://nowcasting-sat-{env}/cloudcasting_forecast/metrics.zarr",
        "LOGLEVEL": "INFO",
    },
    domain="uk",
    container_memory=4096,
    container_cpu=1024,
)


@dag(
    dag_id="uk-analysis-clouds",
    description=__doc__,
    schedule="0 6 * * *",
    default_args=default_args,
    catchup=False,
)
def cloudcasting_metrics_dag() -> None:
    """Dag to score previous day's satellite forecasts."""
    EcsAutoRegisterRunTaskOperator(
        airflow_task_id="run-cloudcasting-metrics",
        container_def=cloudcasting_metrics,
        on_failure_callback=slack_message_callback(
            f"⚠️🇬🇧 The {get_task_link()} failed. Metrics do not require out of hours support.",
        ),
    )


cloudcasting_inference_dag()
cloudcasting_metrics_dag()
