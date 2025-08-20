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

from airflow_dags.plugins.callbacks.slack import get_task_link, slack_message_callback
from airflow_dags.plugins.operators.ecs_run_task_operator import (
    ContainerDefinition,
    EcsAutoRegisterRunTaskOperator,
)
from airflow_dags.plugins.scripts.s3 import extract_latest_zarr

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

sat_consumer = ContainerDefinition(
    name="satellite-consumer",
    container_image="ghcr.io/openclimatefix/satellite-consumer",
    container_tag="0.3.0",
    container_env={
        "LOGLEVEL": "DEBUG",
        "SATCONS_COMMAND": "consume",
        "SATCONS_ICECHUNK": "true",
        "SATCONS_SATELLITE": "rss",
        "SATCONS_VALIDATE": "true",
        "SATCONS_RESOLUTION": "3000",
        "SATCONS_RESCALE": "true",
        "SATCONS_WINDOW_MINS": "210",
        "SATCONS_NUM_WORKERS": "1",
        "SATCONS_CROP_REGION": "UK",
    },
    container_secret_env={
        f"{env}/data/satellite-consumer": [
            "EUMETSAT_CONSUMER_KEY",
            "EUMETSAT_CONSUMER_SECRET",
        ],
    },
    domain="uk",
    container_cpu=1024,
    container_memory=5120,
    container_storage=30,
)

def update_operator(cadence_mins: int) -> BashOperator:
    """BashOperator to update the API with the latest downloaded file."""
    if cadence_mins == 5:
        file: str = f"s3://nowcasting-sat-{env}/rss/data/latest.zarr.zip"
    elif cadence_mins == 15:
        file: str = f"s3://nowcasting-sat-{env}/odegree/data/latest.zarr.zip"
    url: str = "http://api-dev.quartz.solar" if env == "development" else "http://api.quartz.solar"
    command: str = (
        f'curl -X GET "{url}/v0/solar/GB/update_last_data?component=satellite&file={file}"'
    )
    return BashOperator(
        task_id=f"uk-satellite-update-{cadence_mins!s}min",
        bash_command=command,
    )


@dag(
    dag_id="uk-consume-sat",
    description=__doc__,
    schedule="*/5 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def sat_consumer_dag() -> None:
    """Dag to download and process satellite data from EUMETSAT."""
    latest_only_op = LatestOnlyOperator(task_id="latest-only")

    consume_rss_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-rss",
        container_def=sat_consumer,
        env_overrides={
            "SATCONS_TIME": "{{"
            + "(data_interval_start - macros.timedelta(minutes=210))"
            + ".strftime('%Y-%m-%dT%H:%M')"
            + "}}",
            "SATCONS_WORKDIR": f"s3://nowcasting-sat-{env}/rss",
        },
        task_concurrency=1,
    )
    extract_latest_rss_op = extract_latest_zarr(
        bucket=f"nowcasting-sat-{env}",
        prefix="rss/data/rss_uk3000m.icechunk",
        window_mins=210,
        cadence_mins=5,
    )

    consume_odegree_op = EcsAutoRegisterRunTaskOperator(
        airflow_task_id="consume-odegree",
        container_def=sat_consumer,
        trigger_rule=TriggerRule.ALL_FAILED,  # Only run if rss fails
        env_overrides={
            "SATCONS_SATELLITE": "odegree",
            "SATCONS_TIME": "{{" \
                            + "(data_interval_start - macros.timedelta(minutes=210))" \
                            + ".strftime('%Y-%m-%dT%H:%M')" \
                            + "}}",
            "SATCONS_WORKDIR": f"s3://nowcasting-sat-{env}/odegree",
        },
        on_failure_callback=slack_message_callback(
            f"⚠️🇬🇧 The task {get_task_link()} failed to collect odegree satellite data. "
            "The forecast will automatically move over to PVNET-ECMWF "
            "which doesn't need satellite data. "
            "The EUMETSAT status link for the RSS service (5 minute) is "
            "<https://masif.eumetsat.int/ossi/webpages/level3.html?ossi_level3_filename"
            "=seviri_rss_hr.json.html&ossi_level2_filename=seviri_rss.html|here> "
            "and the 0 degree (15 minute) which we use as a backup is "
            "<https://masif.eumetsat.int/ossi/webpages/level3.html?ossi_level3_filename"
            "=seviri_0deg_hr.json.html&ossi_level2_filename=seviri_0deg.html|here>. "
            "No out-of-hours support is required.",
        ),
    )

    extract_latest_odegree_op = extract_latest_zarr(
        bucket=f"nowcasting-sat-{env}",
        prefix="odegree/data/odegree_uk3000m.icechunk",
        window_mins=210,
        cadence_mins=15,
    )

    update_5min_op = update_operator(cadence_mins=5)
    update_15min_op = update_operator(cadence_mins=15)

    latest_only_op >> consume_rss_op >> extract_latest_rss_op >> update_5min_op
    consume_rss_op >> consume_odegree_op >> extract_latest_odegree_op >> update_15min_op



sat_consumer_dag()
