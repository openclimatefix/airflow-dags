"""Preconfigured operator for running ECS tasks."""

import dataclasses
import os
from typing import Any, override

from airflow.providers.amazon.aws.operators.ecs import (
    EcsRunTaskOperator,
)
from airflow.utils.context import Context
from botocore.errorfactory import ClientError

# These should probably be templated instead of top-level, see
# https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html#top-level-python-code

class EcsAutoRegisterRunTaskOperator(EcsRunTaskOperator):
    """Operator to run tasks on ECS.

    Automatically registers a task definition if one doesn't exist,
    or if it is out of date with the container definition.
    """

    container_def: "ContainerDefinition"

    def __init__(
            self,
            *,
            airflow_task_id: str,
            container_def: "ContainerDefinition",
            env_overrides: dict[str, str] | None = None,
            command_override: list[str] | None = None,
            **kwargs: int | bool | str | dict[str, str] | list[str],
        ) -> None:
        """Create a new instance of the class."""
        self.container_def = container_def

        overrides_dict: dict[str, Any] = {"name": container_def.name}
        if env_overrides:
            overrides_dict["environment"] = [
                {"name": k, "value": v} for k, v in env_overrides.items()
            ]
        if command_override:
            overrides_dict["command"] = command_override

        networks_dict: dict[str, dict[str, list[str] | str]] = {
            "awsvpcConfiguration": {
                "subnets": [os.getenv("ECS_SUBNET", "")],
                "securityGroups": [os.getenv("ECS_SECURITY_GROUP", "")],
                "assignPublicIp": "ENABLED",
            },
        }

        cluster, region = self.container_def.cluster_region_tuple
        super().__init__(
            task_id=airflow_task_id,
            task_definition=self.container_def.name,
            cluster=cluster,
            overrides={"containerOverrides": [overrides_dict]},
            launch_type="FARGATE",
            network_configuration=networks_dict,
            awslogs_group=f"/aws/ecs/{cluster}",
            awslogs_stream_prefix="airflow",
            awslogs_region=region,
            **kwargs,
        )

    def _determine_outdated(self) -> bool:
        """Determine whether the task definition is out of date."""
        try:
            existing_def = self.client.describe_task_definition(
                taskDefinition=self.container_def.name, include=["TAGS"],
            )
            existing_container_def = existing_def["taskDefinition"]["containerDefinitions"][0]
            existing_kwargs = existing_def["taskDefinition"] | { "tags": existing_def["tags"] }
            existing_kwargs.pop("containerDefinitions")

            # Only return the ECS operator if the task has changed
            for key in self.container_def.ecs_container_definition():
                if key == "environment":
                    existing = {frozenset(d.items()) for d in existing_container_def["environment"]}
                    new = {
                        frozenset(d.items())
                        for d in self.container_def.ecs_environment()
                    }
                    if existing != new:
                        self.log.info(
                            "Definition key 'environment' different, registering new task "
                            f"definition (current: '{existing}'; new: '{new}')",
                        )
                        return True
                elif existing_container_def.get(key) \
                        != self.container_def.ecs_container_definition().get(key):
                    self.log.info(
                        f"Definition key '{key}' different, registering new task definition",
                    )
                    return True
            for key in self.container_def.ecs_register_task_kwargs():
                if existing_kwargs[key] != self.container_def.ecs_register_task_kwargs()[key]:
                    self.log.info(
                        f"Definition key '{key}' different, registering new task definition",
                    )
                    return True

        except ClientError as e:
            self.log.info(
                f"Task definition '{self.container_def.name}' not found, creating (ctx: {e})",
            )
            return True

        self.log.info("Task definition up to date")
        return False


    @override
    def execute(self, context: Context) -> Any:
        """Execute the task on ECS, registering the task definition if required."""
        if self._determine_outdated():
            self.log.info(
                "Registering task definition %s using the following values: %s",
                self.container_def.name,
                self.container_def.ecs_register_task_kwargs(),
            )
            self.log.info(
                "Using container definition %s",
                self.container_def.ecs_container_definition(),
            )
            response = self.client.register_task_definition(
                family=self.container_def.name,
                containerDefinitions=[self.container_def.ecs_container_definition()],
                **self.container_def.ecs_register_task_kwargs(),
            )
            task_definition_details = response["taskDefinition"]
            task_definition_arn = task_definition_details["taskDefinitionArn"]

            self.log.info(
                "Task Definition %r in state: %r.",
                task_definition_arn,
                task_definition_details.get("status"),
            )
            context["ti"].xcom_push(key="task_definition_arn", value=task_definition_arn)

        return super().execute(context=context)

@dataclasses.dataclass
class ContainerDefinition:
    """Dataclass defining a container to execute a specific job."""

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

    def ecs_environment(self) -> list[dict[str, object]]:
        """Return an ECS environment definition list."""
        default_env: dict[str, str] = {
            "AWS_REGION": os.getenv("AWS_DEFAULT_REGION", "eu-west-1"),
            "SENTRY_DSN": os.getenv("SENTRY_DSN", ""),
            "ENVIRONMENT": os.getenv("ENVIRONMENT", "development"),
        }
        return [
            {"name": k, "value": v}
            for k, v in (self.container_env | default_env).items()
        ]

    def ecs_secrets(self) -> list[dict[str, str]]:
        """Return an ECS secrets definition list."""
        AWS_OWNER_ID: str = os.getenv("AWS_OWNER_ID", "")
        _, region = self.cluster_region_tuple
        return [
            {"name": key, "valueFrom": f"arn:aws:secretsmanager:{region}:{AWS_OWNER_ID}"\
                f":secret:{secret}:{key}::",
            } for secret, keys in self.container_secret_env.items()
            for key in keys
        ]

    def ecs_container_definition(self) -> dict[str, object]:
        """Return an ECS container definition dictionary."""
        cluster, region = self.cluster_region_tuple

        return {
            "name": self.name,
            "image": f"{self.container_image}:{self.container_tag}",
            "essential": True,
            "command": self.container_command,
            "environment": self.ecs_environment(),
            "secrets": self.ecs_secrets(),
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": f"/aws/ecs/{cluster}",
                    "awslogs-region": region,
                    "awslogs-stream-prefix": "airflow",
                },
            },
        }

    def ecs_register_task_kwargs(self) -> dict[str, object]:
        """Return kwargs for registering an ECS task."""
        output: dict[str, object] = {
            "cpu": str(self.container_cpu),
            "memory": str(self.container_memory),
            "requiresCompatibilities": ["FARGATE"],
            "executionRoleArn": os.getenv("ECS_EXECUTION_ROLE_ARN", ""),
            "taskRoleArn": os.getenv("ECS_TASK_ROLE_ARN", ""),
            "networkMode": "awsvpc",
            "tags": [
                {"key": "name", "value": self.name},
                {"key": "environment", "value": os.getenv("ENVIRONMENT", "development")},
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
        ENV: str = os.getenv("ENVIRONMENT", "development")
        if self.domain == "india":
            return f"india-ecs-cluster-{ENV}", "ap-south-1"
        return f"Nowcasting-{ENV}", "eu-west-1"

