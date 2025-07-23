"""Helper functions for sending notifications via slack."""

import os

from airflow.notifications.basenotifier import BaseNotifier
from airflow.providers.slack.notifications.slack import send_slack_notification

# get the env
env = os.getenv("ENVIRONMENT", "development")
url = os.getenv("URL", "airflow-dev.quartz.energy")


def get_task_link() -> str:
    """Get a link to the task in Airflow."""
    # note we need 4 { so that after f-string its 2 { which is needed for airflow
    return f"<https://{url}/dags/{{{{ ti.dag_id }}}}|task {{{{ ti.task_id }}}}>"


# declare on_failure_callback
on_failure_callback = [
    send_slack_notification(
        text=f"The {get_task_link()} failed",
        channel=f"tech-ops-airflow-{env}",
        username="Airflow",
    ),
]

slack_message_callback_no_action_required = [
    send_slack_notification(
        text=f"⚠️ The {get_task_link()}  failed,"
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


def get_slack_message_callback_no_action_required(
    country: str = "gb",
) -> list[BaseNotifier]:
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
                f"⚠️{flag} The {get_task_link()} failed, but its ok. "
                "No out of hours support is required."
            ),
            channel=f"tech-ops-airflow-{env}",
            username="Airflow",
        ),
    ]
