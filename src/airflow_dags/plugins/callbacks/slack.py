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


def slack_message_callback(message: str) -> list[BaseNotifier]:
    """Send a slack message via the slack notifier."""
    return [
        send_slack_notification(
            text=message,
            channel=f"tech-ops-airflow-{env}",
            username="Airflow",
        ),
    ]

def get_slack_message_callback(
    country: str = "gb",
    urgency_level: str = "non_critical",
) -> list[BaseNotifier]:
    """Send a slack message via the slack notifier to channels based on urgency and country."""
    flags = {
        "gb": "🇬🇧",
        "nl": "🇳🇱",
        "in": "🇮🇳",
    }
    flag = flags.get(country.lower(), "🏳️")
    if urgency_level == "critical":
        return [send_slack_notification(
            text=(f"❌{flag} The {get_task_link()} failed. "
            "Please see run book for appropriate actions. "),
            channel=f"tech-ops-airflow-{env}-{urgency_level}",
            username="Airflow",
        ),
        ]

    elif urgency_level == "non_critical":
        return [
            send_slack_notification(
                text=(
                    f"⚠️{flag} The {get_task_link()} failed, but its ok. "
                    "No out of hours support is required."
                ),
                channel=f"tech-ops-airflow-{env}-{urgency_level}",
                username="Airflow",
            ),
        ]
    else:
        raise ValueError("urgency_level must be either 'critical' or 'non_critical'")
