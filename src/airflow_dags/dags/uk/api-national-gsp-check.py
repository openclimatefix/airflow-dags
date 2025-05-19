"""General checks on Uk National/GSP API."""
import datetime as dt
import json
import logging
import os
import time

import requests
from airflow.decorators import dag
from airflow.operators.python import PythonOperator

from airflow_dags.plugins.callbacks.slack import slack_message_callback

logger = logging.getLogger(__name__)

env = os.getenv("ENVIRONMENT", "development")
base_url = "http://api-dev.quartz.solar" if env == "development" else "http://api.quartz.solar"
username = os.getenv("AUTH0_USERNAME")
password = os.getenv("AUTH0_PASSWORD")
client_id = os.getenv("AUTH0_CLIENT_ID")
domain = os.getenv("AUTH0_DOMAIN")
audience = os.getenv("AUTH0_AUDIENCE")

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


def check_len_ge(data: list, min_len: int) -> None:
    """Check the length of the data is greater than or equal to min_len."""
    if len(data) < min_len:
        raise ValueError(f"Data length {len(data)} is less than {min_len}." f"The data is {data}.")


def check_len_equal(data: list, equal_len: int) -> None:
    """Check the length of the data is greater than or equal to min_len."""
    if len(data) != equal_len:
        raise ValueError(
            f"Data length {len(data)} is not equal {equal_len}." f"The data is {data}.",
        )


def check_key_in_data(data: dict, key: str) -> None:
    """Check the key is in the data."""
    if key not in data:
        raise ValueError(f"Key {key} not in data {data}.")


def get_bearer_token_from_auth0() -> str:
    """Get bearer token from Auth0."""
    # # if we don't have a token, or its out of date, then lets get a new one
    # # Note: need to make this user on dev and production auth0

    url = f"https://{domain}/oauth/token"
    header = {"content-type": "application/json"}
    data = json.dumps(
        {
            "client_id": client_id,
            "username": username,
            "password": password,
            "grant_type": "password",
            "audience": audience,
        },
    )
    logger.info("Getting bearer token")
    r = requests.post(url, data=data, headers=header, timeout=30)
    access_token = r.json()["access_token"]

    logger.info("Got bearer token")
    return access_token


def call_api(url: str, access_token: str | None = None) -> dict | list:
    """General function to call the API."""
    logger.info(f"Checking: {url}")

    headers = {"Authorization": "Bearer " + access_token} if access_token else {}

    t = time.time()
    response = requests.get(url, headers=headers, timeout=30)
    logger.info(f"API call took {time.time() - t} seconds")

    if response.status_code != 200:
        raise Exception(
            f"API call failed calling {url} "
            f"with status code {response.status_code},"
            f" message {response.text}",
        )

    return response.json()


def check_api_is_up() -> None:
    """Check the api is up."""
    full_url = f"{base_url}/"
    call_api(url=full_url)


def check_api_status() -> None:
    """Check the status."""
    full_url = f"{base_url}/v0/solar/GB/status"
    call_api(url=full_url)


def check_national_forecast(access_token: str, horizon_minutes: int | None = None) -> None:
    """Check the national forecast."""
    full_url = f"{base_url}/v0/solar/GB/national/forecast?"
    if horizon_minutes:
        full_url += f"forecast_horizon_minutes={horizon_minutes}"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for 2 days in the past + 36 hours in the future
    # date is in 30 min intervals
    check_len_ge(data, 2 * 24 * 2 + 30 * 2)
    check_key_in_data(data[0], "targetTime")
    check_key_in_data(data[0], "expectedPowerGenerationMegawatts")


def check_national_forecast_include_metadata(
    access_token: str,
    horizon_minutes: int | None = None,
) -> None:
    """Check the national forecast with include_metadata=true."""
    full_url = f"{base_url}/v0/solar/GB/national/forecast?include_metadata=true"
    if horizon_minutes:
        full_url += f"forecast_horizon_minutes={horizon_minutes}"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for 2 days in the past + 36 hours in the future
    # date is in 30 min intervals
    check_len_ge(data["forecastValues"], 2 * 24 * 2 + 30 * 2)
    check_key_in_data(data["forecastValues"][0], "targetTime")
    check_key_in_data(data["forecastValues"][0], "expectedPowerGenerationMegawatts")


