"""Custom-resource handler that creates (and deletes) an OpenSearch Serverless
vector index for a Bedrock Knowledge Base.

CloudFormation has no native resource for an OSS data-plane index, so we sign a
plain HTTPS request to the collection endpoint with SigV4. Only ``boto3`` /
``botocore`` are used, both of which ship in the Lambda runtime — so the asset
needs no ``pip install`` and no Docker bundling.
"""

import json
import os
import time
import urllib.error
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

SERVICE = "aoss"


def _signed(method: str, url: str, body: str | None) -> urllib.request.Request:
    session = boto3.Session()
    creds = session.get_credentials().get_frozen_credentials()
    region = os.environ["AWS_REGION"]

    aws_req = AWSRequest(
        method=method,
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    # SigV4Auth derives the Host header from the URL and adds the SigV4 headers.
    SigV4Auth(creds, SERVICE, region).add_auth(aws_req)

    req = urllib.request.Request(
        url, data=body.encode() if body else None, method=method
    )
    for key, value in aws_req.headers.items():
        req.add_header(key, value)
    return req


def _put_index(endpoint: str, index: str, mapping: dict) -> None:
    url = f"{endpoint.rstrip('/')}/{index}"
    body = json.dumps(mapping)

    # The data-access policy and collection can take a little while to become
    # consistent after CloudFormation reports them created. Retry a few times.
    last_err: Exception | None = None
    for attempt in range(10):
        try:
            req = _signed("PUT", url, body)
            with urllib.request.urlopen(req, timeout=30) as resp:
                print(f"Index create response: {resp.status} {resp.read().decode()}")
            return
        except urllib.error.HTTPError as err:
            detail = err.read().decode()
            # 400 with resource_already_exists_exception means we're done.
            if "resource_already_exists_exception" in detail:
                print("Index already exists — nothing to do.")
                return
            last_err = RuntimeError(f"{err.code}: {detail}")
            print(f"Attempt {attempt + 1} failed: {last_err}")
        except urllib.error.URLError as err:
            last_err = err
            print(f"Attempt {attempt + 1} failed: {err}")
        time.sleep(15)
    raise RuntimeError(f"Failed to create index after retries: {last_err}")


def _delete_index(endpoint: str, index: str) -> None:
    url = f"{endpoint.rstrip('/')}/{index}"
    try:
        req = _signed("DELETE", url, None)
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"Index delete response: {resp.status}")
    except urllib.error.HTTPError as err:
        # A missing index on delete is fine — the stack is tearing down anyway.
        print(f"Delete returned {err.code} (ignored): {err.read().decode()}")


def on_event(event, _context):
    print(f"Event: {json.dumps(event)}")
    request_type = event["RequestType"]
    props = event["ResourceProperties"]

    endpoint = props["Endpoint"]
    index = props["IndexName"]
    physical_id = f"{endpoint}/{index}"

    if request_type in ("Create", "Update"):
        mapping = {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    props["VectorField"]: {
                        "type": "knn_vector",
                        "dimension": int(props["Dimension"]),
                        "method": {
                            "name": "hnsw",
                            "engine": "faiss",
                            "space_type": "l2",
                        },
                    },
                    props["TextField"]: {"type": "text"},
                    props["MetadataField"]: {"type": "text", "index": False},
                }
            },
        }
        _put_index(endpoint, index, mapping)
        # Give the index a moment to be queryable before the KB validates it.
        time.sleep(30)
    elif request_type == "Delete":
        _delete_index(endpoint, index)

    return {"PhysicalResourceId": physical_id}
