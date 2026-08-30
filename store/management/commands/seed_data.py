from django.core.management.base import BaseCommand

from store.models import Category, Product

CATEGORIES = ["Electronics", "Books", "Home & Kitchen", "Fashion"]

PRODUCTS = [
    ("Wireless Mouse", "Electronics", "19.99", None, 50),
    ("Mechanical Keyboard", "Electronics", "89.99", "74.99", 30),
    ("Noise Cancelling Headphones", "Electronics", "129.00", None, 15),
    ("Clean Code", "Books", "35.00", None, 40),
    ("Design Patterns", "Books", "42.50", "37.00", 25),
    ("Non-stick Frying Pan", "Home & Kitchen", "24.99", None, 60),
    ("Electric Kettle", "Home & Kitchen", "31.99", None, 45),
    ("Cotton T-Shirt", "Fashion", "12.99", None, 100),
    ("Denim Jacket", "Fashion", "59.99", "49.99", 20),
]


class Command(BaseCommand):
    help = "Populate the database with sample categories and products for local testing/demos."

    def handle(self, *args, **options):
        categories = {}
        for name in CATEGORIES:
            category, created = Category.objects.get_or_create(name=name)
            categories[name] = category
            self.stdout.write(f"{'Created' if created else 'Exists'} category: {name}")

        for name, cat_name, price, discount_price, stock in PRODUCTS:
            product, created = Product.objects.get_or_create(
                name=name,
                defaults={
                    "category": categories[cat_name],
                    "price": price,
                    "discount_price": discount_price,
                    "stock": stock,
                    "description": f"A great {name.lower()} you'll love.",
                },
            )
            self.stdout.write(f"{'Created' if created else 'Exists'} product: {name}")

        self.stdout.write(self.style.SUCCESS("Seed data ready."))
