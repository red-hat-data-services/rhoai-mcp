"""Tests for ConnectionClient operations."""

from unittest.mock import MagicMock

import pytest

from rhoai_mcp.domains.connections.client import ConnectionClient
from rhoai_mcp.domains.connections.models import DataConnection, S3DataConnectionCreate


class TestListDataConnections:
    """Tests for ConnectionClient.list_data_connections."""

    @pytest.fixture
    def mock_k8s(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def client(self, mock_k8s: MagicMock) -> ConnectionClient:
        return ConnectionClient(mock_k8s)

    def test_list_data_connections_filters_by_annotation(
        self,
        client: ConnectionClient,
        mock_k8s: MagicMock,
        sample_secret: MagicMock,
    ) -> None:
        """Only secrets with CONNECTION_TYPE annotation are returned."""
        # Secret without the connection-type annotation (not a data connection)
        non_connection_secret = MagicMock()
        non_connection_secret.metadata.name = "plain-secret"
        non_connection_secret.metadata.namespace = "test-project"
        non_connection_secret.metadata.annotations = {}

        mock_k8s.list_secrets.return_value = [
            sample_secret,
            non_connection_secret,
        ]

        results = client.list_data_connections("test-project")

        assert len(results) == 1
        assert results[0]["name"] == "test-connection"
        assert results[0]["type"] == "s3"
        assert results[0]["display_name"] == "Test S3 Connection"
        assert results[0]["bucket"] == "my-bucket"
        assert results[0]["endpoint"] == "https://s3.amazonaws.com"
        assert results[0]["region"] == "us-east-1"

    def test_list_data_connections_empty(
        self,
        client: ConnectionClient,
        mock_k8s: MagicMock,
    ) -> None:
        """Returns empty list when no secrets match."""
        mock_k8s.list_secrets.return_value = []

        results = client.list_data_connections("test-project")

        assert results == []
        mock_k8s.list_secrets.assert_called_once()


class TestGetDataConnection:
    """Tests for ConnectionClient.get_data_connection."""

    @pytest.fixture
    def mock_k8s(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def client(self, mock_k8s: MagicMock) -> ConnectionClient:
        return ConnectionClient(mock_k8s)

    def test_get_data_connection_masks_secrets(
        self,
        client: ConnectionClient,
        mock_k8s: MagicMock,
        sample_secret: MagicMock,
    ) -> None:
        """Access key is masked when mask_secrets=True (default)."""
        mock_k8s.get_secret.return_value = sample_secret

        conn = client.get_data_connection("test-connection", "test-project")

        assert isinstance(conn, DataConnection)
        # "TEST_ACCESS_KEY_ID_0001" -> first 4 + "****" + last 4
        assert conn.aws_access_key_id == "TEST****0001"
        assert conn.aws_s3_bucket == "my-bucket"
        assert conn.aws_s3_endpoint == "https://s3.amazonaws.com"
        mock_k8s.get_secret.assert_called_once_with("test-connection", "test-project")

    def test_get_data_connection_with_mask_false(
        self,
        sample_secret: MagicMock,
    ) -> None:
        """Full access key returned when mask_secrets=False."""
        conn = DataConnection.from_secret(sample_secret, mask_secrets=False)

        assert conn.aws_access_key_id == "TEST_ACCESS_KEY_ID_0001"


class TestCreateDataConnection:
    """Tests for ConnectionClient.create_s3_data_connection."""

    @pytest.fixture
    def mock_k8s(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def client(self, mock_k8s: MagicMock) -> ConnectionClient:
        return ConnectionClient(mock_k8s)

    def test_create_s3_data_connection(
        self,
        client: ConnectionClient,
        mock_k8s: MagicMock,
        sample_secret: MagicMock,
    ) -> None:
        """Verify k8s.create_secret is called with correct arguments."""
        mock_k8s.create_secret.return_value = sample_secret

        request = S3DataConnectionCreate(
            name="test-connection",
            namespace="test-project",
            display_name="Test S3 Connection",
            aws_access_key_id="TEST_ACCESS_KEY_ID_0001",
            aws_secret_access_key="TEST_SECRET_ACCESS_KEY_0001_NOT_REAL",
            aws_s3_endpoint="https://s3.amazonaws.com",
            aws_s3_bucket="my-bucket",
            aws_default_region="us-east-1",
        )

        result = client.create_s3_data_connection(request)

        assert isinstance(result, DataConnection)
        mock_k8s.create_secret.assert_called_once()
        call_kwargs = mock_k8s.create_secret.call_args
        assert call_kwargs.kwargs["name"] == "test-connection"
        assert call_kwargs.kwargs["namespace"] == "test-project"
        assert call_kwargs.kwargs["string_data"] is True
        assert call_kwargs.kwargs["data"]["AWS_ACCESS_KEY_ID"] == "TEST_ACCESS_KEY_ID_0001"
        assert call_kwargs.kwargs["data"]["AWS_S3_BUCKET"] == "my-bucket"
        # Annotations should include connection-type and display-name
        annotations = call_kwargs.kwargs["annotations"]
        assert annotations["opendatahub.io/connection-type"] == "s3"
        assert annotations["opendatahub.io/managed"] == "true"
        assert annotations["openshift.io/display-name"] == "Test S3 Connection"


class TestDeleteDataConnection:
    """Tests for ConnectionClient.delete_data_connection."""

    def test_delete_data_connection(self) -> None:
        """Verify k8s.delete_secret is called with name and namespace."""
        mock_k8s = MagicMock()
        client = ConnectionClient(mock_k8s)

        client.delete_data_connection("test-connection", "test-project")

        mock_k8s.delete_secret.assert_called_once_with("test-connection", "test-project")
