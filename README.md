# E-Commerce API — Django REST Framework

A backend-only e-commerce API: product catalog with categories, images and
reviews, a per-user cart, and a checkout flow that turns a cart into an
order (with stock validation and snapshotting). JWT authentication.

## Stack

- Django 5 + Django REST Framework
- SimpleJWT (access/refresh token auth)
- django-filter (filtering, search, ordering on the product list)
- SQLite by default, MySQL via one `.env` flag
- Pillow (product images / avatars)

## Project layout

```
ecommerce_drf/
├── manage.py
├── requirements.txt
├── .env.example
├── ecommerce/          # project settings, root urls
├── accounts/           # register, login, profile
└── store/              # catalog, cart, orders
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # then edit SECRET_KEY etc.

python manage.py migrate
python manage.py createsuperuser
python manage.py seed_data      # optional: adds sample categories/products

python manage.py runserver
```

API is now at `http://127.0.0.1:8000/api/v1/`, admin at `/admin/`.

### Switching to MySQL

In `.env`, set:

```
DB_ENGINE=mysql
DB_NAME=ecommerce_db
DB_USER=root
DB_PASSWORD=yourpassword
DB_HOST=127.0.0.1
DB_PORT=3306
```

Install the driver (`pip install mysqlclient` — needs MySQL dev headers on
your OS), create the database (`CREATE DATABASE ecommerce_db;`), then run
`python manage.py migrate` again.

## Running tests

```bash
python manage.py test
```

## Authentication

JWT via SimpleJWT. Send the access token as `Authorization: Bearer <token>`.

| Endpoint                        | Method    | Description                                            |
| ------------------------------- | --------- | ------------------------------------------------------ |
| `/api/v1/auth/register/`      | POST      | Create account, returns user + token pair              |
| `/api/v1/auth/token/`         | POST      | Login (`username`, `password`) → access + refresh |
| `/api/v1/auth/token/refresh/` | POST      | Exchange refresh token for a new access token          |
| `/api/v1/auth/profile/`       | GET/PATCH | View/update your own profile                           |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"asha","email":"asha@example.com","password":"StrongPass123","password2":"StrongPass123"}'

curl -X POST http://127.0.0.1:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"asha","password":"StrongPass123"}'
```

## Catalog

| Endpoint                          | Method       | Auth   | Description                                      |
| --------------------------------- | ------------ | ------ | ------------------------------------------------ |
| `/api/v1/categories/`           | GET          | Public | List categories                                  |
| `/api/v1/categories/`           | POST         | Staff  | Create category                                  |
| `/api/v1/products/`             | GET          | Public | List products — filter/search/order (see below) |
| `/api/v1/products/{slug}/`      | GET          | Public | Product detail (images, reviews, rating)         |
| `/api/v1/products/`             | POST         | Staff  | Create product                                   |
| `/api/v1/products/{slug}/`      | PATCH/DELETE | Staff  | Update/delete product                            |
| `/api/v1/reviews/?product={id}` | GET          | Public | Reviews for a product                            |
| `/api/v1/reviews/`              | POST         | Auth'd | Leave a review (one per user/product)            |

Product list query params:

```
/api/v1/products/?search=keyboard
/api/v1/products/?category=electronics&min_price=20&max_price=100
/api/v1/products/?in_stock=true&ordering=-average_rating
```

## Cart (per logged-in user)

| Endpoint                      | Method | Description                          |
| ----------------------------- | ------ | ------------------------------------ |
| `/api/v1/cart/`             | GET    | View your cart                       |
| `/api/v1/cart/add_item/`    | POST   | `{"product_id": 1, "quantity": 2}` |
| `/api/v1/cart/update_item/` | POST   | `{"item_id": 5, "quantity": 3}`    |
| `/api/v1/cart/remove_item/` | POST   | `{"item_id": 5}`                   |
| `/api/v1/cart/clear/`       | POST   | Empty the cart                       |

## Orders / Checkout

| Endpoint                        | Method | Description                           |
| ------------------------------- | ------ | ------------------------------------- |
| `/api/v1/orders/`             | GET    | Your orders (all orders if staff)     |
| `/api/v1/orders/{id}/`        | GET    | Order detail                          |
| `/api/v1/orders/checkout/`    | POST   | Build an order from your current cart |
| `/api/v1/orders/{id}/cancel/` | POST   | Cancel a still-pending order          |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/orders/checkout/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"shipping_address":"123 Main St","city":"Dhaka","postal_code":"1207","country":"Bangladesh"}'
```

Checkout re-validates stock at the moment of purchase, decrements product
stock, snapshots each item's name/price onto the `OrderItem` (so later price
changes never rewrite past orders), and empties the cart — all inside one
database transaction.

## Notable design choices

- **Permissions**: catalog is publicly readable, writes are staff-only
  (`IsAdminOrReadOnly`); reviews are owner-editable
  (`IsOwnerOrReadOnly`); orders are only visible to their owner or staff
  (`IsOwner`).
- **Cart is a `ViewSet`, not a `ModelViewSet`**: there's exactly one cart
  per user, so every action reads `request.user.cart` instead of an `{id}`
  in the URL.
- **`Profile` and `Cart` are auto-created** via a `post_save` signal on
  `User`, so the rest of the app can assume both always exist.
- **Slugs** are generated automatically from `name` (with a numeric suffix
  on collision) — the API never requires the client to supply one.
