# Generated manually to create missing Result table

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0014_alter_result_line_alter_result_machine_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE TABLE IF NOT EXISTS production_result (
                id BIGSERIAL PRIMARY KEY,
                quantity INTEGER NOT NULL CHECK (quantity >= 1),
                line VARCHAR(100) NOT NULL DEFAULT '',
                machine VARCHAR(100) NOT NULL DEFAULT '',
                part VARCHAR(100) NOT NULL DEFAULT '',
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                serial_number VARCHAR(100) NOT NULL,
                judgment VARCHAR(2) NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS production_result;"
        ),
    ]