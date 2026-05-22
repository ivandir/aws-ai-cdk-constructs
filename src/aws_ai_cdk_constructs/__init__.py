"""Opinionated AWS CDK L3 constructs for production AI/ML infrastructure.

Available constructs:

- :class:`BedrockKnowledgeBase` — fully implemented. A Bedrock Knowledge Base
  backed by an OpenSearch Serverless vector collection, with the vector index,
  scoped IAM, and an optional CloudWatch dashboard wired up for you.
- :class:`SageMakerEndpoint` — *stub*. Auto-scaling real-time inference endpoint.
- :class:`AiProxy` — *stub*. Lambda + API Gateway proxy in front of a model.
- :class:`ModelArtifacts` — *stub*. S3 + CloudFront distribution for model assets.
"""

from .bedrock_knowledge_base import BedrockKnowledgeBase
from .sagemaker_endpoint import SageMakerEndpoint
from .ai_proxy import AiProxy
from .model_artifacts import ModelArtifacts

__all__ = [
    "BedrockKnowledgeBase",
    "SageMakerEndpoint",
    "AiProxy",
    "ModelArtifacts",
]

__version__ = "0.1.0"
