"""Preconfigured operator for running ECS tasks."""

import dataclasses
import os
from collections.abc import Callable
from typing import Any, ClassVar, override

from airflow.models import BaseOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.amazon.aws.operators.ecs import (
    EcsRegisterTaskDefinitionOperator,
    EcsRunTaskOperator,
)
from airflow.utils.context import Context
from airflow.utils.trigger_rule import TriggerRule
from botocore.errorfactory import ClientError

# These should probably be templated instead of top-level, see
# https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html#top-level-python-code
ENV: str = os.getenv("ENVIRONMENT", "development")
SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
ECS_SUBNET: str = os.getenv("ECS_SUBNET", "")
ECS_SECURITY_GROUP: str = os.getenv("ECS_SECURITY_GROUP", "")
ECS_EXECUTION_ROLE_ARN: str = os.getenv("ECS_EXECUTION_ROLE_ARN", "")
ECS_TASK_ROLE_ARN: str = os.getenv("ECS_TASK_ROLE_ARN", "")
AWS_REGION: str = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")
AWS_OWNER_ID: str = os.getenv("AWS_OWNER_ID", "")

class EcsConditionalRegisterTaskDefinitionOperator(EcsRegisterTaskDefinitionOperator):
    """Operator to conditionally register ECS tasks."""

    def __init__(
            self,
            *,
            family: str,
            container_definitions: list[dict[str, Any]],
            register_task_kwargs: dict[str, Any],
            **kwargs: Any,
        ) -> None:
        """Create a new instance of the class."""
        self.family = family
        self.container_definitions = container_definitions
        self.register_task_kwargs = register_task_kwargs
        super().__init__(
            family=family,
            container_definitions=container_definitions,
            register_task_kwargs=register_task_kwargs,
            **kwargs,
        )

    @override
    def execute(self, context: Context) -> Any:
        try:
            existing_def = self.client.describe_task_definition(
                taskDefinition=self.family, include=["TAGS"],
            )
            existing_container_def = existing_def["taskDefinition"]["containerDefinitions"][0]
            existing_kwargs = existing_def["taskDefinition"] | { "tags": existing_def["tags"] }
            existing_kwargs.pop("containerDefinitions")

            # Only return the ECS operator if the task has changed
            for key in self.container_definitions[0]:
                if key == "environment":
                    existing = {frozenset(d.items()) for d in existing_container_def["environment"]}
                    new = {
                        frozenset(d.items()) for d in self.container_definitions[0]["environment"]
                    }
                    if existing != new:
                        self.log.info(
                            "Definition key 'environment' different, registering new task "
                            f"definition (current: '{existing}'; new: '{new}')",
                        )
                elif existing_container_def.get(key) != self.container_definitions[0].get(key):
                    self.log.info(
                        f"Definition key '{key}' different, registering new task definition",
                    )
                    return super().execute(context=context)
            for key in self.register_task_kwargs:
                if existing_kwargs.get(key) != self.register_task_kwargs.get(key):
                    self.log.info(
                        f"Definition key '{key}' different, registering new task definition",
                    )
                    return super().execute(context=context)

        except ClientError as e:
            # ECS Task definition doesn't exist yet, create it
            self.log.info(f"Error getting task definition: {e}")
            return super().execute(context=context)

        self.log.info("Task definition already exists, skipping registry.")
        pass

