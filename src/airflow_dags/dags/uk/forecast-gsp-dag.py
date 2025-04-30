"""DAGs to forecast generation values using PVNet."""

import datetime as dt
import os

import requests
from airflow.decorators import dag
from airflow.operators.latest_only import LatestOnlyOperator
from airflow.operators.python import PythonOperator

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
    container_tag="2.5.17",
    container_env={
        "LOGLEVEL": "INFO",
        "ALLOW_ADJUSTER": "true",
        "DAY_AHEAD_MODEL": "false",
        "SAVE_BATCHES_DIR": f"s3://uk-national-forecaster-models-{env}/pvnet_batches",
        "NWP_ECMWF_ZARR_PATH": f"s3://nowcasting-nwp-{env}/ecmwf/data/latest.zarr",
        "RAISE_MODEL_FAILURE": "critical",
        "NWP_UKV_ZARR_PATH": f"s3://nowcasting-nwp-{env}/data-metoffice/latest.zarr",
        "SATELLITE_ZARR_PATH": f"s3://nowcasting-sat-{env}/data/latest/latest.zarr.zip",
        "USE_OCF_DATA_SAMPLER": str(env == "development").lower(),
    },
    container_secret_env={
        f"{env}/rds/forecast/": ["DB_URL"],
    },
    domain="uk",
    container_cpu=2048,
    container_memory=12288,
)

# This version should only be used on dev for the time-being
dev_gsp_intraday_forecaster = ContainerDefinition(
    name="forecast-pvnet",
    container_image="ghcr.io/openclimatefix/uk-pvnet-app",
    container_tag="cloudcasting_inputs",
    container_env={
        "LOGLEVEL": "INFO",
        "RAISE_MODEL_FAILURE": "critical",
        "ALLOW_ADJUSTER": "true",
        "DAY_AHEAD_MODEL": "false",
        "SAVE_BATCHES_DIR": f"s3://uk-national-forecaster-models-{env}/pvnet_batches",
        "NWP_ECMWF_ZARR_PATH": f"s3://nowcasting-nwp-{env}/ecmwf/data/latest.zarr",
        "NWP_UKV_ZARR_PATH": f"s3://nowcasting-nwp-{env}/data-metoffice/latest.zarr",
        "SATELLITE_ZARR_PATH": f"s3://nowcasting-sat-{env}/data/latest/latest.zarr.zip",
        "CLOUDCASTING_ZARR_PATH": f"s3://nowcasting-sat-{env}/cloudcasting_forecast/latest.zarr",
    },
    container_secret_env={
        f"{env}/rds/forecast/": ["DB_URL"],
    },
    domain="uk",
    container_cpu=2048,
    container_memory=12288,
)

gsp_intraday_forecaster = dev_gsp_intraday_forecaster if env == "development" else gsp_forecaster

national_forecaster = ContainerDefinition(
    name="forecast-national",
    container_image="docker.io/openclimatefix/gradboost_pv",
    container_tag="1.0.41",
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
    container_tag="1.1.1",
    container_env={"LOGLEVEL": "INFO"},
    container_secret_env={
        f"{env}/rds/forecast/": ["DB_URL"],
    },
    container_cpu=512,
    container_memory=1024,
)


def get_forecast_last_run_from_api(model_name: str) -> dt.datetime:
    """Get last forecast run."""
    url = "http://api-dev.quartz.solar" if env == "development" else "http://api.quartz.solar"
    response_pvnet = requests.get(
        f"{url}/v0/solar/GB/check_last_forecast_run?model_name={model_name}",
        timeout=10,
    )

    pvnet_last_run = dt.datetime.strptime(response_pvnet.json(), "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=dt.UTC,
    )

    return pvnet_last_run


