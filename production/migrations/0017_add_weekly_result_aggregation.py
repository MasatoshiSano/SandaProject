# Generated manually for weekly analysis performance improvement

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0016_alter_result_line_alter_result_machine_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='WeeklyResultAggregation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True, verbose_name='日付')),
                ('line', models.CharField(db_index=True, max_length=100, verbose_name='ライン')),
                ('machine', models.CharField(blank=True, max_length=100, null=True, verbose_name='設備')),
                ('part', models.CharField(db_index=True, max_length=100, verbose_name='機種')),
                ('judgment', models.CharField(choices=[('OK', 'OK'), ('NG', 'NG')], max_length=2, verbose_name='判定')),
                ('total_quantity', models.PositiveIntegerField(default=0, verbose_name='合計数量')),
                ('result_count', models.PositiveIntegerField(default=0, verbose_name='実績件数')),
                ('last_updated', models.DateTimeField(auto_now=True, verbose_name='最終更新')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='作成日時')),
            ],
            options={
                'verbose_name': '週別実績集計',
                'verbose_name_plural': '週別実績集計',
                'ordering': ['-date', 'line', 'part'],
            },
        ),
        migrations.AddIndex(
            model_name='weeklyresultaggregation',
            index=models.Index(fields=['date', 'line'], name='production_w_date_li_b8e8a5_idx'),
        ),
        migrations.AddIndex(
            model_name='weeklyresultaggregation',
            index=models.Index(fields=['date', 'line', 'part'], name='production_w_date_li_8c4b2a_idx'),
        ),
        migrations.AddIndex(
            model_name='weeklyresultaggregation',
            index=models.Index(fields=['date', 'line', 'judgment'], name='production_w_date_li_f9c3d1_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='weeklyresultaggregation',
            unique_together={('date', 'line', 'machine', 'part', 'judgment')},
        ),
    ]