"""Functions for elastic beanstalk environment."""
import logging
import time
from datetime import UTC, datetime

import boto3

logger = logging.getLogger(__name__)


def terminate_any_old_instances(name: str, days_limit: int = 3, sleep_seconds: int = 300) -> None:
    """Terminate any old instances in an elastic beanstalk environment.

    Note when an instance in terminate in ELB, the ELB will automatically start a new one up
    Args:
        name: Name of the elastic beanstalk environment.
        days_limit: Number of days to consider an instance as old.
        sleep_seconds: Time to wait after terminating each instance.
    """
    eb = boto3.client("elasticbeanstalk")
    ec2 = boto3.client("ec2")
    response = eb.describe_environment_resources(EnvironmentName=name)

    number_of_instances = len(response["EnvironmentResources"]["Instances"])
    if number_of_instances < 2:
        logger.info(
            f"Only {number_of_instances} instance(s) found in environment '{name}'. ",
            "Termination would be too risky.",
        )
        return

    for instance in response["EnvironmentResources"]["Instances"]:
        instance_details = ec2.describe_instances(InstanceIds=[instance["Id"]])
        launch_datetime = instance_details["Reservations"][0]["Instances"][0]["LaunchTime"]
        if (datetime.now(tz=UTC) - launch_datetime).days > days_limit:
            logger.info(f"Terminating old instance {instance['Id']} launched at {launch_datetime}")
            ec2 = boto3.client("ec2")
            ec2.terminate_instances(InstanceIds=[instance["Id"]])
            logger.info(
                f"Instance {instance['Id']} terminated, ",
                f"now sleeping for {sleep_seconds} seconds to allow for new instance to start.",
            )
            time.sleep(sleep_seconds)
        else:
            logger.info(f"Instance {instance['Id']} is not old enough, skipping termination.")


def scale_elastic_beanstalk_instance(
    name: str,
    number_of_instances: int,
    sleep_seconds: int = 0,
) -> None:
    """Scale elastic beanstalk instance."""
    # get the environment
    eb = boto3.client("elasticbeanstalk")

    # change the number of instances
    logger.info(f"Scaling {name} to {number_of_instances} instances")
    eb.update_environment(
        EnvironmentName=name,
        OptionSettings=[
            {
                "Namespace": "aws:autoscaling:asg",
                "OptionName": "MinSize",
                "Value": str(number_of_instances),
            },
            {
                "Namespace": "aws:autoscaling:asg",
                "OptionName": "MaxSize",
                "Value": str(number_of_instances),
            },
        ],
    )

    # sleep to let the environment update
    if sleep_seconds > 0:
        logger.info(f"Sleeping for {sleep_seconds} seconds")
        time.sleep(sleep_seconds)