def check_forecast_status() -> str:
    """Check the status of the forecast models."""
    # check api for forecast models pvnet_v2 and pvnet_ecmwf
    now = dt.datetime.now(tz=dt.UTC)

    pvnet_last_run = get_forecast_last_run_from_api("pvnet_v2")
    pvnet_ecmwf_last_run = get_forecast_last_run_from_api("pvnet_ecmwf")

    pvnet_delay = now - pvnet_last_run
    pvnet_ecmwf_delay = now - pvnet_ecmwf_last_run

    pvnet_last_run_str = pvnet_last_run.strftime("%Y-%m-%d %H:%M")
    pvnet_ecmwf_last_run_str = pvnet_ecmwf_last_run.strftime("%Y-%m-%d %H:%M")

    hours = 2

    if (pvnet_delay <= dt.timedelta(hours=hours)) and (
        pvnet_ecmwf_delay <= dt.timedelta(hours=hours)
    ):
        message = (
            "⚠️The task forecast-gsps has failed, "
            f"but PVNet and PVNet ECMWF only model have run within the last {hours} hours. "
            "No actions is required. "
        )

    elif (pvnet_delay > dt.timedelta(hours=hours)) and (
        pvnet_ecmwf_delay <= dt.timedelta(hours=hours)
    ):
        message = (
            "⚠️ The task forecast-gsps failed. "
            f"This means in the last {hours} hours, PVNet has failed to run "
            "but PVNet ECMWF only model has run. "
            "Please see run book for appropriate actions."
        )
    elif (pvnet_delay > dt.timedelta(hours=hours)) and (
        pvnet_ecmwf_delay > dt.timedelta(hours=hours)
    ):
        message = (
            "❌ The task forecast-gsps failed. "
            f"This means PVNet and PVNET_ECMWF has failed to run in the last {hours} hours. "
            f" Last success run of PVNet was {pvnet_last_run_str} "
            f"and PVNet ECMWF was {pvnet_ecmwf_last_run_str}. "
            "Please see run book for appropriate actions."
        )
    else:
        message = (
            "❌ The task forecast-gsps failed. "
            f" Last success run of PVNet was {pvnet_last_run_str} "
            f"and PVNet ECMWF was {pvnet_ecmwf_last_run_str}. "
            "Please see run book for appropriate actions."
        )

    return message


@dag(
    dag_id="uk-forecast-gsp",
    description=__doc__,
    schedule="15,45 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def gsp_forecast_pvnet_dag() -> None:
    """Dag to forecast GSP generations using PVNet."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")
    forecast_gsps_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="forecast-gsps",
        container_def=gsp_intraday_forecaster,
        env_overrides={
            "RUN_CRITICAL_MODELS_ONLY": str(env == "production").lower(),
            "ALLOW_SAVE_GSP_SUM": "true",
            "DAY_AHEAD_MODEL": "false",
            "FILTER_BAD_FORECASTS": "false",
        },
    )

    check_forecasts_op = PythonOperator(
        task_id="check-forecast-gsps-last-run",
        trigger_rule="one_failed",
        python_callable=check_forecast_status,
        on_success_callback=slack_message_callback(
            "{{ti.xcom_pull(task_ids='check-forecast-gsps-last-run')}}"),
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed."
            "This was trying to check when PVNet and PVNet ECMWF only last ran",
        ),
    )

    blend_forecasts_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="blend-forecasts",
        container_def=forecast_blender,
        trigger_rule="all_done",
        on_failure_callback=slack_message_callback(
            "❌ The task {{ ti.task_id }} failed."
            "The blending of forecast has failed. "
            "Please see run book for appropriate actions. ",
        ),
    )

    latest_only_op >> forecast_gsps_op >> [blend_forecasts_op, check_forecasts_op]


@dag(
    dag_id="uk-forecast-gsp-dayahead",
    description=__doc__,
    schedule="45 * * * *",
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
        max_active_tis_per_dag=10,
        on_failure_callback=slack_message_callback(
            "❌ the task {{ ti.task_id }} failed. "
            "This would ideally be fixed for da actions at 09.00. "
            "Please see run book for appropriate actions.",
        ),
        env_overrides={
            "DAY_AHEAD_MODEL": "true",
            "RUN_EXTRA_MODELS": "false",
            "USE_OCF_DATA_SAMPLER": "true",
        },
    )

    blend_forecasts_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="blend-forecasts",
        container_def=forecast_blender,
        max_active_tis_per_dag=10,
        on_failure_callback=slack_message_callback(
            "❌ The task {{ ti.task_id }} failed."
            "The blending of forecast has failed. "
            "Please see run book for appropriate actions. ",
        ),
    )

    latest_only_op >> forecast_pvnet_day_ahead_op >> blend_forecasts_op


@dag(
    dag_id="uk-forecast-national",
    description=__doc__,
    schedule="12 */2 * * *",
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
        max_active_tis_per_dag=10,
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. "
            "But its ok, this forecast is only a backup. "
            "No out of office hours support is required, unless other forecasts are failing",
        ),
    )

    blend_forecasts_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="blend-forecasts",
        container_def=forecast_blender,
        max_active_tis_per_dag=10,
        env_overrides={"N_GSP": "1"},
        on_failure_callback=slack_message_callback(
            "❌ The task {{ ti.task_id }} failed."
            "The blending of forecast has failed. "
            "Please see run book for appropriate actions. ",
        ),
    )

    latest_only_op >> forecast_national_op >> blend_forecasts_op


gsp_forecast_pvnet_dag()
gsp_forecast_pvnet_dayahead_dag()
national_forecast_dayahead_dag()
