"""Lambda + API Gateway AI proxy L3 construct.

.. note::
   **Stub.** The public API below is stable, but the implementation is not yet
   written. Tracking issue: REST/HTTP API → Lambda that proxies to a Bedrock
   model (or a SageMaker endpoint), with request throttling, optional API-key
   auth, structured access logging, and a CloudWatch dashboard.
"""

from __future__ import annotations

from typing import Optional, Sequence

from constructs import Construct


class AiProxy(Construct):
    """An API Gateway + Lambda proxy that fronts an AI model.

    :param model_id: Bedrock model id to invoke (mutually exclusive with
        ``sagemaker_endpoint_name``).
    :param sagemaker_endpoint_name: SageMaker endpoint to invoke instead of Bedrock.
    :param require_api_key: Require an API key on requests. Defaults to True.
    :param throttle_rate_limit: Steady-state requests/sec. Defaults to 25.
    :param throttle_burst_limit: Burst request ceiling. Defaults to 50.
    :param allowed_origins: CORS origins. Defaults to none (same-origin only).
    :param create_dashboard: Emit a CloudWatch dashboard. Defaults to True.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        model_id: Optional[str] = None,
        sagemaker_endpoint_name: Optional[str] = None,
        require_api_key: bool = True,
        throttle_rate_limit: int = 25,
        throttle_burst_limit: int = 50,
        allowed_origins: Optional[Sequence[str]] = None,
        create_dashboard: bool = True,
    ) -> None:
        super().__init__(scope, id)
        raise NotImplementedError(
            "AiProxy is not implemented yet. "
            "See https://github.com/ivandir/aws-ai-cdk-constructs/issues for status."
        )