def check_national_pvlive(access_token: str) -> None:
    """Check the national pvlive."""
    full_url = f"{base_url}/v0/solar/GB/national/pvlive"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for 2 days in the past, maybe the last one isnt in yet
    # We could get more precise with this check
    check_len_ge(data, 2 * 24 * 2 - 1)
    check_key_in_data(data[0], "datetimeUtc")
    check_key_in_data(data[0], "solarGenerationKw")


def check_national_pvlive_day_after(access_token: str) -> None:
    """Check the national pvlive with regime=day-after."""
    full_url = f"{base_url}/v0/solar/GB/national/pvlive?regime=day-after"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for more than 12 hours in the past,
    # This is because the data is delayed
    # we could get more precise with this check
    check_len_ge(data, 2 * 12)
    check_key_in_data(data[0], "datetimeUtc")
    check_key_in_data(data[0], "solarGenerationKw")


def check_gsp_forecast_all_compact_false(access_token: str) -> None:
    """Check the GSP forecast all with compact=false."""
    full_url = f"{base_url}/v0/solar/GB/gsp/forecast/all/?compact=false&gsp_ids=1,2,3"
    data = call_api(url=full_url, access_token=access_token)
    logger.debug(data)

    # 36 hours in the future, but just look at 30 hours
    # date is in 30 min intervals
    check_len_equal(data["forecasts"], 3)
    check_key_in_data(data["forecasts"][0], "forecastValues")
    check_len_ge(data["forecasts"][0]["forecastValues"], 2 * 30)


def check_gsp_forecast_all(access_token: str) -> None:
    """Check the GSP forecast all."""
    full_url = f"{base_url}/v0/solar/GB/gsp/forecast/all/?compact=true"
    data = call_api(url=full_url, access_token=access_token)
    logger.debug(data)

    # 36 hours in the future, but just look at 30 hours
    # date is in 30 min intervals
    check_len_ge(data, 2 * 30)
    check_key_in_data(data[0], "datetimeUtc")
    check_key_in_data(data[0], "forecastValues")
    check_len_ge(data[0]["forecastValues"], 317)


