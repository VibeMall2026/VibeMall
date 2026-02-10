from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Hub', '0053_add_product_sub_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category_key', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['order', 'name'],
                'unique_together': {('category_key', 'name')},
            },
        ),
    ]
