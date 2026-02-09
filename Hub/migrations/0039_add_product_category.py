from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Hub', '0038_add_product_timestamps'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='category',
            field=models.CharField(
                blank=True,
                choices=[
                    ('TOP_DEALS', 'Top Deals Of The Day'),
                    ('TOP_SELLING', 'Top Selling Products'),
                    ('TOP_FEATURED', 'Top Featured Products'),
                    ('RECOMMENDED', 'Recommended For You'),
                    ('MOBILES', 'Mobiles'),
                    ('FOOD_HEALTH', 'Food & Health'),
                    ('HOME_KITCHEN', 'Home & Kitchen'),
                    ('AUTO_ACC', 'Auto Acc'),
                    ('FURNITURE', 'Furniture'),
                    ('SPORTS', 'Sports'),
                    ('GENZ_TRENDS', 'GenZ Trends'),
                    ('NEXT_GEN', 'Next Gen'),
                ],
                max_length=50,
                null=True,
            ),
        ),
    ]
