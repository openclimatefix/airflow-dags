"""Helper functions for sending notifications via slack."""

import os
from enum import Enum

from airflow.notifications.basenotifier import BaseNotifier
from airflow.providers.slack.notifications.slack import send_slack_notification

# get the env
env = os.getenv("ENVIRONMENT", "development")
url = os.getenv("URL", "airflow-dev.quartz.energy")

# Constants
FLAGS = {
    "gb": "🇬🇧",
    "nl": "🇳🇱",
    "in": "🇮🇳",
}
DEFAULT_FLAG = "🏳️"

class Urgency(str, Enum):
    """Urgency levels for notifications."""
    CRITICAL = "critical"
    NON_CRITICAL = "non_critical"


def get_task_link() -> str:
    """Get a link to the task in Airflow."""
    # note we need 4 { so that after f-string its 2 { which is needed for airflow
    return f"<https://{url}/dags/{{{{ ti.dag_id }}}}|task {{{{ ti.task_id }}}}>"


def slack_message_callback(message: str) -> list[BaseNotifier]:
    """Send a slack message via the slack notifier."""
    return [
        send_slack_notification(
            text=message,
            channel=f"tech-ops-airflow-{env}",
            username="Airflow",
        ),
    ]

def _build_default_message(task_link: str, flag: str, urgency: Urgency) -> str:
    """Return a sensible default message for the given urgency."""
    if urgency == Urgency.CRITICAL:
        return (
            f"❌{flag} The {task_link} failed. "
            "Please see run book for appropriate actions."
        )
    return (
        f"⚠️{flag} The {task_link} failed, but it's ok. "
        "No out of hours support is required."
    )

def get_slack_message_callback(
    message: str | None = None,
    country: str = "gb",
    urgency: Urgency = Urgency.CRITICAL,
) -> list["BaseNotifier"]:
    """Send a slack message via the slack notifier to channels based on urgency and country.

    Args:
        message: Optional custom message. If None a default message will be used.
        country: Country code used to prefix the message with a flag (default: "gb").
        urgency: Urgency enum ("critical" | "non_critical").

    Returns:
        A list containing the result(s) of `send_slack_notification(...)` calls.
    """
    # get message content
    country_code = country.lower()
    flag = FLAGS.get(country_code, DEFAULT_FLAG)
    task_link = get_task_link()

    # if no message provided provide default
    if not message:
        message = _build_default_message(task_link=task_link, flag=flag, urgency=urgency)

    channel = f"tech-ops-airflow-{env}-{urgency.value}"

    notifier = send_slack_notification(
        text=message,
        channel=channel,
        username="Airflow",
    )

    return [notifier]
