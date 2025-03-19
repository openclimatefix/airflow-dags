"""Dag to download and process satellite data from EUMETSAT.

Consists of two tasks made from the same ECS operator,
one for RSS data and one for Odegree data.
The 0degree data task only runs if the RSS data task fails.
"""

import datetime as dt
import os

from airflow.decorators import dag
from airflow.operators.bash import BashOperator
from airflow.operators.latest_only import LatestOnlyOperator
from airflow.utils.trigger_rule import TriggerRule

from airflow_dags.plugins.callbacks.slack import slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import ECSOperatorGen

env = os.getenv("ENVIRONMENT", "development")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 0,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 5,
    "concurrency": 5,
    "max_active_tasks": 10,
    "execution_timeout": dt.timedelta(minutes=45),
}

sat_consumer = ECSOperatorGen(
    name="satellite-consumer",
    container_image="ghcr.io/openclimatefix/satellite-consumer",
    container_tag="0.1.7",
    container_env={
        "LOGLEVEL": "DEBUG",
        "SATCONS_COMMAND": "consume",
        "SATCONS_SATELLITE": "rss",
        "SATCONS_VALIDATE": "true",
        "SATCONS_RESCALE": "true",
        "SATCONS_WINDOW_MINS": "210",
        "SATCONS_CONSUME_MISSING": "true",
    },
    container_secret_env={
        "development/data/satellite-consumer": [
            "EUMETSAT_CONSUMER_KEY", "EUMETSAT_CONSUMER_SECRET",
        ],
    },
    domain="uk",
    container_memory=4096,
    container_storage=30,
)

def update_operator(cadence_mins: int) -> BashOperator:
    """BashOperator to update the API with the latest downloaded file."""
    file: str = f"s3://nowcasting-sat-{env}/testdata/latest.zarr.zip"
    url: str = "http://api-dev.quartz.solar" if env == "development" else "http://api.quartz.solar"
    command: str = (
        f'curl -X GET '
        f'"{url}/v0/solar/GB/update_last_data?component=satellite&file={file}"'
    )
    return BashOperator(
        task_id=f"uk-satellite-update-{cadence_mins!s}min",
        bash_command=command,
    )

@dag(
    dag_id="uk-satellite-consumer",
    description=__doc__,
    schedule_interval="*/5 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def sat_consumer_dag() -> None:
    """Dag to download and process satellite data from EUMETSAT."""
    setup_op = sat_consumer.setup_operator()
    teardown_op = sat_consumer.teardown_operator()

    with teardown_op.as_teardown(setups=setup_op):
        latest_op = LatestOnlyOperator(task_id="determine_latest_run")

        consume_single_rss_op = sat_consumer.run_task_operator(
            airflow_task_id="satellite-consumer-rss",
            env_overrides={
                "SATCONS_TIME": "{{ data_interval_start }}",
                "SATCONS_WORKDIR": f"s3://nowcasting-sat-{env}/testdata/rss",
            },
        )

        merge_rss_op = sat_consumer.run_task_operator(
            airflow_task_id="satellite-consumer-merge-rss-catchup",
            trigger_rule=TriggerRule.ALL_FAILED,
            env_overrides={
                "SATCONS_COMMAND": "merge",
                "SATCONS_TIME": "{{ data_interval_start }}",
                "SATCONS_WORKDIR": f"s3://nowcasting-sat-{env}/testdata/rss",
            },
        )

        consume_single_odegree_op = sat_consumer.run_task_operator(
            airflow_task_id="satellite-consumer-odegree",
            trigger_rule=TriggerRule.ALL_FAILED, # Only run if rss fails
            env_overrides={
                "SATCONS_SATELLITE": "odegree",
                "SATCONS_TIME": "{{ data_interval_start }}",
                "SATCONS_WORKDIR": f"s3://nowcasting-sat-{env}/testdata/odegree",
            },
        )

        merge_odegree_op = sat_consumer.run_task_operator(
            airflow_task_id="satellite-consumer-merge-odegree-catchup",
            env_overrides={
                "SATCONS_COMMAND": "merge",
                "SATCONS_SATELLITE": "odegree",
                "SATCONS_TIME": "{{ data_interval_start }}",
                "SATCONS_WORKDIR": f"s3://nowcasting-sat-{env}/testdata/odegree",
            },
            on_failure_callback=slack_message_callback(
                "⚠️ The task {{ ti.task_id }} failed to collect odegree satellite data. "
                "The forecast will automatically move over to PVNET-ECMWF "
                "which doesn't need satellite data. "
                "Forecast quality may be impacted, "
                "but no out-of-hours support is required. "
                "Please log in an incident log. ",
            ),
        )


        latest_op >> consume_single_rss_op
        consume_single_rss_op >> merge_rss_op 

        consume_single_rss_op >> consume_single_odegree_op
        consume_single_odegree_op >> merge_odegree_op

sat_consumer_dag()

