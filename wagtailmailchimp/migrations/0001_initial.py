# Generated by Django 4.2.1 on 2023-05-23 11:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('wagtailcore', '0088_userprofile_formsubmission'),
    ]

    operations = [
        migrations.CreateModel(
            name='MailchimpSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_key', models.CharField(blank=True, help_text='Mailchimp API Key ', max_length=50, null=True, verbose_name='Mailchimp API Key')),
                ('default_audience_id', models.CharField(blank=True, help_text='Default Mailchimp Audience Id', max_length=100, null=True, verbose_name='Default Mailchimp Audience Id')),
                ('site', models.OneToOneField(editable=False, on_delete=django.db.models.deletion.CASCADE, to='wagtailcore.site')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
