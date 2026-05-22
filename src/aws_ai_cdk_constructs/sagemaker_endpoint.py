"""SageMaker auto-scaling endpoint L3 construct.

.. note::
   **Stub.** The public API below is stable, but the implementation is not yet
   written. Tracking issue: real-time endpoint + model + endpoint-config,
   target-tracking auto-scaling on ``InvocationsPerInstance``, optional
   data-capture to S3, and a CloudWatch dashboard for latency/invocations.
"""

from __future__ import annotations

from typing import Optional

from constructs import Construct


class SageMakerEndpoint(Construct):
    """A real-time SageMaker inference endpoint with auto-scaling.

    :param model_data_url: S3 URI of the packaged model artifact (``model.tar.gz``).
    :param image_uri: ECR URI of the inference container.
    :param instance_type: Hosting instance type. Defaults to ``ml.m5.large``.
    :param min_capacity: Minimum instance count. Defaults to 1.
    :param max_capacity: Maximum instance count for auto-scaling. Defaults to 4.
    :param target_invocations_per_instance: Scaling target. Defaults to 750.
    :param enable_data_capture: Capture inference I/O to S3. Defaults to False.
    :param create_dashboard: Emit a CloudWatch dashboard. Defaults to True.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        model_data_url: str,
        image_uri: str,
        instance_type: str = "ml.m5.large",
        min_capacity: int = 1,
        max_capacity: int = 4,
        target_invocations_per_instance: int = 750,
        enable_data_capture: bool = False,
        create_dashboard: bool = True,
    ) -> None:
        super().__init__(scope, id)
        raise NotImplementedError(
            "SageMakerEndpoint is not implemented yet. "
            "See https://github.com/ivandir/aws-ai-cdk-constructs/issues for status."
        )
