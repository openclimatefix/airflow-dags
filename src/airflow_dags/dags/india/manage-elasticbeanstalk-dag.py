"""DAG to rotate the ec2 machine in elastic beanstalk instances."""

import datetime as dt
import os

from airflow.decorators import dag
from airflow.operators.latest_only import LatestOnlyOperator
from airflow.operators.python import PythonOperator

from airflow_dags.plugins.callbacks.slack import get_task_link, slack_message_callback
from airflow_dags.plugins.scripts.elastic_beanstalk import scale_elastic_beanstalk_instance

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
    f"⚠️🇮🇳 The {get_task_link()} failed,"
    " but its ok. This task tried to reset the Elastic Beanstalk instances. "
    "No out of hours support is required."
)

names = [
    f"india-{env}-airflow",
    f"india-{env}-analysis-dashboard",
    f"india-{env}-india-api",
]


@dag(
    dag_id="india-manage-elb-reset",
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

        elb_2 = PythonOperator(
            task_id=f"scale_elb_2_{name}",
            python_callable=scale_elastic_beanstalk_instance,
            op_kwargs={"name": name, "number_of_instances": 2, "sleep_seconds": 60 * 5},
            max_active_tis_per_dag=2,
            on_failure_callback=slack_message_callback(elb_error_message),
        )

        elb_1 = PythonOperator(
            task_id=f"scale_elb_1_{name}",
            python_callable=scale_elastic_beanstalk_instance,
            op_kwargs={"name": name, "number_of_instances": 1},
            max_active_tis_per_dag=2,
            on_failure_callback=slack_message_callback(elb_error_message),
        )

        latest_only >> elb_2 >> elb_1


elb_reset_dag()
