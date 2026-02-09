# VibeMall - Django E-Commerce Platform

A modern e-commerce web application built with Django 5.2, featuring product management, shopping cart, wishlist, user authentication, and product reviews with admin approval.

## Features

- Product management: browse products with categories, ratings, and reviews
- Shopping cart: add/remove products, update quantities
- Wishlist: save favorite products for later
- User authentication: register, login, profile management
- Product reviews: user reviews with admin approval workflow
- Admin panel: full product, review, and content management
- Responsive design: modern UI with Bootstrap and custom styling
- Pagination: 16 products per page for optimal browsing

## Tech Stack

- Django 5.2
- Python 3.x
- SQLite (development)
- Bootstrap 5
- FontAwesome icons
- JavaScript (Vanilla)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/rajpaladiya2004/VibeMall.git
cd VibeMall
```

2. Create a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

5. Create a superuser:
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

7. Access the application:
- Main site: http://localhost:8000/
- Admin panel: http://localhost:8000/admin/

## Project Structure

```
VibeMall/
├── VibeMall/          # Project settings
├── Hub/               # Main app
│   ├── models.py      # Database models
│   ├── views.py       # View functions
│   ├── urls.py        # URL routing
│   ├── admin.py       # Admin configuration
│   ├── templates/     # HTML templates
│   └── static/        # CSS, JS, images
├── media/             # User uploads
└── manage.py          # Django management script
```

## Key Models

- Product: product information with pricing, inventory, categories
- ProductReview: user reviews with admin approval
- Cart: shopping cart items
- Wishlist: saved products
- UserProfile: extended user information

## Usage

### For Users:
- Browse products on the shop page
- Add products to cart or wishlist
- Submit reviews (requires login and admin approval)
- Manage profile and orders

### For Admins:
- Manage products, categories, and inventory
- Approve/reject user reviews
- Monitor sales and user activity
- Configure site content (sliders, banners, features)

## License

This project is open-source and available for educational purposes.

## Author

Raj Paladiya - https://github.com/rajpaladiya2004
