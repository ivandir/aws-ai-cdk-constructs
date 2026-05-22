"""Bedrock Knowledge Base L3 construct.

Spinning up a Bedrock Knowledge Base by hand is deceptively fiddly: you need an
OpenSearch Serverless collection, three separate OSS policies (encryption,
network, data-access), a *pre-existing* vector index inside that collection, a
scoped service role, and only then the Knowledge Base and its data source. The
pre-existing index is the part that trips most people up — CloudFormation cannot
create an OSS index, so this construct does it with a small custom resource.

This construct wires all of that together with sensible production defaults.
"""

from __future__ import annotations

import json
import os
from typing import Optional, Sequence

from aws_cdk import (
    Aws,
    CustomResource,
    Duration,
    RemovalPolicy,
    aws_bedrock as bedrock,
    aws_cloudwatch as cloudwatch,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_opensearchserverless as aoss,
    aws_s3 as s3,
    custom_resources as cr,
)
from constructs import Construct

# Field names Bedrock uses by default when you create a Knowledge Base from the
# console. Keeping these as the defaults means the construct interoperates with
# anything that already expects the console layout.
_DEFAULT_VECTOR_FIELD = "bedrock-knowledge-base-default-vector"
_DEFAULT_TEXT_FIELD = "AMAZON_BEDROCK_TEXT_CHUNK"
_DEFAULT_METADATA_FIELD = "AMAZON_BEDROCK_METADATA"

_HANDLER_DIR = os.path.join(os.path.dirname(__file__), "_index_resource")


def _sanitize_collection_name(raw: str) -> str:
    """OSS collection names: lowercase, 3-32 chars, must start with a letter."""
    name = "".join(c for c in raw.lower() if c.isalnum() or c == "-").lstrip("-")
    if not name or not name[0].isalpha():
        name = "kb" + name
    return name[:32].rstrip("-") or "kb"


