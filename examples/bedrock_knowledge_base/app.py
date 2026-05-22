#!/usr/bin/env python3
"""Deployable example: a Bedrock Knowledge Base over an S3 document bucket.

    cd examples/bedrock_knowledge_base
    pip install -e ../..        # install the constructs library
    cdk deploy                  # needs AWS creds + Bedrock model access

After deploy, upload documents to the created bucket and start an ingestion job
from the Bedrock console (or via the API) to populate the vector index.
"""

import aws_cdk as cdk

from aws_ai_cdk_constructs import BedrockKnowledgeBase


class ExampleStack(cdk.Stack):
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        kb = BedrockKnowledgeBase(
            self,
            "DocsKb",
            embedding_model_id="amazon.titan-embed-text-v2:0",
            embedding_dimension=1024,
            chunking_max_tokens=300,
            chunking_overlap_percentage=20,
        )

        cdk.CfnOutput(self, "KnowledgeBaseId", value=kb.knowledge_base_id)
        cdk.CfnOutput(self, "DataBucketName", value=kb.data_bucket.bucket_name)
        cdk.CfnOutput(self, "CollectionArn", value=kb.collection_arn)


app = cdk.App()
ExampleStack(app, "BedrockKnowledgeBaseExample")
app.synth()
