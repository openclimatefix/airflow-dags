"""General checks on Uk Site API."""

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
base_url = (
    "http://api-site-dev.quartz.solar" if env == "development" else "http://api-site.quartz.solar"
)


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
    full_url = f"{base_url}/"
    call_api(url=full_url)


def check_api_status() -> None:
    """Check the status."""
    full_url = f"{base_url}/api_status"
    call_api(url=full_url)


def check_sites(access_token: str) -> None:
    """Check can get sites."""
    full_url = f"{base_url}/sites"

    data = call_api(url=full_url, access_token=access_token)

    # should have at least 1 site
    check_len_ge(data["site_list"], 1)

    # check that the data has the expected keys
    check_key_in_data(data["site_list"][0], "site_uuid")


def check_forecast(access_token: str) -> None:
    """Check the forecast."""
    sites = call_api(url=f"{base_url}/sites", access_token=access_token)
    for site in sites["site_list"]:

        site_uuid = site["site_uuid"]

        full_url = f"{base_url}/sites/{site_uuid}/pv_forecast"

        data = call_api(url=full_url, access_token=access_token)

        check_key_in_data(data, "forecast_values")
        forecast_values = data["forecast_values"]

        # should have data point for 2 days in the past + 36 hours in the future.
        # We just check for the next 30 hours though
        # date is in 30 min intervals
        check_len_ge(forecast_values, 2 * 24 * 2 + 30 * 2)
        check_key_in_data(forecast_values[0], "target_datetime_utc")
        check_key_in_data(forecast_values[0], "expected_generation_kw")


@dag(
    dag_id="uk-api-site-check",
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
        task_id="check-api-status",
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

    if_any_task_failed = PythonOperator(
        task_id="api-uk-national-gsp-check-if-any-task-failed",
        python_callable=lambda: None,
        trigger_rule="one_failed",
        on_success_callback=slack_message_callback(
            "⚠️ 🇬🇧 {{ ti.dag_id }} One of the API Site checks has failed. "
            "See which ones have failed on airflow, to help debug the issue. "
            "No out-of-hours support is required.",
        ),
    )

    (
        get_bearer_token
        >> sites
        >> [
            forecast,
        ]
    )

    [
        sites,
        forecast,
    ] >> if_any_task_failed


api_site_check()

if __name__ == "__main__":
    # Run all the function, Manual UAT
    # This can be useful after the API is deployed
    check_api_is_up()
    bearer_token = get_bearer_token_from_auth0()
    check_sites(bearer_token)
    check_forecast(bearer_token)
