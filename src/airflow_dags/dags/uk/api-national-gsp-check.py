import requests
import os
import datetime as dt
import json

from airflow.operators.python import PythonOperator
from airflow.decorators import dag

import logging

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


def get_bearer_token_from_auth0():

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
        }
    )
    logger.info(f"Getting bearer token")
    r = requests.post(url, data=data, headers=header)
    access_token = r.json()["access_token"]

    logger.info(f"Got bearer token")
    return access_token


def call_api(url: str, access_token=None):

    logger.info(f"Checking: {url}")

    if access_token:
        headers = {"Authorization": "Bearer " + access_token}
    else:
        headers = {}

    response = requests.get(url, headers=headers)

    assert response.status_code == 200, (
        f"API call failed calling {url} "
        f"with status code {response.status_code},"
        f" message {response.text}"
    )

    return response.json()


def check_api_is_up():
    # check the api is up
    full_url = f"{base_url}/"
    call_api(url=full_url)


def check_api_status():

    # check the api is up
    full_url = f"{base_url}/v0/solar/GB/status"
    call_api(url=full_url)


def check_national_forecast(access_token, horizon_minutes=None):

    full_url = f"{base_url}/v0/solar/GB/national/forecast?"
    if horizon_minutes:
        full_url += f"forecast_horizon_minutes={horizon_minutes}"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for 2 days in the past + 36 hours in the future
    # date is in 30 min intervals
    assert len(data) > 2 * 24 * 2 + 30 * 2

    assert "targetTime" in data[0]
    assert "expectedPowerGenerationMegawatts" in data[0]


def check_national_pvlive(access_token):

    full_url = f"{base_url}/v0/solar/GB/national/pvlive"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for 2 days in the past, maybe the last one isnt in yet
    # We could get more precise with this check
    assert len(data) >= 2 * 24 * 2 - 1

    assert "datetimeUtc" in data[0]
    assert "solarGenerationKw" in data[0]


def check_national_pvlive_day_after(access_token):

    full_url = f"{base_url}/v0/solar/GB/national/pvlive?regime=day-after"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for more than 12 hours in the past,
    # This is because the data is delayed
    # we could get more precise with this check
    assert len(data) >= 2 * 12

    assert "datetimeUtc" in data[0]
    assert "solarGenerationKw" in data[0]


def check_gsp_forecast_all(access_token):

    full_url = f"{base_url}/v0/solar/GB/gsp/forecast/all/?compact=true"
    data = call_api(url=full_url, access_token=access_token)
    logger.debug(data)

    # 36 hours in the future, but just look at 30 hours
    # date is in 30 min intervals
    assert len(data) > 2 * 30

    assert "datetimeUtc" in data[0]
    assert "forecastValues" in data[0]
    assert len(data[0]["forecastValues"]) >= 317


def check_gsp_forecast_all_start_and_end(access_token):

    # -2 days to now
    start_datetime = dt.datetime.utcnow() - dt.timedelta(days=2)
    start_datetime_str = start_datetime.isoformat()
    end_datetime = dt.datetime.utcnow()
    end_datetime_str = end_datetime.isoformat()

    full_url = (
        f"{base_url}/v0/solar/GB/gsp/forecast/all/?compact=true"
        f"&start_datetime_utc={start_datetime_str}&end_datetime_utc={end_datetime_str}"
    )
    data = call_api(url=full_url, access_token=access_token)
    logger.info(data)

    # 2 days in the past
    # date is in 30 min intervals
    logger.info(len(data))
    assert len(data) >= 2 * 24 * 2

    assert "datetimeUtc" in data[0]
    assert "forecastValues" in data[0]
    assert len(data[0]["forecastValues"]) >= 317

    logger.info(start_datetime)
    first_datetime = dt.datetime.strptime(data[0]["datetimeUtc"], "%Y-%m-%dT%H:%M:%SZ")
    last_datetime = dt.datetime.strptime(data[-1]["datetimeUtc"], "%Y-%m-%dT%H:%M:%SZ")
    assert start_datetime + dt.timedelta(hours=0.5) >= first_datetime >= start_datetime
    assert end_datetime >= last_datetime >= end_datetime - dt.timedelta(hours=1)


def check_gsp_forecast_one(access_token, horizon_minutes=None):

    full_url = f"{base_url}/v0/solar/GB/gsp/1/forecast/"
    if horizon_minutes:
        full_url += f"?forecast_horizon_minutes={horizon_minutes}"
    data = call_api(url=full_url, access_token=access_token)

    # 2 days in the past + 36 hours in the future, but just look at 30 hours
    # date is in 30 min intervals
    assert len(data) > 2 * 24 * 2 + 2 * 30

    assert "targetTime" in data[0]
    assert "expectedPowerGenerationMegawatts" in data[0]


def check_gsp_pvlive_all(access_token):

    full_url = f"{base_url}/v0/solar/GB/gsp/pvlive/all/"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for 2 days in the past, maybe the last one isnt in yet
    # date is in 30 min intervals
    N = 24 * 2 * 2 - 1
    assert len(data) >= 317

    assert "gspYields" in data[0]
    assert "datetimeUtc" in data[0]["gspYields"][0]
    assert "solarGenerationKw" in data[0]["gspYields"][0]
    assert len(data[0]["gspYields"]) >= N


def check_gsp_pvlive_one(access_token):

    full_url = f"{base_url}/v0/solar/GB/gsp/1/pvlive/"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for 2 days in the past, maybe the last one isnt in yet
    # date is in 30 min intervals
    N = 24 * 2 * 2 - 1
    assert len(data) >= N

    assert "datetimeUtc" in data[0]
    assert "solarGenerationKw" in data[0]


def check_gsp_pvlive_one_day_after(access_token):

    full_url = f"{base_url}/v0/solar/GB/gsp/1/pvlive?regime=day-after"
    data = call_api(url=full_url, access_token=access_token)

    # should have data point for more than 12 hours in the past,
    # This is because the data is delayed
    N = 12 * 2
    assert len(data) >= N

    assert "datetimeUtc" in data[0]
    assert "solarGenerationKw" in data[0]


@dag(
    dag_id="uk-api-national-gsp-check",
    description=__doc__,
    schedule="0 * * * *",
    start_date=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
    catchup=False,
    default_args=default_args,
)
def api_national_gsp_check() -> None:
    """Dag to check API"""

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

    access_token_str = "{{ task_instance.xcom_pull(task_ids='check-api-get-bearer-token') }}"
    national_forecast = PythonOperator(
        task_id="check-api-national-forecast",
        python_callable=check_national_forecast,
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

    gsp_forecast_all_start_and_end = PythonOperator(
        task_id="check-api-gsp-forecast-all-start-and-end",
        python_callable=check_gsp_forecast_all_start_and_end,
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

    get_bearer_token >> national_forecast >> national_forecast_2_hour
    get_bearer_token >> national_generation >> national_generation_day_after
    get_bearer_token >> gsp_forecast_all >> gsp_forecast_all_start_and_end
    get_bearer_token >> gsp_forecast_one >> gsp_forecast_one_2_hour
    get_bearer_token >> gsp_pvlive_all
    get_bearer_token >> gsp_pvlive_one >> gsp_pvlive_one_day_after


api_national_gsp_check()
