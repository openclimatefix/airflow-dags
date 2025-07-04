"""DAG to consume data from RUVNL."""

import datetime as dt
import os

from airflow.decorators import dag
from airflow.operators.latest_only import LatestOnlyOperator

from airflow_dags.plugins.callbacks.slack import (
    slack_message_callback_no_action_required,
)
from airflow_dags.plugins.operators.ecs_run_task_operator import (
    ContainerDefinition,
    EcsAutoRegisterRunTaskOperator,
)

env = os.getenv("ENVIRONMENT", "development")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 0,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
    "execution_timeout": dt.timedelta(minutes=45),
}

ruvnl_consumer = ContainerDefinition(
    name="ruvnl-consumer",
    container_image="docker.io/openclimatefix/ruvnl_consumer_app",
    container_tag="0.1.20",
    container_command=["--write-to-db"],
    container_secret_env={
        f"{env}/rds/indiadb": ["DB_URL"],
    },
    container_cpu=256,
    container_memory=512,
    domain="india",
)


@dag(
    dag_id="india-consume-ruvnl",
    description=__doc__,
    schedule="*/3 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def ruvnl_consumer_dag() -> None:
    """DAG to download data from RUVNL."""
    latest_only_op = LatestOnlyOperator(task_id="latest_only")

    consume_ruvnl_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-runvl",
        container_def=ruvnl_consumer,
        on_failure_callback=slack_message_callback_no_action_required,
        max_active_tis_per_dag=10,
    )

    latest_only_op >> consume_ruvnl_op


ruvnl_consumer_dag()
