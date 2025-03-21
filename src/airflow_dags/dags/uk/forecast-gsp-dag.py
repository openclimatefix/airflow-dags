import os
from datetime import UTC, datetime, timedelta

from airflow import DAG
from airflow.operators.latest_only import LatestOnlyOperator
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator

from airflow_dags.plugins.callbacks.slack import slack_message_callback

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime.now(tz=UTC) - timedelta(hours=1.5),
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

env = os.getenv("ENVIRONMENT", "development")
subnet = os.getenv("ECS_SUBNET")
security_group = os.getenv("ECS_SECURITY_GROUP")
cluster = f"Nowcasting-{env}"


# Tasks can still be defined in terraform, or defined here
forecast_pvnet_error_message = (
    "❌ The task {{ ti.task_id }} failed. This means one or more of the critical PVNet models have "
    "failed to run. We have about 6 hours before the blend services need this. "
    "Please see run book for appropriate actions."
)


forecast_pvnet_da_error_message = (
    "❌ The task {{ ti.task_id }} failed. "
    "This would ideally be fixed before for DA actions at 09.00. "
    "Please see run book for appropriate actions."
)

forecast_blend_error_message = (
    "❌ The task {{ ti.task_id }} failed."
    "The blending of forecast has failed. "
    "Please see run book for appropriate actions. "
)

region = "uk"

with DAG(
    f"{region}-gsp-forecast-pvnet-2",
    schedule_interval="15,45 * * * *",
    default_args=default_args,
    concurrency=10,
    max_active_tasks=10,
) as dag:
    dag.doc_md = "Get PV data"

    latest_only = LatestOnlyOperator(task_id="latest_only")

    forecast = EcsRunTaskOperator(
        task_id=f"{region}-gsp-forecast-pvnet-2",
        task_definition="forecast_pvnet",
        cluster=cluster,
        overrides={},
        launch_type="FARGATE",
        network_configuration={
            "awsvpcConfiguration": {
                "subnets": [subnet],
                "securityGroups": [security_group],
                "assignPublicIp": "ENABLED",
            },
        },
        task_concurrency=10,
        on_failure_callback=slack_message_callback(forecast_pvnet_error_message),
        awslogs_group="/aws/ecs/forecast/forecast_pvnet",
        awslogs_stream_prefix="streaming/forecast_pvnet-forecast",
        awslogs_region="eu-west-1",
    )

    forecast_blend = EcsRunTaskOperator(
        task_id=f"{region}-forecast-blend-pvnet-2",
        task_definition="forecast_blend",
        cluster=cluster,
        overrides={},
        launch_type="FARGATE",
        network_configuration={
            "awsvpcConfiguration": {
                "subnets": [subnet],
                "securityGroups": [security_group],
                "assignPublicIp": "ENABLED",
            },
        },
        task_concurrency=10,
        on_failure_callback=slack_message_callback(forecast_blend_error_message),
        trigger_rule="all_done",
        awslogs_group="/aws/ecs/blend/forecast_blend",
        awslogs_stream_prefix="streaming/forecast_blend-blend",
        awslogs_region="eu-west-1",
    )

    latest_only >> forecast >> forecast_blend


with DAG(
    f"{region}-gsp-forecast-pvnet-day-ahead",
    schedule_interval="45 * * * *",
    default_args=default_args,
    concurrency=10,
    max_active_tasks=10,
) as dag:
    dag.doc_md = "Run Forecast day ahead"

    latest_only = LatestOnlyOperator(task_id="latest_only")

    forecast_pvnet_day_ahead = EcsRunTaskOperator(
        task_id=f"{region}-gsp-forecast-pvnet-day-ahead",
        task_definition="forecast_pvnet_day_ahead",
        cluster=cluster,
        overrides={},
        launch_type="FARGATE",
        network_configuration={
            "awsvpcConfiguration": {
                "subnets": [subnet],
                "securityGroups": [security_group],
                "assignPublicIp": "ENABLED",
            },
        },
        task_concurrency=10,
        on_failure_callback=slack_message_callback(forecast_pvnet_da_error_message),
        awslogs_group="/aws/ecs/forecast/forecast_pvnet_day_ahead",
        awslogs_stream_prefix="streaming/forecast_pvnet_day_ahead-forecast",
        awslogs_region="eu-west-1",
    )

    forecast_blend = EcsRunTaskOperator(
        task_id=f"{region}-forecast-blend",
        task_definition="forecast_blend",
        cluster=cluster,
        overrides={},
        launch_type="FARGATE",
        network_configuration={
            "awsvpcConfiguration": {
                "subnets": [subnet],
                "securityGroups": [security_group],
                "assignPublicIp": "ENABLED",
            },
        },
        task_concurrency=10,
        on_failure_callback=slack_message_callback(forecast_blend_error_message),
        awslogs_group="/aws/ecs/blend/forecast_blend",
        awslogs_stream_prefix="streaming/forecast_blend-blend",
        awslogs_region="eu-west-1",
    )

    latest_only >> forecast_pvnet_day_ahead >> forecast_blend
