# Generated by Django 4.2 on 2023-05-10 04:15

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("gifs", "0005_gif_aspect_ratio_gif_file_size_gif_frames_gif_height_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Reaction",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=100)),
            ],
        ),
        migrations.RemoveField(
            model_name="gif",
            name="reactions",
        ),
        migrations.AlterField(
            model_name="gif",
            name="uploader",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="gifs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="gif",
            name="reactions",
            field=models.ManyToManyField(
                blank=True, null=True, related_name="gifs", to="gifs.reaction"
            ),
        ),
    ]
