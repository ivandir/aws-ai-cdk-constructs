"""S3 + CloudFront model artifacts L3 construct.

.. note::
   **Stub.** The public API below is stable, but the implementation is not yet
   written. Tracking issue: a private, versioned S3 bucket for model weights and
   assets, fronted by a CloudFront distribution with Origin Access Control, plus
   sensible cache behaviour for large immutable artifacts.
"""

from __future__ import annotations

from constructs import Construct


class ModelArtifacts(Construct):
    """A private S3 bucket of model assets distributed via CloudFront.

    :param bucket_name: Optional explicit bucket name.
    :param enable_versioning: Keep prior artifact versions. Defaults to True.
    :param price_class: CloudFront price class. Defaults to ``PRICE_CLASS_100``.
    :param default_max_age_seconds: Cache TTL for artifacts. Defaults to 86400.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        bucket_name: str | None = None,
        enable_versioning: bool = True,
        price_class: str = "PRICE_CLASS_100",
        default_max_age_seconds: int = 86400,
    ) -> None:
        super().__init__(scope, id)
        raise NotImplementedError(
            "ModelArtifacts is not implemented yet. "
            "See https://github.com/ivandir/aws-ai-cdk-constructs/issues for status."
        )
