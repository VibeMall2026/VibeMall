# This migration is empty - timestamp fields were added to model but not applied
# Using -id ordering instead for getting latest products

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Hub', '0037_remove_product_category_field'),
    ]

    operations = [
        # Empty migration - no database changes needed
    ]
