from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('onlinecourse', '0002_question_course'),
    ]

    operations = [
        migrations.RenameField(
            model_name='question',
            old_name='content',
            new_name='question_text',
        ),
        migrations.RenameField(
            model_name='choice',
            old_name='content',
            new_name='choice_text',
        ),
    ]
