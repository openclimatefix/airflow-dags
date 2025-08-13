"""Functions to help checks on apis."""
import json
import logging
import os
import time

import requests

username = os.getenv("AUTH0_USERNAME")
password = os.getenv("AUTH0_PASSWORD")
client_id = os.getenv("AUTH0_CLIENT_ID")
domain = os.getenv("AUTH0_DOMAIN")
audience = os.getenv("AUTH0_AUDIENCE")

logger = logging.getLogger(__name__)


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


def check_values_ascending_order(values: list, labels: list = None) -> None:
    """Check that values are in ascending order.
    
    Args:
        values: List of numeric values to check
        labels: Optional list of labels for better error messages
    """
    if labels is None:
        labels = [f"value_{i}" for i in range(len(values))]
    
    for i in range(1, len(values)):
        if values[i-1] > values[i]:
            raise ValueError(
                f"Values not in ascending order: "
                f"{labels[i-1]}={values[i-1]} should be <= {labels[i]}={values[i]}"
            )


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
