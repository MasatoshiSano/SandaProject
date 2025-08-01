# Generated by Django 4.2.7 on 2025-07-26 05:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0015_create_result_table'),
    ]

    operations = [
        migrations.AlterField(
            model_name='result',
            name='line',
            field=models.CharField(blank=True, default='', max_length=100, null=True, verbose_name='ライン'),
        ),
        migrations.AlterField(
            model_name='result',
            name='machine',
            field=models.CharField(blank=True, default='', max_length=100, null=True, verbose_name='設備'),
        ),
        migrations.AlterField(
            model_name='result',
            name='part',
            field=models.CharField(blank=True, default='', max_length=100, null=True, verbose_name='機種'),
        ),
    ]
