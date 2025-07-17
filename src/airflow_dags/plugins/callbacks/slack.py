"""Helper functions for sending notifications via slack."""

import os

from airflow.notifications.basenotifier import BaseNotifier
from airflow.providers.slack.notifications.slack import send_slack_notification

# get the env
env = os.getenv("ENVIRONMENT", "development")

# declare on_failure_callback
on_failure_callback = [
    send_slack_notification(
        text="The task {{ ti.task_id }} failed",
        channel=f"tech-ops-airflow-{env}",
        username="Airflow",
    ),
]

slack_message_callback_no_action_required = [
    send_slack_notification(
        text="⚠️ The task {{ ti.task_id }} failed,"
        " but its ok. No out of hours support is required.",
        channel=f"tech-ops-airflow-{env}",
        username="Airflow",
    ),
]


def slack_message_callback(message: str) -> list[BaseNotifier]:
    """Send a slack message via the slack notifier."""
    return [
        send_slack_notification(
            text=message,
            channel=f"tech-ops-airflow-{env}",
            username="Airflow",
        ),
    ]

def get_slack_message_callback_no_action_required(country: str = "gb") -> list[BaseNotifier]:
    """Send a slack message with a country flag, depending on the country code."""
    flags = {
        "gb": "🇬🇧",
        "nl": "🇳🇱",
        "in": "🇮🇳",
    }
    flag = flags.get(country.lower(), "🏳️")
    return [
        send_slack_notification(
            text=(
                    f"{flag} The task {{ ti.task_id }} failed, but its ok. "
                    "No out of hours support is required."
                ),
            channel=f"tech-ops-airflow-{env}",
            username="Airflow",
        ),
    ]
