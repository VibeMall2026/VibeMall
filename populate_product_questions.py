#!/usr/bin/env python
import os
from datetime import timedelta

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone

from Hub.models import Product, ProductQuestion


NAME_PAIRS = [
    ('Aarav', 'Sharma'),
    ('Vivaan', 'Patel'),
    ('Aditya', 'Verma'),
    ('Arjun', 'Mehta'),
    ('Krishna', 'Nair'),
    ('Ishaan', 'Reddy'),
    ('Sai', 'Kulkarni'),
    ('Rahul', 'Yadav'),
    ('Rohan', 'Bansal'),
    ('Mohit', 'Agarwal'),
    ('Ananya', 'Gupta'),
    ('Diya', 'Joshi'),
    ('Kavya', 'Iyer'),
    ('Priya', 'Singh'),
    ('Sneha', 'Choudhary'),
    ('Neha', 'Mishra'),
    ('Aditi', 'Desai'),
    ('Pooja', 'Malhotra'),
    ('Meera', 'Kapoor'),
    ('Riya', 'Jain'),
    ('Saanvi', 'Tiwari'),
    ('Nisha', 'Pillai'),
    ('Tanvi', 'Chauhan'),
    ('Harsh', 'Trivedi'),
    ('Karan', 'Arora'),
    ('Yash', 'Thakur'),
    ('Manav', 'Saxena'),
    ('Deepak', 'Rawat'),
    ('Nitin', 'Dubey'),
    ('Siddharth', 'Bhat'),
    ('Lakshmi', 'Menon'),
    ('Bhavna', 'Soni'),
    ('Payal', 'Bhatt'),
    ('Shreya', 'Kamble'),
    ('Komal', 'Prajapati'),
    ('Ritika', 'Seth'),
    ('Alok', 'Nagpal'),
    ('Varun', 'Pawar'),
    ('Abhishek', 'Goswami'),
    ('Mayank', 'Saini'),
    ('Tanya', 'Rastogi'),
    ('Ira', 'Bora'),
    ('Mitali', 'Khatri'),
    ('Dev', 'Solanki'),
    ('Parth', 'Vora'),
    ('Nakul', 'Chawla'),
    ('Heena', 'Bedi'),
    ('Jiya', 'Sachdeva'),
    ('Palak', 'Srinivasan'),
    ('Reyansh', 'Bedi'),
    ('Sakshi', 'Tomar'),
    ('Avni', 'Garg'),
    ('Dhruv', 'Lohia'),
    ('Pranav', 'Kohli'),
    ('Madhav', 'Rana'),
    ('Nandini', 'Mahajan'),
    ('Ishita', 'Bajaj'),
    ('Rudra', 'Ahuja'),
    ('Sanika', 'Bhosale'),
    ('Vedant', 'Madan'),
]


