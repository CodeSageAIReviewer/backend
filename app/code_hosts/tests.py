from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from code_hosts.models.integration import CodeHostIntegration, CodeHostProvider
from code_hosts.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole


class WorkspaceAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="workspace_user", password="strong-pass"
        )
        self.client.force_authenticate(user=self.user)

    def test_create_workspace_assigns_owner_and_admin(self):
        response = self.client.post(reverse("workspace-create"), {"name": "AI Team"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "AI Team")
        self.assertEqual(response.data["owner_id"], self.user.id)
        self.assertEqual(response.data["role"], WorkspaceRole.ADMIN)
        self.assertTrue(response.data["created_at"].endswith("Z"))

        workspace = Workspace.objects.get(id=response.data["id"])
        membership = WorkspaceMembership.objects.get(
            workspace=workspace, user=self.user
        )
        self.assertEqual(membership.role, WorkspaceRole.ADMIN)

    def test_create_workspace_requires_name(self):
        response = self.client.post(reverse("workspace-create"), {})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"detail": "Name is required."})

    def test_create_workspace_rejects_invalid_length(self):
        response = self.client.post(reverse("workspace-create"), {"name": ""})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"detail": "Invalid name length."})

    def test_list_workspaces_shows_memberships(self):
        other_user = get_user_model().objects.create_user(
            username="second_user", password="second-pass"
        )
        workspace_one = Workspace.objects.create(name="First", owner=self.user)
        WorkspaceMembership.objects.create(
            workspace=workspace_one, user=self.user, role=WorkspaceRole.ADMIN
        )

        workspace_two = Workspace.objects.create(name="Second", owner=other_user)
        WorkspaceMembership.objects.create(
            workspace=workspace_two, user=self.user, role=WorkspaceRole.MEMBER
        )

        WorkspaceMembership.objects.create(
            workspace=workspace_two, user=other_user, role=WorkspaceRole.ADMIN
        )

        response = self.client.get(reverse("workspace-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        first_entry = response.data[0]
        self.assertEqual(first_entry["id"], workspace_one.id)
        self.assertEqual(first_entry["name"], "First")
        self.assertEqual(first_entry["owner_id"], self.user.id)
        self.assertEqual(first_entry["role"], WorkspaceRole.ADMIN)
        self.assertTrue(first_entry["created_at"].endswith("Z"))

        second_entry = response.data[1]
        self.assertEqual(second_entry["id"], workspace_two.id)
        self.assertEqual(second_entry["role"], WorkspaceRole.MEMBER)

    def test_delete_workspace_as_admin(self):
        workspace = Workspace.objects.create(name="DeleteMe", owner=self.user)
        WorkspaceMembership.objects.create(
            workspace=workspace, user=self.user, role=WorkspaceRole.ADMIN
        )

        response = self.client.delete(reverse("workspace-delete", args=[workspace.id]))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Workspace.objects.filter(id=workspace.id).exists())

    def test_delete_workspace_forbidden_for_member(self):
        other_user = get_user_model().objects.create_user(
            username="owner", password="owner-pass"
        )
        workspace = Workspace.objects.create(name="Foreign", owner=other_user)
        WorkspaceMembership.objects.create(
            workspace=workspace, user=other_user, role=WorkspaceRole.ADMIN
        )
        WorkspaceMembership.objects.create(
            workspace=workspace, user=self.user, role=WorkspaceRole.MEMBER
        )

        response = self.client.delete(reverse("workspace-delete", args=[workspace.id]))

        self.assertEqual(response.status_code, 403)

    def test_delete_workspace_returns_404_for_unknown(self):
        response = self.client.delete(reverse("workspace-delete", args=[999]))

        self.assertEqual(response.status_code, 404)

    def test_create_integration_as_admin(self):
        workspace = Workspace.objects.create(name="Team", owner=self.user)
        WorkspaceMembership.objects.create(
            workspace=workspace, user=self.user, role=WorkspaceRole.ADMIN
        )

        payload = {
            "name": "Main GitLab",
            "provider": "gitlab",
            "access_token": "token-123",
        }

        response = self.client.post(
            reverse("workspace-integration-create", args=[workspace.id]),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], payload["name"])
        self.assertEqual(response.data["workspace_id"], workspace.id)
        self.assertEqual(response.data["provider"], CodeHostProvider.GITLAB)
        self.assertTrue(response.data["created_at"].endswith("Z"))
        self.assertEqual(response.data["base_url"], "https://gitlab.com")

    def test_create_integration_requires_provider(self):
        workspace = Workspace.objects.create(name="Team", owner=self.user)
        WorkspaceMembership.objects.create(
            workspace=workspace, user=self.user, role=WorkspaceRole.ADMIN
        )

        payload = {
            "name": "Main GitLab",
            "access_token": "token-123",
        }

        response = self.client.post(
            reverse("workspace-integration-create", args=[workspace.id]),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"detail": "Provider is required."})

    def test_create_integration_forbidden_for_non_admin(self):
        other_user = get_user_model().objects.create_user(
            username="workspace_owner", password="owner-pass"
        )
        workspace = Workspace.objects.create(name="Foreign", owner=other_user)
        WorkspaceMembership.objects.create(
            workspace=workspace, user=self.user, role=WorkspaceRole.MEMBER
        )

        payload = {
            "name": "Main GitLab",
            "provider": "gitlab",
            "access_token": "token-123",
        }

        response = self.client.post(
            reverse("workspace-integration-create", args=[workspace.id]),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data,
            {
                "detail": "You do not have permission to add integrations to this workspace."
            },
        )

    def test_create_integration_returns_404_for_missing_membership(self):
        other_user = get_user_model().objects.create_user(
            username="workspace_owner", password="owner-pass"
        )
        workspace = Workspace.objects.create(name="Foreign", owner=other_user)

        payload = {
            "name": "Main GitLab",
            "provider": "gitlab",
            "access_token": "token-123",
        }

        response = self.client.post(
            reverse("workspace-integration-create", args=[workspace.id]),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_list_integrations_returns_entries(self):
        workspace = Workspace.objects.create(name="Team", owner=self.user)
        WorkspaceMembership.objects.create(
            workspace=workspace, user=self.user, role=WorkspaceRole.ADMIN
        )

        CodeHostIntegration.objects.create(
            workspace=workspace,
            name="Main GitLab",
            provider=CodeHostProvider.GITLAB,
            base_url="https://gitlab.com",
            access_token="token-1",
        )
        CodeHostIntegration.objects.create(
            workspace=workspace,
            name="Company GitHub",
            provider=CodeHostProvider.GITHUB,
            base_url="https://api.github.com",
            access_token="token-2",
        )

        response = self.client.get(
            reverse("workspace-integration-list", args=[workspace.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        first_entry = response.data[0]
        self.assertEqual(first_entry["provider"], CodeHostProvider.GITLAB)
        self.assertTrue(first_entry["created_at"].endswith("Z"))

    def test_list_integrations_forbidden_for_non_member(self):
        other_user = get_user_model().objects.create_user(
            username="workspace_owner", password="owner-pass"
        )
        workspace = Workspace.objects.create(name="Foreign", owner=other_user)

        response = self.client.get(
            reverse("workspace-integration-list", args=[workspace.id])
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data, {"detail": "You do not have access to this workspace."}
        )
