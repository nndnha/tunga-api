# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-07-04 18:41
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_profiles', '0007_auto_20160703_2237'),
    ]

    operations = [
        migrations.AddField(
            model_name='developerapplication',
            name='used',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='developerapplication',
            name='used_at',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name='developerapplication',
            name='confirmation_sent_at',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
