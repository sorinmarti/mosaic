# Generated migration for enhanced task tracking

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('twf', '0079_delete_prompt'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='task_type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('instant', 'Instant'),
                    ('celery', 'Celery Background Task'),
                    ('workflow', 'Workflow'),
                ],
                default='celery'
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='category',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('create', 'Create'),
                    ('update', 'Update'),
                    ('delete', 'Delete'),
                    ('bulk_delete', 'Bulk Delete'),
                    ('import', 'Import/Extract'),
                    ('export', 'Export'),
                    ('ai_processing', 'AI Processing'),
                    ('enrichment', 'Enrichment'),
                    ('workflow', 'Workflow'),
                    ('system', 'System'),
                ],
                null=True,
                blank=True
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='total_items',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='task',
            name='processed_items',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='task',
            name='successful_items',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='task',
            name='failed_items',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='task',
            name='workflow_steps',
            field=models.JSONField(default=dict, blank=True),
        ),
    ]