class BedrockKnowledgeBase(Construct):
    """A Bedrock Knowledge Base backed by OpenSearch Serverless.

    :param data_bucket: Existing S3 bucket holding the source documents. If
        omitted, a new private, encrypted bucket is created for you.
    :param embedding_model_id: Bedrock embedding model id. Defaults to
        ``amazon.titan-embed-text-v2:0``.
    :param embedding_dimension: Vector dimension of the embedding model. Must
        match the model (Titan v2 supports 256/512/1024). Defaults to 1024.
    :param collection_name: Override the generated OSS collection name.
    :param knowledge_base_name: Override the generated Knowledge Base name.
    :param inclusion_prefixes: S3 key prefixes to ingest. Defaults to the whole
        bucket.
    :param chunking_max_tokens: Fixed-size chunking token budget. Defaults to 300.
    :param chunking_overlap_percentage: Overlap between chunks. Defaults to 20.
    :param create_dashboard: Emit a CloudWatch dashboard. Defaults to True.
    :param vector_index_name: Name of the vector index created in the collection.
    :param removal_policy: Removal policy for the bucket/collection. Defaults to
        ``DESTROY`` so teardown is clean in dev; set ``RETAIN`` for production.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        data_bucket: Optional[s3.IBucket] = None,
        embedding_model_id: str = "amazon.titan-embed-text-v2:0",
        embedding_dimension: int = 1024,
        collection_name: Optional[str] = None,
        knowledge_base_name: Optional[str] = None,
        inclusion_prefixes: Optional[Sequence[str]] = None,
        chunking_max_tokens: int = 300,
        chunking_overlap_percentage: int = 20,
        create_dashboard: bool = True,
        vector_index_name: str = "bedrock-knowledge-base-default-index",
        removal_policy: RemovalPolicy = RemovalPolicy.DESTROY,
    ) -> None:
        super().__init__(scope, id)

        embedding_model_arn = (
            f"arn:aws:bedrock:{Aws.REGION}::foundation-model/{embedding_model_id}"
        )
        coll_name = _sanitize_collection_name(collection_name or f"{id}-{Aws.STACK_NAME}")

        # --- Source data bucket ------------------------------------------------
        self.data_bucket: s3.IBucket = data_bucket or s3.Bucket(
            self,
            "DataBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=removal_policy,
            auto_delete_objects=removal_policy == RemovalPolicy.DESTROY,
        )

        # --- Service role for the Knowledge Base ------------------------------
        self.role = iam.Role(
            self,
            "KnowledgeBaseRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Service role assumed by the Bedrock Knowledge Base",
        )
        self.role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[embedding_model_arn],
            )
        )
        self.data_bucket.grant_read(self.role)

        # --- OpenSearch Serverless collection + policies ----------------------
        encryption_policy = aoss.CfnSecurityPolicy(
            self,
            "EncryptionPolicy",
            name=f"{coll_name}-enc",
            type="encryption",
            policy=json.dumps(
                {
                    "Rules": [
                        {"ResourceType": "collection", "Resource": [f"collection/{coll_name}"]}
                    ],
                    "AWSOwnedKey": True,
                }
            ),
        )
        network_policy = aoss.CfnSecurityPolicy(
            self,
            "NetworkPolicy",
            name=f"{coll_name}-net",
            type="network",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {"ResourceType": "collection", "Resource": [f"collection/{coll_name}"]},
                            {"ResourceType": "dashboard", "Resource": [f"collection/{coll_name}"]},
                        ],
                        "AllowFromPublic": True,
                    }
                ]
            ),
        )

        self.collection = aoss.CfnCollection(
            self,
            "Collection",
            name=coll_name,
            type="VECTORSEARCH",
            description="Vector store for the Bedrock Knowledge Base",
        )
        self.collection.add_dependency(encryption_policy)
        self.collection.add_dependency(network_policy)

        # --- Custom resource that creates the vector index --------------------
        index_provider, index_role = self._build_index_provider(
            vector_index_name=vector_index_name,
            embedding_dimension=embedding_dimension,
        )

        # Data-access policy: both the KB role and the index Lambda role need
        # data-plane access to the collection and its indexes.
        data_access_policy = aoss.CfnAccessPolicy(
            self,
            "DataAccessPolicy",
            name=f"{coll_name}-access",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{coll_name}"],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:DescribeCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                ],
                            },
                            {
                                "ResourceType": "index",
                                "Resource": [f"index/{coll_name}/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument",
                                    "aoss:UpdateIndex",
                                    "aoss:DeleteIndex",
                                ],
                            },
                        ],
                        "Principal": [self.role.role_arn, index_role.role_arn],
                    }
                ]
            ),
        )

        index_cr = CustomResource(
            self,
            "VectorIndex",
            service_token=index_provider.service_token,
            properties={
                "Endpoint": self.collection.attr_collection_endpoint,
                "IndexName": vector_index_name,
                "VectorField": _DEFAULT_VECTOR_FIELD,
                "TextField": _DEFAULT_TEXT_FIELD,
                "MetadataField": _DEFAULT_METADATA_FIELD,
                "Dimension": embedding_dimension,
            },
        )
        index_cr.node.add_dependency(data_access_policy)
        index_cr.node.add_dependency(self.collection)

        # --- The Knowledge Base ------------------------------------------------
        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "KnowledgeBase",
            name=knowledge_base_name or f"{coll_name}-kb",
            role_arn=self.role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=embedding_model_arn,
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=self.collection.attr_arn,
                    vector_index_name=vector_index_name,
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        vector_field=_DEFAULT_VECTOR_FIELD,
                        text_field=_DEFAULT_TEXT_FIELD,
                        metadata_field=_DEFAULT_METADATA_FIELD,
                    ),
                ),
            ),
        )
        # The KB validates the index exists at create time, so it must wait for
        # both the index custom resource and the data-access policy.
        self.knowledge_base.node.add_dependency(index_cr)
        self.knowledge_base.node.add_dependency(data_access_policy)

        # --- Data source pointing at the S3 bucket ----------------------------
        s3_config = bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
            bucket_arn=self.data_bucket.bucket_arn,
            inclusion_prefixes=list(inclusion_prefixes) if inclusion_prefixes else None,
        )
        self.data_source = bedrock.CfnDataSource(
            self,
            "DataSource",
            name=f"{coll_name}-s3-source",
            knowledge_base_id=self.knowledge_base.attr_knowledge_base_id,
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=s3_config,
            ),
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="FIXED_SIZE",
                    fixed_size_chunking_configuration=bedrock.CfnDataSource.FixedSizeChunkingConfigurationProperty(
                        max_tokens=chunking_max_tokens,
                        overlap_percentage=chunking_overlap_percentage,
                    ),
                )
            ),
        )

        # Convenient public attributes
        self.knowledge_base_id = self.knowledge_base.attr_knowledge_base_id
        self.collection_arn = self.collection.attr_arn

        if create_dashboard:
            self._build_dashboard()

    # ------------------------------------------------------------------ helpers
    def _build_index_provider(self, *, vector_index_name: str, embedding_dimension: int):
        """Lambda-backed provider that PUTs the vector index into the collection."""
        index_role = iam.Role(
            self,
            "IndexFnRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        index_role.add_to_policy(
            iam.PolicyStatement(actions=["aoss:APIAccessAll"], resources=["*"])
        )

        index_fn = lambda_.Function(
            self,
            "IndexFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.on_event",
            code=lambda_.Code.from_asset(_HANDLER_DIR),
            timeout=Duration.minutes(5),
            memory_size=256,
            role=index_role,
            description="Creates the OpenSearch Serverless vector index for the Knowledge Base",
        )

        provider = cr.Provider(
            self,
            "IndexProvider",
            on_event_handler=index_fn,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )
        return provider, index_role

    def _build_dashboard(self) -> None:
        dashboard = cloudwatch.Dashboard(
            self,
            "Dashboard",
            dashboard_name=None,  # auto-named to avoid cross-stack collisions
        )

        def kb_metric(metric_name: str, stat: str = "Sum") -> cloudwatch.Metric:
            return cloudwatch.Metric(
                namespace="AWS/Bedrock",
                metric_name=metric_name,
                dimensions_map={"KnowledgeBaseId": self.knowledge_base_id},
                statistic=stat,
                period=Duration.minutes(5),
            )

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Knowledge Base — Ingestion",
                left=[kb_metric("IngestionDocumentCount"), kb_metric("IngestionFailureCount")],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Knowledge Base — Retrieval latency (ms)",
                left=[kb_metric("RetrieveLatency", stat="Average")],
                width=12,
            ),
        )
        self.dashboard = dashboard
