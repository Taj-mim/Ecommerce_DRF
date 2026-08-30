from django.db import transaction
from rest_framework import serializers

from store.models import Cart, CartItem, Category, Order, OrderItem, Product, ProductImage, Review


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------
class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source="products.count", read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "parent", "product_count")
        read_only_fields = ("slug",)


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image", "alt_text", "is_primary")


class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = Review
        fields = ("id", "product", "user", "rating", "comment", "created_at")
        read_only_fields = ("id", "user", "created_at")
        extra_kwargs = {"product": {"write_only": True}}

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer used for the product list / search endpoint."""

    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    average_rating = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "name", "slug", "category", "price", "discount_price",
            "current_price", "thumbnail", "in_stock", "average_rating",
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    """Full serializer used for the product detail endpoint: nested images
    and reviews, plus computed price/rating fields."""

    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(), write_only=True
    )
    images = ProductImageSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    average_rating = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "name", "slug", "description", "category", "category_id",
            "price", "discount_price", "current_price", "stock", "in_stock",
            "thumbnail", "images", "reviews", "average_rating", "is_active",
            "created_at", "updated_at",
        )
        read_only_fields = ("slug", "created_at", "updated_at")


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------
class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ("id", "product", "quantity", "subtotal", "added_at")


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ("id", "items", "total_items", "total_price", "updated_at")


class AddCartItemSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(
        source="product", queryset=Product.objects.filter(is_active=True)
    )
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        product = attrs["product"]
        if attrs["quantity"] > product.stock:
            raise serializers.ValidationError(
                {"quantity": f"Only {product.stock} unit(s) of '{product.name}' are in stock."}
            )
        return attrs


class UpdateCartItemSerializer(serializers.Serializer):
    item_id = serializers.PrimaryKeyRelatedField(source="item", queryset=CartItem.objects.all())
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        item = attrs["item"]
        if attrs["quantity"] > item.product.stock:
            raise serializers.ValidationError(
                {"quantity": f"Only {item.product.stock} unit(s) of '{item.product.name}' are in stock."}
            )
        return attrs


class RemoveCartItemSerializer(serializers.Serializer):
    item_id = serializers.PrimaryKeyRelatedField(source="item", queryset=CartItem.objects.all())


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("id", "product", "product_name", "price", "quantity", "subtotal")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = Order
        fields = (
            "id", "user", "status", "shipping_address", "city", "postal_code",
            "country", "total_amount", "items", "created_at", "updated_at",
        )
        read_only_fields = ("status", "total_amount", "created_at", "updated_at")


class CheckoutSerializer(serializers.Serializer):
    """Turns the current user's cart into an Order. Requires a non-empty
    cart and enough stock for every line item; both are re-checked here to
    avoid race conditions with whatever the cart said earlier."""

    shipping_address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100)

    def validate(self, attrs):
        user = self.context["request"].user
        cart = getattr(user, "cart", None)
        if not cart or not cart.items.exists():
            raise serializers.ValidationError("Your cart is empty.")

        for item in cart.items.select_related("product"):
            if item.quantity > item.product.stock:
                raise serializers.ValidationError(
                    f"Only {item.product.stock} unit(s) of '{item.product.name}' are in stock."
                )
        attrs["cart"] = cart
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        cart = validated_data.pop("cart")
        user = self.context["request"].user

        order = Order.objects.create(user=user, **validated_data)

        order_items = []
        for item in cart.items.select_related("product"):
            product = item.product
            order_items.append(
                OrderItem(
                    order=order,
                    product=product,
                    product_name=product.name,
                    price=product.current_price,
                    quantity=item.quantity,
                )
            )
            product.stock -= item.quantity
            product.save(update_fields=["stock"])

        OrderItem.objects.bulk_create(order_items)
        order.recalculate_total()
        cart.items.all().delete()
        return order
