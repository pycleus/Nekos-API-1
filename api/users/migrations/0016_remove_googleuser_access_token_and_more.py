# Generated by Django 4.1.5 on 2023-02-11 06:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_alter_googleuser_id"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="googleuser",
            name="access_token",
        ),
        migrations.RemoveField(
            model_name="googleuser",
            name="refresh_token",
        ),
    ]