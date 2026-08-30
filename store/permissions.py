from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """Anyone can read (list/retrieve); only staff/admin users can
    create, update, or delete. Used for Category, Product, ProductImage."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Anyone can read; only the object's owner can edit/delete it.
    Used for Review, where `obj.user` is the owner."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user_id == request.user.id


class IsOwner(permissions.BasePermission):
    """Object is only visible/editable by its owner (or staff).
    Used for Order, where `obj.user` is the owner."""

    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.user_id == request.user.id