def check_gsp_forecast_all_start_and_end(access_token: str) -> None:
    """Check the GSP forecast all with start and end datetime."""
    # -2 days to now
    now = dt.datetime.now(tz=dt.UTC)
    start_datetime = now - dt.timedelta(days=2)
    start_datetime_str = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")
    end_datetime = now
    end_datetime_str = end_datetime.strftime("%Y-%m-%dT%H:%M:%S")

    full_url = (
        f"{base_url}/v0/solar/GB/gsp/forecast/all/?compact=true"
        f"&start_datetime_utc={start_datetime_str}&end_datetime_utc={end_datetime_str}"
    )
    data = call_api(url=full_url, access_token=access_token)
    logger.info(data)

    # 2 days in the past
    # date is in 30 min intervals
    check_len_ge(data, 2 * 24 * 2)
    check_key_in_data(data[0], "datetimeUtc")
    check_key_in_data(data[0], "forecastValues")
    check_len_ge(data[0]["forecastValues"], 317)

    first_datetime = dt.datetime.strptime(data[0]["datetimeUtc"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.UTC,
    )
    last_datetime = dt.datetime.strptime(data[-1]["datetimeUtc"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.UTC,
    )

    if not (start_datetime + dt.timedelta(hours=0.5) >= first_datetime >= start_datetime):
        raise Exception(
            f"{first_datetime} is not in the range {start_datetime} ",
            f"to {start_datetime + dt.timedelta(hours=0.5)}",
        )
    if not (end_datetime >= last_datetime >= end_datetime - dt.timedelta(hours=1)):
        raise Exception(
            f"{last_datetime} is not in the range ",
            f"{end_datetime - dt.timedelta(hours=1)} to {end_datetime}",
        )


def check_gsp_forecast_all_one_datetime(access_token: str) -> None:
    """Check the GSP forecast all with one datetime."""
    # now
    start_datetime = dt.datetime.now(tz=dt.UTC)
    start_datetime_str = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")
    end_datetime = start_datetime + dt.timedelta(hours=0.5)
    end_datetime_str = end_datetime.strftime("%Y-%m-%dT%H:%M:%S")

    full_url = (
        f"{base_url}/v0/solar/GB/gsp/forecast/all/?compact=true"
        f"&start_datetime_utc={start_datetime_str}&end_datetime_utc={end_datetime_str}"
    )
    data = call_api(url=full_url, access_token=access_token)
    logger.info(data)

    # Just one datetime
    check_len_ge(data, 1)
    check_key_in_data(data[0], "datetimeUtc")
    check_key_in_data(data[0], "forecastValues")
    check_len_ge(data[0]["forecastValues"], 317)

    first_datetime = dt.datetime.strptime(data[0]["datetimeUtc"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.UTC,
    )
    last_datetime = dt.datetime.strptime(data[-1]["datetimeUtc"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.UTC,
    )

    if not (start_datetime + dt.timedelta(hours=0.5) >= first_datetime >= start_datetime):
        raise Exception(
            f"{first_datetime} is not in the range {start_datetime} ",
            f"to {start_datetime + dt.timedelta(hours=0.5)}",
        )
    if not (end_datetime >= last_datetime >= end_datetime - dt.timedelta(hours=1)):
        raise Exception(
            f"{last_datetime} is not in the range ",
            f"{end_datetime - dt.timedelta(hours=1)} to {end_datetime}",
        )


def check_gsp_forecast_one(access_token: str, horizon_minutes: int | None = None) -> None:
    """Check the GSP forecast one."""
    full_url = f"{base_url}/v0/solar/GB/gsp/1/forecast/"
    if horizon_minutes:
        full_url += f"?forecast_horizon_minutes={horizon_minutes}"
    data = call_api(url=full_url, access_token=access_token)

    # 2 days in the past + 36 hours in the future, but just look at 30 hours
    # date is in 30 min intervals
    check_len_ge(data, 2 * 24 * 2 + 2 * 30)
    check_key_in_data(data[0], "targetTime")
    check_key_in_data(data[0], "expectedPowerGenerationMegawatts")


def check_gsp_pvlive_all(access_token: str) -> None:
    """Check the GSP pvlive all."""
    full_url = f"{base_url}/v0/solar/GB/gsp/pvlive/all/"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for 2 days in the past, maybe the last one isnt in yet
    # date is in 30 min intervals
    N = 24 * 2 * 2 - 1
    check_len_ge(data, 317)
    check_key_in_data(data[0], "gspYields")
    check_key_in_data(data[0]["gspYields"][0], "datetimeUtc")
    check_key_in_data(data[0]["gspYields"][0], "solarGenerationKw")
    check_len_ge(data[0]["gspYields"], N)


def check_gsp_pvlive_all_compact(access_token: str) -> None:
    """Check the GSP pvlive all."""
    full_url = f"{base_url}/v0/solar/GB/gsp/pvlive/all/?compact=true"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for 2 days in the past, maybe the last one isnt in yet
    # date is in 30 min intervals
    N = 24 * 2 * 2 - 1
    check_len_ge(data, N)
    check_key_in_data(data[0], "datetimeUtc")
    check_key_in_data(data[0], "generationKwByGspId")
    check_key_in_data(data[0]["generationKwByGspId"], "1")


def check_gsp_pvlive_one(access_token: str) -> None:
    """Check the GSP pvlive one."""
    full_url = f"{base_url}/v0/solar/GB/gsp/1/pvlive/"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for 2 days in the past, maybe the last one isnt in yet
    # date is in 30 min intervals
    N = 24 * 2 * 2 - 1
    check_len_ge(data, N)
    check_key_in_data(data[0], "datetimeUtc")
    check_key_in_data(data[0], "solarGenerationKw")


def check_gsp_pvlive_one_day_after(access_token: str) -> None:
    """Check the GSP pvlive one with regime=day-after."""
    full_url = f"{base_url}/v0/solar/GB/gsp/1/pvlive?regime=day-after"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for more than 12 hours in the past,
    # This is because the data is delayed
    N = 12 * 2
    check_len_ge(data, N)
    check_key_in_data(data[0], "datetimeUtc")
    check_key_in_data(data[0], "solarGenerationKw")


@dag(
    dag_id="uk-api-national-gsp-check",
    description=__doc__,
    schedule="0 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def api_national_gsp_check() -> None:
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
    national_forecast = PythonOperator(
        task_id="check-api-national-forecast",
        python_callable=check_national_forecast,
        op_kwargs={"access_token": access_token_str},
    )

    national_forecast_include_metadata = PythonOperator(
        task_id="check-api-national-forecast-include-metadata",
        python_callable=check_national_forecast_include_metadata,
        op_kwargs={"access_token": access_token_str},
    )

    national_generation = PythonOperator(
        task_id="check-api-national-pvlive",
        python_callable=check_national_pvlive,
        op_kwargs={"access_token": access_token_str},
    )

    national_generation_day_after = PythonOperator(
        task_id="check-api-national-pvlive-day-after",
        python_callable=check_national_pvlive_day_after,
        op_kwargs={"access_token": access_token_str},
    )

    gsp_forecast_all = PythonOperator(
        task_id="check-api-gsp-forecast-all",
        python_callable=check_gsp_forecast_all,
        op_kwargs={"access_token": access_token_str},
    )

    gsp_forecast_all_compact_false = PythonOperator(
        task_id="check-api-gsp-forecast-all-compact-false",
        python_callable=check_gsp_forecast_all_compact_false,
        op_kwargs={"access_token": access_token_str},
    )

    gsp_forecast_all_start_and_end = PythonOperator(
        task_id="check-api-gsp-forecast-all-start-and-end",
        python_callable=check_gsp_forecast_all_start_and_end,
        op_kwargs={"access_token": access_token_str},
    )

    gsp_forecast_all_one_datetime = PythonOperator(
        task_id="check-api-gsp-forecast-all-one-datetime",
        python_callable=check_gsp_forecast_all_one_datetime,
        op_kwargs={"access_token": access_token_str},
    )

    gsp_forecast_one = PythonOperator(
        task_id="check-api-gsp-forecast-one",
        python_callable=check_gsp_forecast_one,
        op_kwargs={"access_token": access_token_str},
    )

    gsp_pvlive_all = PythonOperator(
        task_id="check-api-gsp-pvlive-all",
        python_callable=check_gsp_pvlive_all,
        op_kwargs={"access_token": access_token_str},
    )

    gsp_pvlive_all_compact = PythonOperator(
        task_id="check-api-gsp-pvlive-all-compact",
        python_callable=check_gsp_pvlive_all_compact,
        op_kwargs={"access_token": access_token_str},
    )

    gsp_pvlive_one = PythonOperator(
        task_id="check-api-gsp-pvlive-one",
        python_callable=check_gsp_pvlive_one,
        op_kwargs={"access_token": access_token_str},
    )

    gsp_pvlive_one_day_after = PythonOperator(
        task_id="check-api-gsp-pvlive-one-day-after",
        python_callable=check_gsp_pvlive_one_day_after,
        op_kwargs={"access_token": access_token_str},
    )

    # N hour forecasts
    national_forecast_2_hour = PythonOperator(
        task_id="check-api-national-forecast-2h",
        python_callable=check_national_forecast,
        op_kwargs={"access_token": access_token_str, "horizon_minutes": 120},
    )

    gsp_forecast_one_2_hour = PythonOperator(
        task_id="check-api-gsp-forecast-one-2h",
        python_callable=check_gsp_forecast_one,
        op_kwargs={"access_token": access_token_str, "horizon_minutes": 120},
    )

    if_any_task_failed = PythonOperator(
        task_id="api-uk-national-gsp-check-if-any-task-failed",
        python_callable=lambda: None,
        trigger_rule="one_failed",
        on_success_callback=slack_message_callback(
            "⚠️ One of the API checks has failed. "
            "See which ones have failed on airflow, to help debug the issue. "
            "No out-of-hours support is required.",
        ),
    )

    (
        get_bearer_token
        >> national_forecast
        >> [national_forecast_2_hour, national_forecast_include_metadata]
    )
    get_bearer_token >> national_generation >> national_generation_day_after
    (
        get_bearer_token
        >> gsp_forecast_all
        >> [
            gsp_forecast_all_start_and_end,
            gsp_forecast_all_one_datetime,
            gsp_forecast_all_compact_false,
        ]
    )
    get_bearer_token >> gsp_forecast_one >> gsp_forecast_one_2_hour
    get_bearer_token >> gsp_pvlive_all >> gsp_pvlive_all_compact
    get_bearer_token >> gsp_pvlive_one >> gsp_pvlive_one_day_after

    [
        national_forecast,
        national_forecast_2_hour,
        national_forecast_include_metadata,
        national_generation,
        national_generation_day_after,
        gsp_forecast_all,
        gsp_forecast_all_compact_false,
        gsp_forecast_all_start_and_end,
        gsp_forecast_all_one_datetime,
        gsp_forecast_one,
        gsp_forecast_one_2_hour,
        gsp_pvlive_all,
        gsp_pvlive_one,
        gsp_pvlive_one_day_after,
    ] >> if_any_task_failed


api_national_gsp_check()
