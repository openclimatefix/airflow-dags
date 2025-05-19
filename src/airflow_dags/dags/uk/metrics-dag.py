"""DAG to calculate metrics from the forecast."""

import datetime as dt
import os
from datetime import timedelta

from airflow.decorators import dag

from airflow_dags.plugins.callbacks.slack import slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import (
    ContainerDefinition,
    EcsAutoRegisterRunTaskOperator,
)

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

metrics_calculator = ContainerDefinition(
    name="metrics",
    container_image="docker.io/openclimatefix/nowcasting_metrics",
    container_tag="1.2.26",
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
    dag_id="uk-analysis-metrics",
    description="DAG to calculate metrics from the forecast.",
    schedule="0 21 * * *",  # 21:00 UTC
    start_date=dt.datetime(2025, 3, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def metrics_dag() -> None:
    """Run the metrics DAG."""
    EcsAutoRegisterRunTaskOperator(
        airflow_task_id="calculate-metrics",
        container_def=metrics_calculator,
        env_overrides={
            "USE_PVNET_GSP_SUM": "true",
            "RUN_METRICS": "true",  # Explicitly enable metrics
            "RUN_ME": "false",  # Disable ME calculations
            "LOGLEVEL": "DEBUG",
        },
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed,"
            " but its ok. This task is not critical for live services. "
            "No out of hours support is required.",
        ),
    )


@dag(
    dag_id="uk-analysis-metrics-me",
    description="DAG to run ME calculations for the adjuster.",
    schedule="0 20 * * *",  # 20:00 UTC (1 hour earlier)
    start_date=dt.datetime(2025, 3, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def me_dag() -> None:
    """Run the ME DAG, used by the adjuster."""
    EcsAutoRegisterRunTaskOperator(
        airflow_task_id="calculate-metrics-me",
        container_def=metrics_calculator,
        env_overrides={
            "USE_PVNET_GSP_SUM": "true",
            "RUN_METRICS": "false",  # Disable metrics
            "RUN_ME": "true",  # Enable ME calculations
            "LOGLEVEL": "DEBUG",
        },
        on_failure_callback=slack_message_callback(
            "⚠️ The task {{ ti.task_id }} failed,"
            " but its ok. This task is not critical for live services. "
            "No out of hours support is required.",
        ),
    )


# Register both DAGs
metrics_dag()
me_dag()