def product_context(product, variant):
    category = (product.category or '').upper()
    product_name = product.name.strip()
    brand = (product.brand or 'this product').strip()
    sub_category = (product.sub_category or 'regular use').strip()
    return_days = product.return_days or 7

    if 'LEHENGA' in product_name.upper() or 'WOMEN WEAR' in category or 'LEHENGA' in sub_category.upper():
        fashion_sets = [
            {
                'questions': [
                    f"Is {product_name} suitable for weddings and sangeet functions?",
                    f"Does {product_name} come with blouse fabric and dupatta as shown?",
                ],
                'answers': [
                    f"Yes, {product_name} is styled for festive and wedding occasions. Please check the product images for the exact finish and embroidery look.",
                    f"The set details shown on the product page are included with {product_name}. If a stitched blouse is not mentioned, the blouse fabric is provided unstitched.",
                ],
            },
            {
                'questions': [
                    f"Will {product_name} be comfortable for long function hours?",
                    f"Is the overall look of {product_name} more traditional or party wear style?",
                ],
                'answers': [
                    f"Yes, {product_name} is intended for festive wear and family occasions. Comfort also depends on the fabric, fall, and the blouse stitching you choose.",
                    f"{product_name} has a festive ethnic look that works well for celebrations, parties, and wedding events. The styling can be adjusted with jewellery and footwear.",
                ],
            },
            {
                'questions': [
                    f"Can {product_name} be ordered for engagement or reception wear?",
                    f"Does {brand} {product_name} look close to the catalog photos?",
                ],
                'answers': [
                    f"Yes, many customers choose {product_name} for engagement, reception, and festive gatherings. It is best suited for dressy occasions rather than daily wear.",
                    f"The catalog images are meant to represent the design, color family, and work pattern of {product_name}. Slight variations may happen because of lighting and display settings.",
                ],
            },
        ]
        return fashion_sets[variant % len(fashion_sets)]

    if category == 'HOME_KITCHEN' or 'HOME DECOR' in sub_category.upper() or 'WALL' in product_name.upper() or 'PLANT' in product_name.upper():
        decor_sets = [
            {
                'questions': [
                    f"Will {product_name} look good in a living room or entry area?",
                    f"Is {product_name} easy to clean and maintain at home?",
                ],
                'answers': [
                    f"Yes, {product_name} works well in living rooms, entry spaces, and side corners. Its design is best suited for everyday home styling.",
                    f"Yes, {product_name} is easy to maintain. A soft dry cloth or light dusting is usually enough for regular care.",
                ],
            },
            {
                'questions': [
                    f"Can {product_name} be used in a bedroom shelf or balcony corner?",
                    f"Does {product_name} need any special care after delivery?",
                ],
                'answers': [
                    f"Yes, {product_name} can be styled in bedroom shelves, balconies, study tables, or compact decor corners depending on the available space.",
                    f"No special setup is usually needed for {product_name}. Just unpack carefully and place it on a clean, dry surface.",
                ],
            },
            {
                'questions': [
                    f"Will {brand} {product_name} suit a modern home setup?",
                    f"Is {product_name} a good option for gifting during housewarming or festivals?",
                ],
                'answers': [
                    f"Yes, {product_name} can blend well with both modern and classic home decor themes, especially in everyday display areas.",
                    f"Yes, {product_name} is a practical gifting option for housewarming, festive visits, and decor lovers.",
                ],
            },
        ]
        return decor_sets[variant % len(decor_sets)]

    if category == 'MOBILES' or any(keyword in product_name.upper() for keyword in ['PHONE', 'CHARGER', 'CABLE', 'HEADPHONE', 'KEYBOARD', 'MOUSE', 'WEBCAM', 'LAPTOP', 'USB']):
        tech_sets = [
            {
                'questions': [
                    f"Is {product_name} good for daily use and long hours?",
                    f"Does {product_name} support standard devices available in India?",
                ],
                'answers': [
                    f"Yes, {product_name} is suitable for daily use. It is designed to handle regular work, study, or entertainment needs comfortably.",
                    f"Yes, {product_name} is intended for standard compatible devices. Please match the product specifications on the page with your device before ordering.",
                ],
            },
            {
                'questions': [
                    f"How is the performance of {product_name} for regular home and office use?",
                    f"Will {brand} {product_name} work well for everyday charging or connectivity needs?",
                ],
                'answers': [
                    f"{product_name} is suitable for regular use and is meant for practical daily tasks. The exact experience depends on how you plan to use it.",
                    f"Yes, {product_name} is meant for routine use cases. Please review the compatibility and feature details on the product page before purchase.",
                ],
            },
            {
                'questions': [
                    f"Is {product_name} a good choice for students or work from home use?",
                    f"Does {product_name} match the specifications shown on the listing?",
                ],
                'answers': [
                    f"Yes, {product_name} is a practical option for students, office use, and general personal use depending on your requirement.",
                    f"Yes, {product_name} is listed with its intended specifications and usage details. Please review the listing carefully for the exact fit.",
                ],
            },
        ]
        return tech_sets[variant % len(tech_sets)]

    generic_sets = [
        {
            'questions': [
                f"How is the quality of {product_name} for regular use?",
                f"Can I return {product_name} if it does not match my expectation?",
            ],
            'answers': [
                f"{product_name} is selected for dependable everyday use. The material, finish, and product presentation should match the listing details.",
                f"Yes, this product follows the store return policy. Eligible returns can be requested within {return_days} days if the item is unused and in original condition.",
            ],
        },
        {
            'questions': [
                f"Is {product_name} worth ordering for personal use or gifting?",
                f"Will I receive {product_name} exactly as per the product photos?",
            ],
            'answers': [
                f"Yes, {product_name} is suitable for personal use and can also work well as a gifting option depending on the occasion.",
                f"The product design and key details are represented on the listing page for {product_name}. Minor visual differences can happen because of lighting or screen settings.",
            ],
        },
        {
            'questions': [
                f"Is {brand} {product_name} suitable for everyday use?",
                f"What is the return window for {product_name}?",
            ],
            'answers': [
                f"Yes, {product_name} is meant for regular use when handled as per the product type and care guidance on the page.",
                f"Eligible returns for {product_name} can be requested within {return_days} days, provided the product is unused and returned in original condition.",
            ],
        },
    ]
    return generic_sets[variant % len(generic_sets)]


def build_user(index):
    first_name, last_name = NAME_PAIRS[index % len(NAME_PAIRS)]
    serial = index + 1
    username = f"{first_name.lower()}.{last_name.lower()}{serial}"
    email = f"{first_name.lower()}.{last_name.lower()}{serial}@gmail.com"

    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'is_active': True,
        },
    )

    updated = False
    if user.email != email:
        user.email = email
        updated = True
    if user.first_name != first_name:
        user.first_name = first_name
        updated = True
    if user.last_name != last_name:
        user.last_name = last_name
        updated = True
    if created:
        user.set_unusable_password()
        updated = True
    if updated:
        user.save()

    return user


def main():
    products = Product.objects.filter(is_active=True).order_by('id')
    admin_user = User.objects.filter(is_superuser=True).order_by('id').first()

    if not products.exists():
        print('No active products found.')
        return

    created_questions = 0
    skipped_products = 0
    user_index = 0

    for product_position, product in enumerate(products):
        if ProductQuestion.objects.filter(product=product).exists():
            skipped_products += 1
            print(f"Skipped {product.name} (questions already exist)")
            continue

        qa_pack = product_context(product, product_position)
        for qa_index, question_text in enumerate(qa_pack['questions']):
            customer = build_user(user_index)
            user_index += 1

            created_at = timezone.now() - timedelta(days=(product_position * 2) + qa_index + 1)
            answered_at = created_at + timedelta(hours=8 + qa_index)

            question = ProductQuestion.objects.create(
                product=product,
                user=customer,
                question=question_text,
                answer=qa_pack['answers'][qa_index],
                answered_by=admin_user,
                is_answered=True,
                is_approved=True,
                answered_at=answered_at,
            )

            ProductQuestion.objects.filter(pk=question.pk).update(created_at=created_at)
            created_questions += 1

        print(f"Added {len(qa_pack['questions'])} Q&A entries for {product.name}")

    print('-' * 60)
    print(f"Products processed: {products.count()}")
    print(f"Questions created: {created_questions}")
    print(f"Products skipped: {skipped_products}")
    print(f"Total product questions: {ProductQuestion.objects.count()}")


if __name__ == '__main__':
    main()