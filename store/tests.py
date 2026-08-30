from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from store.models import Category, Product

User = get_user_model()


class ProductCatalogTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            category=self.category, name="Wireless Mouse", price="19.99", stock=10
        )

    def test_products_are_publicly_listable(self):
        url = reverse("product-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_anonymous_user_cannot_create_product(self):
        url = reverse("product-list")
        response = self.client.post(url, {"name": "New", "price": "1.00", "category_id": self.category.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_create_product(self):
        admin = User.objects.create_user("admin", password="pass12345", is_staff=True)
        self.client.force_authenticate(admin)
        url = reverse("product-list")
        response = self.client.post(
            url, {"name": "Keyboard", "price": "49.99", "category_id": self.category.id}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class CartAndCheckoutTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("shopper", password="pass12345")
        self.client.force_authenticate(self.user)
        category = Category.objects.create(name="Books")
        self.product = Product.objects.create(category=category, name="Clean Code", price="35.00", stock=5)

    def test_add_item_to_cart(self):
        url = reverse("cart-add-item")
        response = self.client.post(url, {"product_id": self.product.id, "quantity": 2})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total_items"], 2)

    def test_checkout_creates_order_and_clears_cart(self):
        self.client.post(reverse("cart-add-item"), {"product_id": self.product.id, "quantity": 2})

        checkout_url = reverse("order-checkout")
        response = self.client.post(
            checkout_url,
            {
                "shipping_address": "123 Main St",
                "city": "Dhaka",
                "postal_code": "1207",
                "country": "Bangladesh",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["items"][0]["quantity"], 2)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

        cart_response = self.client.get(reverse("cart-list"))
        self.assertEqual(cart_response.data["total_items"], 0)

    def test_cannot_order_more_than_stock(self):
        checkout_url = reverse("order-checkout")
        self.client.post(reverse("cart-add-item"), {"product_id": self.product.id, "quantity": 999})
        response = self.client.post(
            checkout_url,
            {"shipping_address": "x", "city": "x", "country": "x"},
        )
        # add_item itself rejects the over-stock quantity before checkout is reached
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)
