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

from airflow_dags.plugins.callbacks.slack import slack_message_callback
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
    container_tag="1.2.6",
    container_env={
        "LOGLEVEL": "DEBUG",
        "PVLIVE_DOMAIN_URL": "api.solar.sheffield.ac.uk",
        # api.pvlive.uk" is the new one, api.solar.sheffield.ac.uk is the old one
    },
    container_secret_env={
        f"{env}/rds/forecast/": ["DB_URL"],
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
            "N_GSPS": "317",
            "REGIME": "in-day",
        },
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed. "
            "This is needed for the adjuster in the Forecast."
            "No out of office hours support needed."
            "Its good to check <https://www.solar.sheffield.ac.uk/pvlive/|PV Live> "
            "to see if its working. ",
        ),
    )

    update_api_last_gsp_data = BashOperator(
        task_id="uk-gsp-lastdownloaded-api-update",
        bash_command=f"curl -X GET {url}/v0/solar/GB/update_last_data?component=gsp",
    )

    consume_pvlive_gsps >> update_api_last_gsp_data


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
    error_message: str = (
        "⚠️ The task {{ ti.task_id }} failed,"
        " but its ok. This task is not critical for live services. "
        "No out of hours support is required."
    )

    consume_pvlive_national = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-pvlive-dayafter-national",
        container_def=pvlive_consumer,
        env_overrides={
            "N_GSPS": "0",
            "INCLUDE_NATIONAL": "True",
            "REGIME": "day-after",
        },
        on_failure_callback=slack_message_callback(error_message),
    )

    consume_pvlive_gsps = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-pvlive-dayafter-gsps",
        container_def=pvlive_consumer,
        env_overrides={
            "N_GSPS": "317",
            "REGIME": "day-after",
        },
        on_failure_callback=slack_message_callback(error_message),
    )

    consume_pvlive_national >> consume_pvlive_gsps


pvlive_intraday_consumer_dag()
pvlive_dayafter_consumer_dag()
