"""Shared fixtures for connections domain tests."""

import base64
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_secret() -> MagicMock:
    """A K8s Secret mock representing an S3 data connection."""
    secret = MagicMock()
    secret.metadata.name = "test-connection"
    secret.metadata.namespace = "test-project"
    secret.metadata.uid = "secret-uid"
    secret.metadata.creation_timestamp = "2024-01-01T00:00:00Z"
    secret.metadata.labels = {"opendatahub.io/dashboard": "true"}
    secret.metadata.annotations = {
        "opendatahub.io/connection-type": "s3",
        "opendatahub.io/managed": "true",
        "openshift.io/display-name": "Test S3 Connection",
    }
    secret.data = {
        "AWS_ACCESS_KEY_ID": base64.b64encode(b"TEST_ACCESS_KEY_ID_0001").decode(),
        "AWS_SECRET_ACCESS_KEY": base64.b64encode(b"TEST_SECRET_ACCESS_KEY_0001_NOT_REAL").decode(),
        "AWS_S3_ENDPOINT": base64.b64encode(b"https://s3.amazonaws.com").decode(),
        "AWS_S3_BUCKET": base64.b64encode(b"my-bucket").decode(),
        "AWS_DEFAULT_REGION": base64.b64encode(b"us-east-1").decode(),
    }
    return secret
