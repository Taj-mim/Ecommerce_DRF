from django.db.models import Avg
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from store.filters import ProductFilter
from store.models import Cart, Category, Order, Product, Review
from store.permissions import IsAdminOrReadOnly, IsOwner, IsOwnerOrReadOnly
from store.serializers import (
    AddCartItemSerializer,
    CartSerializer,
    CategorySerializer,
    CheckoutSerializer,
    OrderSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    RemoveCartItemSerializer,
    ReviewSerializer,
    UpdateCartItemSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"


class ProductViewSet(viewsets.ModelViewSet):
    """
    /products/                 GET list, POST create (admin)
    /products/{slug}/          GET retrieve, PUT/PATCH/DELETE (admin)
    /products/?category=...&min_price=...&max_price=...&in_stock=true
    /products/?search=...      free-text search on name/description
    /products/?ordering=price,-created_at
    """

    queryset = Product.objects.filter(is_active=True).select_related("category").annotate(
        average_rating=Avg("reviews__rating")
    )
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"
    filterset_class = ProductFilter
    search_fields = ["name", "description", "category__name"]
    ordering_fields = ["price", "created_at", "average_rating"]

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Staff can see inactive/out-of-catalog products too (e.g. in the admin panel).
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = Product.objects.all().select_related("category").annotate(
                average_rating=Avg("reviews__rating")
            )
        return qs


class ReviewViewSet(viewsets.ModelViewSet):
    """
    /reviews/?product=<id>      list reviews for a product
    /reviews/                   POST to leave a review (one per user/product)
    """

    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filterset_fields = ["product", "rating"]

    def get_queryset(self):
        return Review.objects.select_related("user", "product").all()


class CartViewSet(viewsets.ViewSet):
    """Everything about the logged-in user's own cart. There's exactly one
    cart per user, so this deliberately isn't a standard list/detail
    ModelViewSet — every action operates on `request.user.cart`."""

    permission_classes = [permissions.IsAuthenticated]

    def _get_cart(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    def list(self, request):
        cart = self._get_cart(request)
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=["post"])
    def add_item(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data["product"]
        quantity = serializer.validated_data["quantity"]

        cart = self._get_cart(request)
        item, created = cart.items.get_or_create(product=product, defaults={"quantity": quantity})
        if not created:
            item.quantity += quantity
            if item.quantity > product.stock:
                return Response(
                    {"quantity": f"Only {product.stock} unit(s) of '{product.name}' are in stock."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            item.save()

        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def update_item(self, request):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.validated_data["item"]
        cart = self._get_cart(request)

        if item.cart_id != cart.id:
            return Response({"item_id": "Not found in your cart."}, status=status.HTTP_404_NOT_FOUND)

        item.quantity = serializer.validated_data["quantity"]
        item.save()
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=["post"])
    def remove_item(self, request):
        serializer = RemoveCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.validated_data["item"]
        cart = self._get_cart(request)

        if item.cart_id != cart.id:
            return Response({"item_id": "Not found in your cart."}, status=status.HTTP_404_NOT_FOUND)

        item.delete()
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=["post"])
    def clear(self, request):
        cart = self._get_cart(request)
        cart.items.all().delete()
        return Response(CartSerializer(cart).data)


class OrderViewSet(viewsets.ModelViewSet):
    """
    /orders/                    GET: own orders (all orders if staff)
    /orders/{id}/                GET: a single order (owner or staff only)
    /orders/checkout/            POST: turn the current cart into an order
    /orders/{id}/cancel/         POST: cancel a still-pending order
    Orders can't be created or edited directly through the normal
    create/update endpoints — checkout is the only way in, and status
    changes go through dedicated actions.
    """

    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = Order.objects.prefetch_related("items")
        return qs if user.is_staff else qs.filter(user=user)

    @action(detail=False, methods=["post"])
    def checkout(self, request):
        serializer = CheckoutSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status != Order.Status.PENDING:
            return Response(
                {"detail": f"Order in status '{order.status}' can no longer be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        return Response(OrderSerializer(order).data)
