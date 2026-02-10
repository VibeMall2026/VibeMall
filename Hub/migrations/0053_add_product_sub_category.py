from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Hub', '0052_merge_20260209_1533'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='sub_category',
            field=models.CharField(blank=True, help_text='Optional sub-category label', max_length=100),
        ),
    ]
