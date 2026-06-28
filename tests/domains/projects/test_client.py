"""Tests for ProjectClient operations."""

from unittest.mock import MagicMock

import pytest

from rhoai_mcp.domains.projects.client import ProjectClient
from rhoai_mcp.domains.projects.models import DataScienceProject, ProjectCreate
from rhoai_mcp.utils.errors import NotFoundError


@pytest.fixture
def mock_k8s() -> MagicMock:
    """Create a mock K8sClient."""
    return MagicMock()


@pytest.fixture
def client(mock_k8s: MagicMock) -> ProjectClient:
    """Create a ProjectClient with mocked K8sClient."""
    return ProjectClient(mock_k8s)


def _make_namespace(
    name: str = "test-project",
    display_name: str = "Test Project",
    description: str = "A test project",
    dashboard: str = "true",
    modelmesh: str = "false",
    phase: str = "Active",
) -> MagicMock:
    """Build a mock namespace object with the given attributes."""
    ns = MagicMock()
    ns.metadata.name = name
    ns.metadata.namespace = None
    ns.metadata.uid = "test-uid"
    ns.metadata.creation_timestamp = "2024-01-01T00:00:00Z"
    ns.metadata.labels = {
        "opendatahub.io/dashboard": dashboard,
        "modelmesh-enabled": modelmesh,
    }
    ns.metadata.annotations = {
        "openshift.io/display-name": display_name,
        "openshift.io/description": description,
    }
    ns.status.phase = phase
    return ns


class TestListProjects:
    """Tests for ProjectClient.list_projects."""

    def test_list_projects_returns_ds_projects(
        self, client: ProjectClient, mock_k8s: MagicMock
    ) -> None:
        """Should return a list of DataScienceProject from listed namespaces."""
        ns1 = _make_namespace(name="project-a", display_name="Project A")
        ns2 = _make_namespace(name="project-b", display_name="Project B")
        mock_k8s.list_projects.return_value = [ns1, ns2]

        result = client.list_projects()

        assert len(result) == 2
        assert all(isinstance(p, DataScienceProject) for p in result)
        assert result[0].metadata.name == "project-a"
        assert result[1].metadata.name == "project-b"
        mock_k8s.list_projects.assert_called_once()
        call_kwargs = mock_k8s.list_projects.call_args
        assert "label_selector" in call_kwargs.kwargs

    def test_list_projects_empty(self, client: ProjectClient, mock_k8s: MagicMock) -> None:
        """Should return an empty list when no projects exist."""
        mock_k8s.list_projects.return_value = []

        result = client.list_projects()

        assert result == []
        mock_k8s.list_projects.assert_called_once()


class TestGetProject:
    """Tests for ProjectClient.get_project."""

    def test_get_project_success(self, client: ProjectClient, mock_k8s: MagicMock) -> None:
        """Should return a DataScienceProject for a valid DS namespace."""
        ns = _make_namespace(name="my-project", display_name="My Project")
        mock_k8s.get_namespace.return_value = ns

        result = client.get_project("my-project")

        assert isinstance(result, DataScienceProject)
        assert result.metadata.name == "my-project"
        assert result.display_name == "My Project"
        mock_k8s.get_namespace.assert_called_once_with("my-project")

    def test_get_project_not_ds_project_raises(
        self, client: ProjectClient, mock_k8s: MagicMock
    ) -> None:
        """Should raise NotFoundError when namespace lacks the dashboard label."""
        ns = MagicMock()
        ns.metadata.name = "plain-namespace"
        ns.metadata.namespace = None
        ns.metadata.uid = "uid"
        ns.metadata.creation_timestamp = "2024-01-01T00:00:00Z"
        ns.metadata.labels = {"some-label": "value"}
        ns.metadata.annotations = {}
        ns.status.phase = "Active"
        mock_k8s.get_namespace.return_value = ns

        with pytest.raises(NotFoundError, match="DataScienceProject"):
            client.get_project("plain-namespace")


class TestCreateProject:
    """Tests for ProjectClient.create_project."""

    def test_create_project_success(self, client: ProjectClient, mock_k8s: MagicMock) -> None:
        """Should call create_namespace with dashboard labels and annotations."""
        created_ns = _make_namespace(
            name="new-project",
            display_name="New Project",
            description="A new project",
        )
        mock_k8s.create_namespace.return_value = created_ns

        request = ProjectCreate(
            name="new-project",
            display_name="New Project",
            description="A new project",
        )
        result = client.create_project(request)

        assert isinstance(result, DataScienceProject)
        assert result.metadata.name == "new-project"
        mock_k8s.create_namespace.assert_called_once()

        call_kwargs = mock_k8s.create_namespace.call_args.kwargs
        assert call_kwargs["name"] == "new-project"
        # Dashboard label must be present
        assert call_kwargs["labels"]["opendatahub.io/dashboard"] == "true"
        # Default is KServe (single-model) => modelmesh-enabled = false
        assert call_kwargs["labels"]["modelmesh-enabled"] == "false"
        # Annotations
        assert call_kwargs["annotations"]["openshift.io/display-name"] == "New Project"
        assert call_kwargs["annotations"]["openshift.io/description"] == "A new project"

    def test_create_project_with_modelmesh(
        self, client: ProjectClient, mock_k8s: MagicMock
    ) -> None:
        """Should set modelmesh-enabled=true when enable_modelmesh is True."""
        created_ns = _make_namespace(name="mm-project", modelmesh="true")
        mock_k8s.create_namespace.return_value = created_ns

        request = ProjectCreate(name="mm-project", enable_modelmesh=True)
        client.create_project(request)

        call_kwargs = mock_k8s.create_namespace.call_args.kwargs
        assert call_kwargs["labels"]["modelmesh-enabled"] == "true"


class TestDeleteProject:
    """Tests for ProjectClient.delete_project."""

    def test_delete_project_success(self, client: ProjectClient, mock_k8s: MagicMock) -> None:
        """Should verify the project exists then delete the namespace."""
        ns = _make_namespace(name="doomed-project")
        mock_k8s.get_namespace.return_value = ns

        client.delete_project("doomed-project")

        mock_k8s.get_namespace.assert_called_once_with("doomed-project")
        mock_k8s.delete_namespace.assert_called_once_with("doomed-project")


class TestSetModelServingMode:
    """Tests for ProjectClient.set_model_serving_mode."""

    def test_set_model_serving_mode_kserve(
        self, client: ProjectClient, mock_k8s: MagicMock
    ) -> None:
        """Should patch with modelmesh-enabled=false for single-model (KServe)."""
        ns = _make_namespace(name="my-project")
        mock_k8s.get_namespace.return_value = ns
        mock_k8s.patch_project.return_value = ns

        result = client.set_model_serving_mode("my-project", enable_modelmesh=False)

        assert isinstance(result, DataScienceProject)
        mock_k8s.patch_project.assert_called_once_with(
            "my-project", labels={"modelmesh-enabled": "false"}
        )

    def test_set_model_serving_mode_modelmesh(
        self, client: ProjectClient, mock_k8s: MagicMock
    ) -> None:
        """Should patch with modelmesh-enabled=true for multi-model (ModelMesh)."""
        ns = _make_namespace(name="my-project", modelmesh="true")
        mock_k8s.get_namespace.return_value = ns
        mock_k8s.patch_project.return_value = ns

        result = client.set_model_serving_mode("my-project", enable_modelmesh=True)

        assert isinstance(result, DataScienceProject)
        mock_k8s.patch_project.assert_called_once_with(
            "my-project", labels={"modelmesh-enabled": "true"}
        )
