# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-03-24 13:49
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0077_application_days_available'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='dev_rate',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=19),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='task',
            name='pm_rate',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=19),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='task',
            name='tunga_percentage_dev',
            field=models.DecimalField(decimal_places=4, default=13, max_digits=19),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='task',
            name='tunga_percentage_pm',
            field=models.DecimalField(decimal_places=4, default=48.71, max_digits=19),
            preserve_default=False,
        ),
    ]