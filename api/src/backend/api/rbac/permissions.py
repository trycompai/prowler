from enum import Enum
from typing import Optional

from django.db.models import QuerySet
from rest_framework.permissions import BasePermission

from api.db_router import MainRouter
from api.models import Provider, Role, User, UserRoleRelationship


class Permissions(Enum):
    MANAGE_USERS = "manage_users"
    MANAGE_ACCOUNT = "manage_account"
    MANAGE_BILLING = "manage_billing"
    MANAGE_PROVIDERS = "manage_providers"
    MANAGE_INTEGRATIONS = "manage_integrations"
    MANAGE_SCANS = "manage_scans"
    UNLIMITED_VISIBILITY = "unlimited_visibility"


class HasPermissions(BasePermission):
    """
    Custom permission to check if the user's role has the required permissions.
    The required permissions should be specified in the view as a list in `required_permissions`.
    """

    def has_permission(self, request, view):
        required_permissions = getattr(view, "required_permissions", [])
        if not required_permissions:
            return True

        # Get tenant_id from auth token
        tenant_id = None
        if request.auth:
            tenant_id = request.auth.get("tenant_id")
        
        if not tenant_id:
            return False

        # Query UserRoleRelationship directly through admin_db to bypass RLS
        # Filter by both user and tenant_id, then get the roles
        relationships = UserRoleRelationship.objects.using(MainRouter.admin_db).filter(
            user_id=request.user.id,
            tenant_id=tenant_id
        ).select_related('role')
        
        if not relationships.exists():
            return False

        # Get the first role from the relationship
        role = relationships[0].role
        
        # Check all required permissions
        for perm in required_permissions:
            if not getattr(role, perm.value, False):
                return False

        return True


def get_role(user: User, tenant_id: Optional[str] = None) -> Optional[Role]:
    """
    Retrieve the first role assigned to the given user, optionally filtered by tenant_id.

    Args:
        user: The user to get the role for
        tenant_id: Optional tenant_id to filter roles by

    Returns:
        The user's first Role instance if the user has any roles for the tenant, otherwise None.
    """
    if tenant_id:
        # Query UserRoleRelationship directly through admin_db to bypass RLS
        relationships = UserRoleRelationship.objects.using(MainRouter.admin_db).filter(
            user_id=user.id,
            tenant_id=tenant_id
        ).select_related('role')
        
        if relationships.exists():
            return relationships[0].role
        return None
    
    # Fallback to original behavior if no tenant_id provided
    return user.roles.first()


def get_providers(role: Role) -> QuerySet[Provider]:
    """
    Return a distinct queryset of Providers accessible by the given role.

    If the role has no associated provider groups, an empty queryset is returned.

    Args:
        role: A Role instance.

    Returns:
        A QuerySet of Provider objects filtered by the role's provider groups.
        If the role has no provider groups, returns an empty queryset.
    """
    tenant = role.tenant
    provider_groups = role.provider_groups.all()
    if not provider_groups.exists():
        return Provider.objects.none()

    return Provider.objects.filter(
        tenant=tenant, provider_groups__in=provider_groups
    ).distinct()
