from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Hub', '0034_sitesettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='site_name_html',
            field=models.TextField(blank=True, help_text='Optional styled HTML for brand name (supports multiple colors/fonts)'),
        ),
    ]
