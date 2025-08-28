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
    check_len_equal,
    check_len_ge,
    get_bearer_token_from_auth0,
)

logger = logging.getLogger(__name__)

env = os.getenv("ENVIRONMENT", "development")
base_url = "http://api-dev.quartz.solar" if env == "development" else "http://api.quartz.solar"


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


def check_national_forecast_metadata_true_and_false(
    access_token: str,
) -> None:
    """Check the national forecast with include_metadata true and false.

    Make sure both routes gives back the same values
    """
    full_url = f"{base_url}/v0/solar/GB/national/forecast?include_metadata=true"
    data_true = call_api(url=full_url, access_token=access_token)

    full_url = f"{base_url}/v0/solar/GB/national/forecast?include_metadata=false"
    data_false = call_api(url=full_url, access_token=access_token)

    values_true = data_true["forecastValues"]
    values_false = data_false

    # create dict of target times and power
    values_true = {v["targetTime"]: v["expectedPowerGenerationMegawatts"] for v in values_true}
    values_false = {v["targetTime"]: v["expectedPowerGenerationMegawatts"] for v in values_false}

    diff_values = []
    for k, v in values_true.items():
        if k in values_false and v != values_false[k]:
            diff_values.append(
                {"targetTime": k, "metadata=true": v, "metadata=false": values_false[k]},
            )

    if len(diff_values) > 0:
        message = (
            "Values with include_metadata=true and false are not the same. This should not happen. "
        )
        message += f"The first different values is at {diff_values[0]}."

        if len(diff_values) > 1:
            message += f"The last different values is at {diff_values[-1]}"

        raise ValueError(message)


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


def check_national_forecast_quantiles_order(access_token: str) -> None:
    """Check that national forecast quantiles are returned in correct order.

    This function validates that for each forecast value,
    plevel_10 <= expectedPowerGenerationMegawatts <= plevel_90.
    """
    full_url = f"{base_url}/v0/solar/GB/national/forecast?include_metadata=true"
    data = call_api(url=full_url, access_token=access_token)

    # Check that we have forecast values
    check_key_in_data(data, "forecastValues")
    forecast_values = data["forecastValues"]
    check_len_ge(forecast_values, 1)

    for i, forecast_value in enumerate(forecast_values):
        plevels = forecast_value.get("plevels")
        if not plevels:
            target_time = forecast_value.get("targetTime", "unknown")
            raise ValueError(
                f"No plevels found for forecast index {i}, targetTime: {target_time}. "
                "We should always have plevels.",
            )

        plevel_10 = plevels.get("plevel_10")
        plevel_90 = plevels.get("plevel_90")
        expected = forecast_value.get("expectedPowerGenerationMegawatts")

        # Check for missing quantiles and raise error with specific details
        missing_values = []
        if plevel_10 is None:
            missing_values.append("plevel_10")
        if plevel_90 is None:
            missing_values.append("plevel_90")
        if expected is None:
            missing_values.append("expectedPowerGenerationMegawatts")

        if missing_values:
            raise ValueError(
                f"Missing required values {missing_values} for forecast index {i}, "
                f"targetTime: {forecast_value.get('targetTime', 'unknown')}",
            )

        if not (plevel_10 <= expected <= plevel_90):
            raise ValueError(
                f"Quantiles not in correct order at forecast index {i}. "
                f"{plevel_10=} <= {expected=} <= {plevel_90=} is not satisfied. "
                f"Target time: {forecast_value.get('targetTime', 'unknown')}",
            )
        logger.debug(
            f"plevel_10 <= expected <= plevel_90 for forecast {i}: "
            f"{plevel_10} <= {expected} <= {plevel_90}",
        )

    logger.info(
        "All national forecast quantiles are in correct order (plevel_10 <= expected <= plevel_90)",
    )


def check_gsp_forecast_all_compact_false(access_token: str) -> None:
    """Check the GSP forecast all with compact=false."""
    full_url = f"{base_url}/v0/solar/GB/gsp/forecast/all/?compact=false&gsp_ids=1,2,3"
    data = call_api(url=full_url, access_token=access_token)

    # 36 hours in the future, but just look at 30 hours
    # date is in 30 min intervals
    check_len_equal(data["forecasts"], 3)
    check_key_in_data(data["forecasts"][0], "forecastValues")
    check_len_ge(data["forecasts"][0]["forecastValues"], 2 * 30)


def check_gsp_forecast_all(access_token: str) -> None:
    """Check the GSP forecast all."""
    full_url = f"{base_url}/v0/solar/GB/gsp/forecast/all/?compact=true"
    data = call_api(url=full_url, access_token=access_token)

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

    access_token_str = "{{ task_instance.xcom_pull(task_ids='check-api-get-bearer-token') }}"  # noqa: S105
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

    national_forecast_compare_metadata = PythonOperator(
        task_id="check-api-national-forecast-compare-metadata-true-and-false",
        python_callable=check_national_forecast_metadata_true_and_false,
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

    national_forecast_quantiles_order = PythonOperator(
        task_id="check-api-national-forecast-quantiles-order",
        python_callable=check_national_forecast_quantiles_order,
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
            "⚠️ One of the API checks has failed. 🇬🇧 "
            "See which ones have failed on airflow, to help debug the issue. "
            "No out-of-hours support is required.",
        ),
    )

    (
        get_bearer_token
        >> national_forecast
        >> [
            national_forecast_2_hour,
            national_forecast_include_metadata,
            national_forecast_compare_metadata,
        ]
    )
    (
        get_bearer_token
        >> national_generation
        >> national_generation_day_after
        >> national_forecast_quantiles_order
    )
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
        national_forecast_quantiles_order,
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

if __name__ == "__main__":
    # Run all the function, Manual UAT
    # This can be useful after the API is deployed
    check_api_is_up()
    bearer_token = get_bearer_token_from_auth0()
    check_national_forecast(bearer_token)
    check_national_forecast(bearer_token, horizon_minutes=120)
    check_national_forecast_include_metadata(bearer_token)
    check_national_forecast_metadata_true_and_false(bearer_token)
    check_national_forecast_quantiles_order(bearer_token)
    check_national_pvlive(bearer_token)
    check_national_pvlive_day_after(bearer_token)
    check_gsp_forecast_all(bearer_token)
    check_gsp_forecast_all_compact_false(bearer_token)
    check_gsp_forecast_all_start_and_end(bearer_token)
    check_gsp_forecast_all_one_datetime(bearer_token)
    check_gsp_forecast_one(bearer_token)
    check_gsp_forecast_one(bearer_token, horizon_minutes=120)
    check_gsp_pvlive_all(bearer_token)
    check_gsp_pvlive_all_compact(bearer_token)
    check_gsp_pvlive_one(bearer_token)
    check_gsp_pvlive_one_day_after(bearer_token)
    check_api_status()
