"""DAG to calculate metrics from the forecast."""

import datetime as dt
import os
from datetime import timedelta

from airflow.decorators import dag

from airflow_dags.plugins.callbacks.slack import slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import ECSOperatorGen

env = os.getenv("ENVIRONMENT", "development")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

metrics_calculator = ECSOperatorGen(
    name="metrics",
    container_image="docker.io/openclimatefix/nowcasting_metrics",
    container_tag="1.2.21",
    container_env={
        "USE_PVNET_GSP_SUM": "true",
        "LOGLEVEL": "DEBUG",
    },
    container_secret_env={
        f"{env}/rds/forecast/": ["DB_URL"],
    },
    domain="uk",
    container_cpu=256,
    container_memory=512,
)

@dag(
    dag_id="uk-metrics",
    description=__doc__,
    schedule_interval="0 21 * * *",
    start_date=dt.datetime(2025, 3, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def metrics_dag() -> None:
    """Dag to download pvlive intraday data."""
    setup_op = metrics_calculator.setup_operator()
    teardown_op = metrics_calculator.teardown_operator()

    error_message: str = (
        "⚠️ The task {{ ti.task_id }} failed,"
        " but its ok. This task is not critical for live services. "
        "No out of hours support is required."
    )

    with teardown_op.as_teardown(setups=setup_op):

        calculate_metrics_op = metrics_calculator.run_task_operator(
            airflow_task_id="calculate-metrics",
            on_failure_callback=slack_message_callback(error_message),
        )

        calculate_metrics_op

metrics_dag()
