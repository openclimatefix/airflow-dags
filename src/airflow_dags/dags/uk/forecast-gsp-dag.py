"""DAGs to forecast generation values using PVNet."""

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

gsp_forecaster = ContainerDefinition(
    name="forecast-pvnet",
    container_image="ghcr.io/openclimatefix/uk-pvnet-app",
    container_tag="2.5.7",
    container_env={
        "LOGLEVEL": "INFO",
        "ALLOW_ADJUSTER": "true",
        "DAY_AHEAD_MODEL": "false",
        "SAVE_BATCHES_DIR": f"s3://uk-national-forecaster-models-{env}/pvnet_batches",
        "NWP_ECMWF_ZARR_PATH": f"s3://nowcasting-nwp-{env}/ecmwf/data/latest.zarr",
        "RAISE_MODEL_FAILURE": "critical",
        "NWP_UKV_ZARR_PATH": f"s3://nowcasting-nwp-{env}/data-metoffice/latest.zarr",
        "SATELLITE_ZARR_PATH": f"s3://nowcasting-sat-{env}/data/latest/latest.zarr.zip",
        "USE_OCF_DATA_SAMPLER": "true",
    },
    container_secret_env={
        f"{env}/rds/forecast/": ["DB_URL"],
    },
    domain="uk",
    container_cpu=2048,
    container_memory=10240,
)

national_forecaster = ContainerDefinition(
    name="forecast-national",
    container_image="docker.io/openclimatefix/gradboost_pv",
    container_tag="1.0.40",
    container_env={
        "LOGLEVEL": "INFO",
        "ML_MODEL_BUCKET": f"uk-national-forecaster-models-{env}",
        "NWP_ZARR_PATH": f"s3://nowcasting-nwp-{env}/data-metoffice/latest.zarr",
    },
    container_secret_env={
        f"{env}/rds/forecast/": ["DB_URL"],
    },
    container_cpu=2048,
    container_memory=11264,
)

forecast_blender = ContainerDefinition(
    name="forecast-blend",
    container_image="docker.io/openclimatefix/uk_pv_forecast_blend",
    container_tag="1.0.7",
    container_env={"LOGLEVEL": "INFO"},
    container_secret_env={
        f"{env}/rds/forecast/": ["DB_URL"],
    },
    container_cpu=512,
    container_memory=1024,
)

@dag(
    dag_id="uk-gsp-forecast",
    description=__doc__,
    schedule_interval="15,45 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def gsp_forecast_pvnet_dag() -> None:
    """Dag to forecast GSP generations using PVNet."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")
    forecast_gsps_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="forecast-gsps",
        container_def=gsp_forecaster,
        env_overrides={
            "RUN_CRITICAL_MODELS_ONLY": "false",
            "ALLOW_SAVE_GSP_SUM": "true",
            "DAY_AHEAD_MODEL": "false",
            "FILTER_BAD_FORECASTS": "false",
        },

        on_failure_callback=slack_message_callback(
            "❌ The task {{ ti.task_id }} failed. "
            "This means one or more of the critical PVNet models have failed to run. "
            "We have about 6 hours before the blend services need this. "
            "Please see run book for appropriate actions.",
        ),
    )

    blend_forecasts_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="blend-forecasts",
        container_def=forecast_blender,
        on_failure_callback=slack_message_callback(
            "❌ The task {{ ti.task_id }} failed."
            "The blending of forecast has failed. "
            "Please see run book for appropriate actions. ",
        ),
    )

    latest_only_op >> forecast_gsps_op >> blend_forecasts_op

@dag(
    dag_id="uk-gsp-forecast-day-ahead",
    description=__doc__,
    schedule_interval="45 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def gsp_forecast_pvnet_dayahead_dag() -> None:
    """DAG to forecast GSPs using PVNet."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    forecast_pvnet_day_ahead_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="forecast-dayahead-gsps",
        container_def=gsp_forecaster,
        task_concurrency=10,
        on_failure_callback=slack_message_callback(
            "❌ the task {{ ti.task_id }} failed. "
            "This would ideally be fixed for da actions at 09.00. "
            "Please see run book for appropriate actions.",
        ),
        env_overrides={
            "DAY_AHEAD_MODEL": "true",
            "RUN_EXTRA_MODELS": "false",
        },
    )

    blend_forecasts_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="blend-forecasts",
        container_def=forecast_blender,
        task_concurrency=10,
        on_failure_callback=slack_message_callback(
            "❌ The task {{ ti.task_id }} failed."
            "The blending of forecast has failed. "
            "Please see run book for appropriate actions. ",
        )
    )

    latest_only_op >> forecast_pvnet_day_ahead_op >> blend_forecasts_op


@dag(
    dag_id="uk-national-forecast",
    description=__doc__,
    schedule_interval="12 */2 * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def national_forecast_dayahead_dag() -> None:
    """DAG to forecast Nationally using XGBoost."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    forecast_national_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="forecast-national",
        container_def=national_forecaster,
        task_concurrency=10,
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. "
            "But its ok, this forecast is only a backup. "
            "No out of office hours support is required, unless other forecasts are failing"
        ),
    )

    blend_forecasts_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="blend-forecasts",
        container_def=forecast_blender,
        task_concurrency=10,
        on_failure_callback=slack_message_callback(
            "❌ The task {{ ti.task_id }} failed."
            "The blending of forecast has failed. "
            "Please see run book for appropriate actions. ",
        )
    )

    latest_only_op >> forecast_national_op >> blend_forecasts_op

gsp_forecast_pvnet_dag()
gsp_forecast_pvnet_dayahead_dag()
national_forecast_dayahead_dag()
