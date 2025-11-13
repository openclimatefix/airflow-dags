"""DAGs to dowload data from PVLive.

This service gives an estimate of the current solar generation in the UK,
in two regimes, 'in-day' and 'day-after'. This gives a baseline to compare
the forecasts against.
"""

import datetime as dt
import os
from datetime import timedelta

from airflow.decorators import dag
from airflow.operators.bash import BashOperator

from airflow_dags.plugins.callbacks.slack import Urgency, get_slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import (
    ContainerDefinition,
    EcsAutoRegisterRunTaskOperator,
)

env = os.getenv("ENVIRONMENT", "development")
url: str = "http://api-dev.quartz.solar" if env == "development" else "http://api.quartz.solar"

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

pvlive_consumer = ContainerDefinition(
    name="pvlive-consumer",
    container_image="docker.io/openclimatefix/pvliveconsumer",
    container_tag="1.3.2",
    container_env={
        "LOGLEVEL": "INFO",
        "PVLIVE_DOMAIN_URL": "api.pvlive.uk",
    },
    container_secret_env={
        f"{env}/rds/forecast/": ["DB_URL"],
    },
    domain="uk",
    container_cpu=256,
    container_memory=512,
)

pvlive_consumer_data_platform = ContainerDefinition(
    name="pvlive-consumer-data-platform",
    container_image="ghcr.io/openclimatefix/solar-consumer",
    container_tag="1.4.2",
    container_env={
        "LOGURU_LEVEL": "INFO",
        "PVLIVE_DOMAIN_URL": "api.pvlive.uk",
        "SAVE_METHOD": "data-platform",
        "UK_PVLIVE_N_GSPS": "342",
        "UK_PVLIVE_REGIME": "in-day",
        "UK_PVLIVE_BACKFILL_HOURS": "12",
        "COUNTRY": "gb",
    },
    container_secret_env={
        f"{env}/rds/forecast/": ["DB_URL"],
        f"{env}/rds/dataplatform": ["DATA_PLATFORM_HOST"],
    },
    domain="uk",
    container_cpu=256,
    container_memory=512,
)


@dag(
    dag_id="uk-consume-pvlive-intraday",
    description=__doc__,
    schedule="6,9,12,14,20,36,39,42,44,50 * * * *",
    start_date=dt.datetime(2025, 3, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def pvlive_intraday_consumer_dag() -> None:
    """Dag to download pvlive intraday data."""
    consume_pvlive_gsps = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="pvlive-intraday-consumer-gsps",
        container_def=pvlive_consumer,
        env_overrides={
            "N_GSPS": "342",
            "REGIME": "in-day",
            "BACKFILL_HOURS": "12",
        },
        on_failure_callback=get_slack_message_callback(
            additional_message_context= (
            "This is needed for the adjuster in the Forecast."
            "Its good to check <https://www.solar.sheffield.ac.uk/pvlive/|PV Live> "
            "to see if it's working. "
            ),
            urgency=Urgency.SUBCRITICAL,
        ),
    )

    update_api_last_gsp_data = BashOperator(
        task_id="uk-gsp-lastdownloaded-api-update",
        bash_command=f"curl -X GET {url}/v0/solar/GB/update_last_data?component=gsp",
    )

    consume_pvlive_gsps >> update_api_last_gsp_data

    if env == "development":
        consume_pvlive_gsps_data_platform = EcsAutoRegisterRunTaskOperator(
            airflow_task_id="pvlive-intraday-consumer-data-platform",
            container_def=pvlive_consumer_data_platform,
        )

        consume_pvlive_gsps_data_platform  # noqa: B018

@dag(
    dag_id="uk-consume-pvlive-dayafter",
    description=__doc__,
    schedule="0 11 * * *",
    start_date=dt.datetime(2025, 3, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def pvlive_dayafter_consumer_dag() -> None:
    """Dag to download pvlive-dayafter data."""
    consume_pvlive_national = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-pvlive-dayafter-national",
        container_def=pvlive_consumer,
        env_overrides={
            "N_GSPS": "0",
            "INCLUDE_NATIONAL": "True",
            "REGIME": "day-after",
        },
        on_failure_callback=get_slack_message_callback(
            additional_message_context="This task is not critical for live services. ",
            urgency=Urgency.SUBCRITICAL,
        ),
    )

    consume_pvlive_gsps = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-pvlive-dayafter-gsps",
        container_def=pvlive_consumer,
        env_overrides={
            "N_GSPS": "342",
            "REGIME": "day-after",
        },
        on_failure_callback=get_slack_message_callback(
            additional_message_context="This task is not critical for live services. ",
            urgency=Urgency.SUBCRITICAL,
        ),
    )

    consume_pvlive_national >> consume_pvlive_gsps

    if env == "development":
        consume_pvlive_gsps_data_platform = EcsAutoRegisterRunTaskOperator(
            airflow_task_id="pvlive-dayafter-consumer-data-platform",
            container_def=pvlive_consumer_data_platform,
            env_overrides={
                "UK_PVLIVE_REGIME": "day-after",
            },
        )

        consume_pvlive_gsps_data_platform  # noqa: B018



pvlive_intraday_consumer_dag()
pvlive_dayafter_consumer_dag()
