from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Hub', '0064_alter_coupon_code_alter_coupon_coupon_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='categoryicon',
            name='card_image',
            field=models.ImageField(blank=True, help_text='Homepage All Categories card image (recommended: 800x1000 or 4:5 ratio)', null=True, upload_to='category_cards/'),
        ),
    ]
