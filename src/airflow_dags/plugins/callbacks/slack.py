"""Helper functions for sending notifications via slack."""

import os
from enum import StrEnum, auto

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

class Urgency(StrEnum):
    """Urgency levels for notifications."""
    CRITICAL = auto()
    SUBCRITICAL = auto()


def get_task_link() -> str:
    """Get a link to the task in Airflow."""
    # note we need 4 { so that after f-string its 2 { which is needed for airflow
    return f"<https://{url}/dags/{{{{ ti.dag_id }}}}|task {{{{ ti.task_id }}}}>"

def _build_message(
    task_link: str, flag: str, urgency: Urgency, additional_message_context: str = "",
) -> str:
    """Return a sensible message for the given urgency."""
    if urgency == Urgency.CRITICAL:
        print(additional_message_context, "additional_message_context!")
        return (
            f"❌{flag} The {task_link} failed. "
            + additional_message_context
            + " Please see run book for appropriate actions."
        )

    return (
        f"⚠️{flag} The {task_link} failed, but it's ok. "
        + additional_message_context
        + "No out of hours support is required."
    )

def get_slack_message_callback(
    country: str = "gb",
    urgency: Urgency = Urgency.CRITICAL,
    additional_message_context: str = "",
) -> list[BaseNotifier]:
    """Send a slack message via the slack notifier to channels based on urgency and country.

    Args:
        country: Country code used to prefix the message with a flag (default: "gb").
        urgency: Urgency enum ("critical" | "non_critical").
        additional_message_context: Optional additional message.

    Returns:
        A list containing the result(s) of `send_slack_notification(...)` calls.
    """
    # get message content
    flag = FLAGS.get(country.lower(), DEFAULT_FLAG)
    task_link = get_task_link()

    message = _build_message(task_link=task_link, flag=flag, urgency=urgency,
                             additional_message_context=additional_message_context)

    # Split channels by urgency for prod
    if env == "production":
        channel = f"tech-ops-airflow-{env}-{urgency.value}"
    else:
        channel = f"tech-ops-airflow-{env}"

    notifier = send_slack_notification(
        text=message,
        channel=channel,
        username="Airflow",
    )

    return [notifier]
