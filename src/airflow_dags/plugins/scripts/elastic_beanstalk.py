"""Functions for elastic beanstalk environment."""
import logging
import time

import boto3

logger = logging.getLogger(__name__)


def scale_elastic_beanstalk_instance(
        name: str,
        number_of_instances: int,
        sleep_seconds: int=0,
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

