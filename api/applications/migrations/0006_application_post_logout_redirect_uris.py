# Generated by Django 4.2.1 on 2023-06-05 03:16

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0005_alter_application_icon"),
    ]

    operations = [
        migrations.AddField(
            model_name="application",
            name="post_logout_redirect_uris",
            field=models.TextField(
                blank=True, help_text="Allowed Post Logout URIs list, space separated"
            ),
        ),
    ]
