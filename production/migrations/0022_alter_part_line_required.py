# Generated manually for Part.line required field

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0021_alter_part_options_alter_result_options_part_line_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='part',
            name='line',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='production.line', verbose_name='ライン'),
        ),
    ]