@dataclasses.dataclass
class ECSOperatorGen:
    """Wrapper class to handle creation of ECS operators to run an image."""

    name: str
    """The name given to the container, logs, and task definition."""
    container_image: str
    """The container image to run, including the container repository."""
    container_tag: str
    """The tag of the container image."""
    container_env: dict[str, str] = dataclasses.field(default_factory=dict)
    """The environment variables to pass to the container."""
    container_secret_env: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    """Map of AWS secret names to keys within the secret to pas to the container.

    The secret ARN is fetched from the secret name via boto3.
    """
    container_cpu: int = 1024
    """The CPU size of the container in milli-units."""
    container_memory: int = 2048
    """The memory size of the container in MiB."""
    container_command: list[str] = dataclasses.field(default_factory=list)
    """The command to run in the container."""
    domain: str = "uk"
    """The domain of the container."""
    container_storage: int = 20
    """The ephemeral storage size of the container in GB."""

    _default_env: ClassVar[dict[str, str]] = {
        "AWS_REGION": AWS_REGION,
        "SENTRY_DSN": SENTRY_DSN,
        "ENVIRONMENT": ENV,
    }


    def __post_init__(self) -> None:
        """Perform some validation on inputs."""
        allowed_sizes: dict[int, list[int]] = {
            256: [512, 1024, 2048],
            512: list(range(1024, 4096, 1024)),
            1024: list(range(2048, 9216, 1024)),
            2048: list(range(4096, 16384, 1024)),
            4096: list(range(8192, 30720, 1024)),
            8192: list(range(16384, 61440, 4096)),
        }
        if self.container_cpu not in allowed_sizes:
            raise ValueError(f"CPU must be one of {allowed_sizes.keys()}, got {self.container_cpu}")
        if self.container_memory not in allowed_sizes[self.container_cpu]:
            raise ValueError(
                f"Memory must be one of {allowed_sizes[self.container_cpu]}"
                f", got {self.container_memory}",
            )
        if self.domain not in ["uk", "india"]:
            raise ValueError(f"Domain must be one of ['uk', 'india'], got {self.domain}")
        if self.container_storage < 20:
            raise ValueError(f"Storage must be at least 20GB. Got {self.container_storage}GB")

    def as_container_definition(self) -> dict[str, object]:
        """Return an ECS container definition."""
        cluster, region = self.cluster_region_tuple
        return {
            "name": self.name,
            "image": f"{self.container_image}:{self.container_tag}",
            "essential": True,
            "command": self.container_command,
            "environment": [
                {"name": k, "value": v}
                for k, v in (self.container_env | self._default_env).items()
            ],
            "secrets": [
                {"name": key, "valueFrom": "arn:aws:secretsmanager"\
                        f":{region}:{AWS_OWNER_ID}:secret:{secret}:{key}::",
                } for secret, keys in self.container_secret_env.items()
                for key in keys
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": f"/aws/ecs/{cluster}",
                    "awslogs-region": region,
                    "awslogs-stream-prefix": "airflow",
                },
            },
        }

    def as_task_kwargs(self) -> dict[str, object]:
        """Return ECS task kwargs."""
        output: dict[str, object] = {
            "cpu": str(self.container_cpu),
            "memory": str(self.container_memory),
            "requiresCompatibilities": ["FARGATE"],
            "executionRoleArn": ECS_EXECUTION_ROLE_ARN,
            "taskRoleArn": ECS_TASK_ROLE_ARN,
            "networkMode": "awsvpc",
            "tags": [
                {"key": "name", "value": self.name},
                {"key": "environment", "value": ENV},
                {"key": "type", "value": "ecs"},
                {"key": "domain", "value": self.domain},
            ],
        }
        if self.container_storage > 20:
            output["ephemeralStorage"] = {"sizeInGiB": self.container_storage}

        return output


    @property
    def cluster_region_tuple(self) -> tuple[str, str]:
        """Return the name of the ECS cluster and its region."""
        if self.domain == "india":
            return f"india-ecs-cluster-{ENV}", "ap-south-1"
        return f"Nowcasting-{ENV}", "eu-west-1"

    def setup_operator(self) -> BaseOperator:
        """Create an Airflow operator to register an ECS task definition.

        Secrets are not passed through the environment directly but through
        the `secrets` key in the container definition to prevent exposure in
        the task definition.
        """
        cluster, region = self.cluster_region_tuple

        return EcsConditionalRegisterTaskDefinitionOperator(
            family=self.name,
            task_id=f"register_{self.name}",
            container_definitions=[self.as_container_definition()],
            register_task_kwargs=self.as_task_kwargs(),
            region=region,
        )

    def run_task_operator(
        self,
        airflow_task_id: str,
        env_overrides: dict[str, str] | None = None,
        command_override: list[str] | None = None,
        on_failure_callback: Callable | None = None,
        trigger_rule: TriggerRule = TriggerRule.ALL_SUCCESS,
    ) -> EcsRunTaskOperator:
        """Create an Airflow operator to run an ECS task."""
        overrides_dict: dict[str, Any] = {"name": self.name}
        if env_overrides:
            overrides_dict["environment"] = [
                {"name": k, "value": v} for k, v in env_overrides.items()
            ]
        if command_override:
            overrides_dict["command"] = command_override

        networks_dict: dict[str, dict[str, list[str] | str]] = {
            "awsvpcConfiguration": {
                "subnets": [ECS_SUBNET],
                "securityGroups": [ECS_SECURITY_GROUP],
                "assignPublicIp": "ENABLED",
            },
        }

        cluster, region = self.cluster_region_tuple

        return EcsRunTaskOperator(
            task_id=airflow_task_id,
            task_definition=self.name,
            task_concurrency=1,
            cluster=cluster,
            overrides={"containerOverrides": [overrides_dict]},
            launch_type="FARGATE",
            network_configuration=networks_dict,
            awslogs_group=f"/aws/ecs/{cluster}",
            awslogs_stream_prefix="airflow",
            awslogs_region=region,
            trigger_rule=trigger_rule,
            on_failure_callback=on_failure_callback,
        )

    def teardown_operator(self) -> BaseOperator:
        """Create an Airflow operator to deregister an ECS task definition."""
        # Since task_definition is a templateable field, we can do this
        # td = f"{{{{ ti.xcom_pull(task_ids='register_{self.name}', key='task_definition_arn') }}}}"
        # return EcsDeregisterTaskDefinitionOperator(
        #     task_id=f"deregister_{self.name}",
        #     task_definition=td,
        # )
        return EmptyOperator(task_id=f"deregister_{self.name}")

