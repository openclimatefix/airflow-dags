"""General checks on Uk National/GSP API."""

import datetime as dt
import logging
import os

from airflow.decorators import dag
from airflow.operators.python import PythonOperator

from airflow_dags.plugins.callbacks.slack import slack_message_callback
from airflow_dags.plugins.scripts.api_checks import (
    call_api,
    check_key_in_data,
    check_len_ge,
    get_bearer_token_from_auth0,
)

logger = logging.getLogger(__name__)

env = os.getenv("ENVIRONMENT", "development")
base_url = "http://api-dev.quartz.energy" if env == "development" else "http://api.quartz.energy"


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    "retries": 1,
    "retry_delay": dt.timedelta(minutes=1),
    "max_active_runs": 10,
    "concurrency": 10,
    "max_active_tasks": 10,
}


def check_api_is_up() -> None:
    """Check the api is up."""
    full_url = f"{base_url}/openapi.json"
    call_api(url=full_url)


def check_api_status() -> None:
    """Check the status."""
    full_url = f"{base_url}/health"
    call_api(url=full_url)


def check_sites(access_token: str) -> None:
    """Check can get sites."""
    full_url = f"{base_url}/sites"

    data = call_api(url=full_url, access_token=access_token)

    # should have at least 1 site
    check_len_ge(data, 1)

    # check that the data has the expected keys
    check_key_in_data(data[0], "site_uuid")


def check_forecast(access_token: str) -> None:
    """Check the forecast."""
    sites = call_api(url=f"{base_url}/sites", access_token=access_token)
    for site in sites:

        site_uuid = site["site_uuid"]

        full_url = f"{base_url}/sites/{site_uuid}/forecast"

        forecast_values = call_api(url=full_url, access_token=access_token)

        # should have data point for 2 days in the past + 36 hours in the future
        # date is in 30 min intervals
        check_len_ge(forecast_values, 2 * 24 * 2 + 30 * 2)
        check_key_in_data(forecast_values[0], "Time")
        check_key_in_data(forecast_values[0], "PowerKW")


def check_generation(access_token: str) -> None:
    """Check the forecast."""
    sites = call_api(url=f"{base_url}/sites", access_token=access_token)
    for site in sites:
        site_uuid = site["site_uuid"]

        full_url = f"{base_url}/sites/{site_uuid}/generation"

        pv_actual_values = call_api(url=full_url, access_token=access_token)

        # Make sure there is atleast one datapoint
        check_len_ge(pv_actual_values, 1)
        check_key_in_data(pv_actual_values[0], "Time")
        check_key_in_data(pv_actual_values[0], "PowerKW")

        # only check this for non ruvnl sites
        if "ruvnl" not in site["client_site_name"]:

            # check that the last datetime is within the last hour
            last_datetime = max([d["Time"] for d in pv_actual_values])
            # convert last_datetime to a datetime object
            last_datetime = dt.datetime.fromisoformat(last_datetime).replace(tzinfo=dt.UTC)
            if dt.datetime.now(dt.UTC) - last_datetime > dt.timedelta(hours=1):
                raise ValueError(
                    f"Last datetime {last_datetime} is more than 1 hour old. "
                    "This is likely because the API has not been updated with the latest data."
                    f"This is for {site=}",
                )


@dag(
    dag_id="india-api-check",
    description=__doc__,
    schedule="0 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def api_site_check() -> None:
    """Dag to check API."""
    _ = PythonOperator(
        task_id="check-api",
        python_callable=check_api_is_up,
    )

    _ = PythonOperator(
        task_id="check-api-health",
        python_callable=check_api_status,
    )

    get_bearer_token = PythonOperator(
        task_id="check-api-get-bearer-token",
        python_callable=get_bearer_token_from_auth0,
    )

    access_token_str = (
        "{{ task_instance.xcom_pull(task_ids='check-api-get-bearer-token') }}"  # noqa: S105
    )
    sites = PythonOperator(
        task_id="check-sites",
        python_callable=check_forecast,
        op_kwargs={"access_token": access_token_str},
    )

    forecast = PythonOperator(
        task_id="check-forecast",
        python_callable=check_forecast,
        op_kwargs={"access_token": access_token_str},
    )

    generation = PythonOperator(
        task_id="check-generation",
        python_callable=check_forecast,
        op_kwargs={"access_token": access_token_str},
    )

    if_any_task_failed = PythonOperator(
        task_id="api-uk-national-gsp-check-if-any-task-failed",
        python_callable=lambda: None,
        trigger_rule="one_failed",
        on_success_callback=slack_message_callback(
            "⚠️🇮🇳 One of the API checks has failed. "
            "See which ones have failed on airflow, to help debug the issue. "
            "No out-of-hours support is required.",
        ),
    )

    (
        get_bearer_token
        >> sites
        >> [
            forecast,
            generation,
        ]
    )

    [
        sites,
        forecast,
        generation,
    ] >> if_any_task_failed


api_site_check()

if __name__ == "__main__":
    # Run all the function, Manual UAT
    # This can be useful after the API is deployed
    check_api_is_up()
    bearer_token = get_bearer_token_from_auth0()
    check_sites(bearer_token)
    check_forecast(bearer_token)
    check_generation(bearer_token)
