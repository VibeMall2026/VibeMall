from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Hub", "0050_orderitem_margin_amount_product_margin"),
    ]

    operations = [
        migrations.AddField(
            model_name="categoryicon",
            name="icon_size",
            field=models.PositiveIntegerField(
                default=48,
                help_text="Icon size in pixels (used for image width/height or FontAwesome size)",
            ),
        ),
    ]
