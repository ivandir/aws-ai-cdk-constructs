"""Synthesis tests for the BedrockKnowledgeBase construct.

These assert the construct produces the right CloudFormation resources without
deploying anything. The index custom-resource asset is pure-Python (no Docker),
so ``Template.from_stack`` works in plain CI.
"""

import aws_cdk as cdk
import pytest
from aws_cdk import assertions

from aws_ai_cdk_constructs import (
    AiProxy,
    BedrockKnowledgeBase,
    ModelArtifacts,
    SageMakerEndpoint,
)


def _template() -> assertions.Template:
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack", env=cdk.Environment(account="111111111111", region="us-east-1"))
    BedrockKnowledgeBase(stack, "Kb")
    return assertions.Template.from_stack(stack)


def test_creates_core_resources():
    template = _template()
    template.resource_count_is("AWS::OpenSearchServerless::Collection", 1)
    template.resource_count_is("AWS::Bedrock::KnowledgeBase", 1)
    template.resource_count_is("AWS::Bedrock::DataSource", 1)
    template.resource_count_is("AWS::S3::Bucket", 1)


def test_creates_all_three_oss_policies():
    template = _template()
    # encryption + network are SecurityPolicy; data-access is AccessPolicy.
    template.resource_count_is("AWS::OpenSearchServerless::SecurityPolicy", 2)
    template.resource_count_is("AWS::OpenSearchServerless::AccessPolicy", 1)


def test_collection_is_vectorsearch():
    template = _template()
    template.has_resource_properties(
        "AWS::OpenSearchServerless::Collection", {"Type": "VECTORSEARCH"}
    )


def test_knowledge_base_uses_default_field_mapping():
    template = _template()
    template.has_resource_properties(
        "AWS::Bedrock::KnowledgeBase",
        assertions.Match.object_like(
            {
                "StorageConfiguration": {
                    "Type": "OPENSEARCH_SERVERLESS",
                    "OpensearchServerlessConfiguration": {
                        "FieldMapping": {
                            "VectorField": "bedrock-knowledge-base-default-vector",
                            "TextField": "AMAZON_BEDROCK_TEXT_CHUNK",
                            "MetadataField": "AMAZON_BEDROCK_METADATA",
                        }
                    },
                }
            }
        ),
    )


def test_dashboard_can_be_disabled():
    app = cdk.App()
    stack = cdk.Stack(app, "NoDash", env=cdk.Environment(account="111111111111", region="us-east-1"))
    BedrockKnowledgeBase(stack, "Kb", create_dashboard=False)
    assertions.Template.from_stack(stack).resource_count_is("AWS::CloudWatch::Dashboard", 0)


@pytest.mark.parametrize("construct", [SageMakerEndpoint, AiProxy, ModelArtifacts])
def test_stub_constructs_raise_not_implemented(construct):
    """Stubs are importable and define their API, but error on instantiation."""
    app = cdk.App()
    stack = cdk.Stack(app, "StubStack")
    kwargs = {
        SageMakerEndpoint: {"model_data_url": "s3://b/m.tar.gz", "image_uri": "x"},
        AiProxy: {"model_id": "anthropic.claude-3-sonnet"},
        ModelArtifacts: {},
    }[construct]
    with pytest.raises(NotImplementedError):
        construct(stack, "Stub", **kwargs)
