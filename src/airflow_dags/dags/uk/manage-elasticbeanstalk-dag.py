"""DAG to rotate the ec2 machine in elastic beanstalk instances."""

import datetime as dt
import os

from airflow.decorators import dag
from airflow.operators.latest_only import LatestOnlyOperator
from airflow.operators.python import PythonOperator

from airflow_dags.plugins.callbacks.slack import slack_message_callback
from airflow_dags.plugins.scripts.elastic_beanstalk import (
    scale_elastic_beanstalk_instance,
    terminate_any_old_instances,
)

env = os.getenv("ENVIRONMENT", "development")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}

elb_error_message = (
    "⚠️ The task {{ ti.task_id }} failed,"
    " but its ok. This task tried to reset the Elastic Beanstalk instances. "
    "No out of hours support is required."
)

names = [
    f"uk-{env}-airflow",
    f"uk-{env}-internal-ui",
    f"uk-{env}-nowcasting-api",
    f"uk-{env}-sites-api",
]


@dag(
    dag_id="uk-manage-elb",
    description=__doc__,
    schedule="0 0 1 * *",
    start_date=dt.datetime(2025, 3, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def elb_reset_dag() -> None:
    """Reset elastic beanstalk instances on a cadence."""
    latest_only = LatestOnlyOperator(task_id="latest_only")

    for name in names:
        number_of_instances = 2 if name == f"uk-{env}-nowcasting-api" else 1

        elb_2 = PythonOperator(
            task_id=f"scale_elb_2_{name}",
            python_callable=scale_elastic_beanstalk_instance,
            op_kwargs={
                "name": name,
                "number_of_instances": number_of_instances + 1,
                "sleep_seconds": 60 * 5,
            },
            max_active_tis_per_dag=2,
            on_failure_callback=slack_message_callback(elb_error_message),
        )

        elb_1 = PythonOperator(
            task_id=f"scale_elb_1_{name}",
            python_callable=scale_elastic_beanstalk_instance,
            op_kwargs={"name": name, "number_of_instances": number_of_instances, "days_limit": 3},
            max_active_tis_per_dag=2,
            on_failure_callback=slack_message_callback(elb_error_message),
        )

        if "api" in name:
            elb_terminate = PythonOperator(
                task_id=f"terminate_old_ec2_{name}",
                python_callable=terminate_any_old_instances,
                op_kwargs={
                    "name": name,
                    "sleep_seconds": 60 * 5,
                },
                max_active_tis_per_dag=2,
                on_failure_callback=slack_message_callback(elb_error_message),
            )
            latest_only >> elb_2 >> elb_terminate >> elb_1
        else:

            latest_only >> elb_2 >> elb_1


elb_reset_dag()
