# aws-ai-cdk-constructs

Opinionated [AWS CDK](https://aws.amazon.com/cdk/) **L3 constructs** for production AI/ML infrastructure. The CDK construct ecosystem for AI is sparse — these are the working, sensible-default building blocks that save a team weeks of wiring IAM, vector stores, and scaling policies by hand.

Python, `pip`-installable, built on `aws-cdk-lib` v2.

```bash
pip install aws-ai-cdk-constructs
```

## Constructs

| Construct | Status | What it provisions |
| --- | --- | --- |
| **`BedrockKnowledgeBase`** | ✅ Implemented | Bedrock Knowledge Base + OpenSearch Serverless vector collection + vector index + scoped IAM + CloudWatch dashboard |
| `SageMakerEndpoint` | 🚧 Stub | Auto-scaling real-time inference endpoint |
| `AiProxy` | 🚧 Stub | API Gateway + Lambda proxy in front of Bedrock / SageMaker |
| `ModelArtifacts` | 🚧 Stub | Versioned S3 bucket + CloudFront for model assets |

The stubs ship with their **public API already defined** (constructor signatures + docstrings) so you can see where the library is going; instantiating one raises `NotImplementedError`.

## Quick start — `BedrockKnowledgeBase`

```python
import aws_cdk as cdk
from aws_ai_cdk_constructs import BedrockKnowledgeBase

class MyStack(cdk.Stack):
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        kb = BedrockKnowledgeBase(
            self, "DocsKb",
            embedding_model_id="amazon.titan-embed-text-v2:0",
            embedding_dimension=1024,
        )

        cdk.CfnOutput(self, "KnowledgeBaseId", value=kb.knowledge_base_id)
        cdk.CfnOutput(self, "DataBucket", value=kb.data_bucket.bucket_name)
```

That single construct creates **everything** a Bedrock Knowledge Base needs:

- a private, encrypted **S3 source bucket** (or bring your own via `data_bucket=`)
- an **OpenSearch Serverless collection** with all three required policies (encryption, network, data-access)
- the **vector index** inside that collection — the part CloudFormation can't do natively, handled here by a small SigV4-signed custom resource (no Docker, no extra dependencies)
- a correctly **scoped IAM service role** (embedding-model invoke + S3 read + OSS data access only)
- the **Knowledge Base** and an **S3 data source** with fixed-size chunking
- an optional **CloudWatch dashboard** for ingestion and retrieval metrics

### Why this is non-trivial by hand

Bedrock validates that the vector index already exists when the Knowledge Base is created — but CloudFormation has no resource type for an OpenSearch Serverless data-plane index. The usual workarounds are a manual console step or a bespoke Lambda. This construct bakes that in: a custom resource signs a request to the collection endpoint with SigV4 (using only the `boto3`/`botocore` already in the Lambda runtime) and creates the index with the right `knn_vector` mapping before the Knowledge Base is built.

### Key parameters

| Parameter | Default | Notes |
| --- | --- | --- |
| `data_bucket` | *new bucket* | Pass an existing `s3.IBucket` to ingest from it |
| `embedding_model_id` | `amazon.titan-embed-text-v2:0` | Any Bedrock embedding model |
| `embedding_dimension` | `1024` | Must match the model |
| `chunking_max_tokens` | `300` | Fixed-size chunk budget |
| `chunking_overlap_percentage` | `20` | Overlap between chunks |
| `create_dashboard` | `True` | CloudWatch dashboard for KB metrics |
| `removal_policy` | `DESTROY` | Set `RETAIN` for production |

## Try the example

```bash
cd examples/bedrock_knowledge_base
pip install -e ../..
cdk deploy        # requires AWS credentials and Bedrock model access
```

Then upload documents to the created bucket and start an ingestion job from the Bedrock console or API.

## Development

```bash
pip install -e ".[dev]"
pytest                 # synth-only tests, no AWS account needed
```

## Requirements

- Python ≥ 3.9
- `aws-cdk-lib` ≥ 2.140.0
- Bedrock model access enabled in your account/region for the embedding model you choose

## License

MIT © Ivandir Ndrio
