# encoding=utf8
from __future__ import unicode_literals

import re
import uuid
from decimal import Decimal

import tagulous.models
from actstream.models import Action
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.query_utils import Q
from django.template.defaultfilters import floatformat, truncatewords
from django.utils.crypto import get_random_string
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings
from tunga.settings import BITONIC_PAYMENT_COST_PERCENTAGE, \
    BANK_TRANSFER_PAYMENT_COST_PERCENTAGE
from tunga_activity.models import ActivityReadLog
from tunga_comments.models import Comment
from tunga_messages.models import Channel
from tunga_profiles.models import Skill, Connection
from tunga_settings.models import VISIBILITY_CHOICES
from tunga_utils.constants import CURRENCY_EUR, CURRENCY_USD, USER_TYPE_DEVELOPER, VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM, VISIBILITY_CUSTOM, UPDATE_SCHEDULE_HOURLY, UPDATE_SCHEDULE_DAILY, \
    UPDATE_SCHEDULE_WEEKLY, UPDATE_SCHEDULE_MONTHLY, UPDATE_SCHEDULE_QUATERLY, UPDATE_SCHEDULE_ANNUALLY, \
    TASK_PAYMENT_METHOD_BITONIC, TASK_PAYMENT_METHOD_BITCOIN, TASK_PAYMENT_METHOD_BANK, \
    PROGRESS_EVENT_TYPE_DEFAULT, PROGRESS_EVENT_TYPE_PERIODIC, PROGRESS_EVENT_TYPE_MILESTONE, \
    PROGRESS_EVENT_TYPE_SUBMIT, PROGRESS_REPORT_STATUS_ON_SCHEDULE, PROGRESS_REPORT_STATUS_BEHIND, \
    PROGRESS_REPORT_STATUS_STUCK, INTEGRATION_TYPE_REPO, INTEGRATION_TYPE_ISSUE, STATUS_PENDING, \
    STATUS_PROCESSING, STATUS_COMPLETED, STATUS_FAILED, STATUS_INITIATED, \
    APP_INTEGRATION_PROVIDER_SLACK, APP_INTEGRATION_PROVIDER_HARVEST, APP_INTEGRATION_PROVIDER_GITHUB, TASK_TYPE_WEB, \
    TASK_TYPE_MOBILE, TASK_TYPE_OTHER, TASK_CODERS_NEEDED_ONE, TASK_CODERS_NEEDED_MULTIPLE, TASK_SCOPE_TASK, \
    TASK_SCOPE_ONGOING, TASK_BILLING_METHOD_FIXED, TASK_BILLING_METHOD_HOURLY, TASK_SCOPE_PROJECT, TASK_SOURCE_DEFAULT, \
    TASK_SOURCE_NEW_USER, PROGRESS_EVENT_TYPE_COMPLETE, STATUS_INITIAL, STATUS_APPROVED, STATUS_DECLINED, \
    STATUS_ACCEPTED, STATUS_REJECTED, STATUS_SUBMITTED
from tunga_utils.helpers import round_decimal, get_serialized_id, get_tunga_model
from tunga_utils.models import Upload, Rating
from tunga_utils.validators import validate_btc_address

CURRENCY_CHOICES = (
    (CURRENCY_EUR, 'EUR'),
    (CURRENCY_USD, 'USD')
)

CURRENCY_SYMBOLS = {
    'EUR': '€',
    'USD': '$'
}

UPDATE_SCHEDULE_CHOICES = (
    (UPDATE_SCHEDULE_HOURLY, 'Hour'),
    (UPDATE_SCHEDULE_DAILY, 'Day'),
    (UPDATE_SCHEDULE_WEEKLY, 'Week'),
    (UPDATE_SCHEDULE_MONTHLY, 'Month'),
    (UPDATE_SCHEDULE_QUATERLY, 'Quarter'),
    (UPDATE_SCHEDULE_ANNUALLY, 'Annual')
)


class Project(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='projects_created', on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    deadline = models.DateTimeField(blank=True, null=True)
    closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(blank=True, null=True)

    def __unicode__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'title')

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return request.user.is_project_owner or request.user.is_project_manager

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return request.user == self.user

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_project_owner or request.user.is_project_manager

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user

    @property
    def excerpt(self):
        try:
            return strip_tags(self.description).strip()
        except:
            return None


TASK_TYPE_CHOICES = (
    (TASK_TYPE_WEB, 'Web'),
    (TASK_TYPE_MOBILE, 'Mobile'),
    (TASK_TYPE_OTHER, 'Other')
)

TASK_SCOPE_CHOICES = (
    (TASK_SCOPE_TASK, 'Task'),
    (TASK_SCOPE_PROJECT, 'Project'),
    (TASK_SCOPE_ONGOING, 'Ongoing')
)

TASK_BILLING_CHOICES = (
    (TASK_BILLING_METHOD_FIXED, 'Fixed'),
    (TASK_BILLING_METHOD_HOURLY, 'Hourly')
)

TASK_CODERS_NEEDED_CHOICES = (
    (TASK_CODERS_NEEDED_ONE, 'One coder'),
    (TASK_CODERS_NEEDED_MULTIPLE, 'Multiple coders')
)

TASK_PAYMENT_METHOD_CHOICES = (
    (TASK_PAYMENT_METHOD_BITONIC, 'Pay with ideal / mister cash'),
    (TASK_PAYMENT_METHOD_BITCOIN, 'Pay with bitcoin'),
    (TASK_PAYMENT_METHOD_BANK, 'Pay by bank transfer')
)

TASK_SOURCE_CHOICES = (
    (TASK_SOURCE_DEFAULT, 'Default'),
    (TASK_SOURCE_NEW_USER, 'New Wizard User')
)


class Task(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='tasks_created', on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=200, blank=True, null=True, default='')
    description = models.TextField(blank=True, null=True)

    # Task structure
    # TODO: Replace parent to become project
    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.SET_NULL, blank=True, null=True)
    parent = models.ForeignKey('self', related_name='sub_tasks', on_delete=models.DO_NOTHING, blank=True, null=True)
    source = models.IntegerField(choices=TASK_SOURCE_CHOICES, default=TASK_SOURCE_DEFAULT)

    # Payment
    billing_method = models.IntegerField(
        choices=TASK_BILLING_CHOICES, default=TASK_BILLING_METHOD_FIXED, blank=True, null=True
    )
    currency = models.CharField(max_length=5, choices=CURRENCY_CHOICES, default=CURRENCY_CHOICES[0][0])
    fee = models.DecimalField(
        max_digits=19, decimal_places=4, blank=True, null=True, default=None
    )
    bid = models.DecimalField(
        max_digits=19, decimal_places=4, blank=True, null=True, default=None
    )
    dev_rate = models.DecimalField(
        max_digits=19, decimal_places=4, default=19
    )
    pm_rate = models.DecimalField(
        max_digits=19, decimal_places=4, default=39
    )
    pm_time_percentage = models.DecimalField(
        max_digits=7, decimal_places=4, default=15
    )
    tunga_percentage_dev = models.DecimalField(
        max_digits=7, decimal_places=4, default=34.21
    )
    tunga_percentage_pm = models.DecimalField(
        max_digits=7, decimal_places=4, default=48.71
    )

    # Contact info
    skype_id = models.CharField(max_length=100, blank=True, null=True)

    # Payment related info
    payment_method = models.CharField(
        max_length=30, choices=TASK_PAYMENT_METHOD_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in TASK_PAYMENT_METHOD_CHOICES]),
        blank=True, null=True
    )
    btc_address = models.CharField(max_length=40, blank=True, null=True, validators=[validate_btc_address])
    btc_price = models.DecimalField(max_digits=18, decimal_places=8, blank=True, null=True)

    # Classification details
    type = models.IntegerField(choices=TASK_TYPE_CHOICES, default=TASK_TYPE_OTHER)  # Web, Mobile ...
    scope = models.IntegerField(choices=TASK_SCOPE_CHOICES, default=TASK_SCOPE_TASK)  # task, project or ongoing project
    has_requirements = models.BooleanField(default=False)
    pm_required = models.BooleanField(default=False)
    contact_required = models.BooleanField(default=False)
    skills = tagulous.models.TagField(Skill, blank=True)
    coders_needed = models.IntegerField(choices=TASK_CODERS_NEEDED_CHOICES, blank=True, null=True)

    # Update settings
    update_interval = models.PositiveIntegerField(blank=True, null=True)
    update_interval_units = models.PositiveSmallIntegerField(choices=UPDATE_SCHEDULE_CHOICES, blank=True, null=True)

    # Audience for the task
    visibility = models.PositiveSmallIntegerField(choices=VISIBILITY_CHOICES, default=VISIBILITY_CHOICES[0][0])

    # Additional task info
    stack_description = models.TextField(blank=True, null=True)
    deliverables = models.TextField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    satisfaction = models.SmallIntegerField(blank=True, null=True, help_text="Client's rating of task developers")

    # Task state modifiers
    approved = models.BooleanField(default=False)
    apply = models.BooleanField(
        default=True, help_text='True if developers can apply for this task (visibility can override this)'
    )
    closed = models.BooleanField(default=False, help_text='True if the task is closed')
    paid = models.BooleanField(default=False, help_text='True if the task is paid')
    pay_distributed = models.BooleanField(
        default=False,
        help_text='True if task has been paid and entire payment has been distributed tp participating developers'
    )
    archived = models.BooleanField(default=False)
    reminded_complete_task = models.BooleanField(default=False)

    # Significant event dates
    deadline = models.DateTimeField(blank=True, null=True)
    apply_closed_at = models.DateTimeField(blank=True, null=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    invoice_date = models.DateTimeField(blank=True, null=True)
    complete_task_email_at = models.DateTimeField(blank=True, null=True)
    check_task_email_at = models.DateTimeField(blank=True, null=True)

    # Applications and participation info
    pm = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='tasks_managed', on_delete=models.DO_NOTHING, blank=True, null=True
    )
    applicants = models.ManyToManyField(
            settings.AUTH_USER_MODEL, through='Application', through_fields=('task', 'user'),
            related_name='task_applications', blank=True
    )
    participants = models.ManyToManyField(
            settings.AUTH_USER_MODEL, through='Participation', through_fields=('task', 'user'),
            related_name='task_participants', blank=True)

    # Relationships
    comments = GenericRelation(Comment, related_query_name='tasks')
    uploads = GenericRelation(Upload, related_query_name='tasks')
    ratings = GenericRelation(Rating, related_query_name='tasks')
    activity_objects = GenericRelation(
        Action,
        object_id_field='target_object_id',
        content_type_field='target_content_type',
        related_query_name='tasks'
    )
    read_logs = GenericRelation(ActivityReadLog, related_query_name='tasks')

    def __unicode__(self):
        return self.summary

    class Meta:
        ordering = ['-created_at']

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if self.id:
            if not self.approved:
                if self.source == TASK_SOURCE_NEW_USER and self.scope == TASK_SCOPE_TASK and self.description and len(
                        self.description.split(' ')) >= 15:
                    self.approved = True
        else:
            # Analyze new tasks to decide on approval status
            if self.source == TASK_SOURCE_NEW_USER:
                # For tasks from new users, only approve if sufficient info is provided
                if self.scope == TASK_SCOPE_TASK and self.description and len(self.description.split(' ')) >= 15:
                    self.approved = True
                else:
                    self.approved = False
            else:
                # For authenticated users, approve tasks and projects that don't need a PM on creation
                self.approved = bool(
                    self.scope == TASK_SCOPE_TASK or (self.scope == TASK_SCOPE_PROJECT and not self.pm_required)
                )

        super(Task, self).save(
            force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields
        )

    def has_admin_access(self, user):
        if user and user.is_authenticated():
            if user == self.user:
                return True
            return self.taskaccess_set.filter(user=user).count() == 1
        return False

    @property
    def subtask_participants_inclusive_filter(self):
        return get_tunga_model('tunga_tasks.Participation').objects.filter(
            (Q(task=self) | Q(task__parent=self))
        )

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        if request.user == self.user or \
                (self.parent and request.user == self.parent.user) or \
                self.has_admin_access(request.user) or \
                (request.user.is_project_manager): #and (self.pm == request.user or not self.pm)):
            return True
        elif self.visibility == VISIBILITY_DEVELOPER:
            return request.user.type == USER_TYPE_DEVELOPER
        elif self.visibility == VISIBILITY_MY_TEAM:
            return bool(
                Connection.objects.exclude(accepted=False).filter(
                    Q(from_user=self.user, to_user=request.user) | Q(from_user=request.user, to_user=self.user)
                ).count()
            )
        elif self.visibility == VISIBILITY_CUSTOM:
            return self.subtask_participants_inclusive_filter.filter(
                (Q(accepted=True) | Q(responded=False)),
                user=request.user
            ).count()
        return False

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_project_owner or request.user.is_project_manager

    @staticmethod
    @allow_staff_or_superuser
    def has_create_permission(request):
        return not request.user.is_authenticated() or request.user.is_project_owner or request.user.is_project_manager

    @staticmethod
    @allow_staff_or_superuser
    def has_update_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user or \
               (self.parent and request.user == self.parent.user) or \
               self.has_admin_access(request.user)

    @allow_staff_or_superuser
    def has_object_update_permission(self, request):
        if self.has_object_write_permission(request):
            return True
        # Participants can edit participation info directly on task object
        if request.method in ['PUT', 'PATCH']:
            allowed_keys = [
                'assignee', 'participation', 'participants',
                'confirmed_participants', 'rejected_participants'
            ]
            if not [x for x in request.data.keys() if not (x in allowed_keys or re.match(r'^file\d*$', x))]:
                return (self.pm and self.pm.id == request.user.id) or self.participation_set.filter((Q(accepted=True) | Q(responded=False)), user=request.user).count()
        return False

    @property
    def task_number(self):
        return get_serialized_id(self.id, max_digits=3)

    @property
    def tunga_ratio_dev(self):
        return self.tunga_percentage_dev * Decimal(0.01)

    @property
    def tunga_ratio_pm(self):
        return self.tunga_percentage_pm * Decimal(0.01)

    @property
    def pm_time_ratio(self):
        return self.pm_time_percentage * Decimal(0.01)

    @property
    def pay(self):
        return self.bid or self.fee

    @property
    def pay_dev(self):
        return self.pay - self.pay_pm

    @property
    def pay_pm(self):
        if self.is_project and self.pm:
            return self.pm_time_ratio*self.pay
        return 0

    def display_fee(self, amount=None):
        if amount is None:
            amount = self.pay
        if not amount:
            return ''
        if self.currency in CURRENCY_SYMBOLS:
            return '{}{}'.format(CURRENCY_SYMBOLS[self.currency], floatformat(amount, arg=-2))
        return amount
    display_fee.short_description = 'Fee'

    @property
    def is_payable(self):
        return bool(self.pay)

    @property
    def is_task(self):
        return self.scope == TASK_SCOPE_TASK

    @property
    def is_project(self):
        return not self.is_task

    @property
    def is_developer_ready(self):
        if self.scope == TASK_SCOPE_TASK:
            return True
        if self.scope == TASK_SCOPE_PROJECT and not self.pm_required and self.source != TASK_SOURCE_NEW_USER:
            return True
        if self.quote and self.quote.status == STATUS_ACCEPTED:
            return True
        return False

    @property
    def requires_estimate(self):
        return not self.is_developer_ready

    @property
    def amount(self):
        processing_share = 0
        if self.payment_method == TASK_PAYMENT_METHOD_BITONIC:
            processing_share = Decimal(BITONIC_PAYMENT_COST_PERCENTAGE) * Decimal(0.01)
        elif self.payment_method == TASK_PAYMENT_METHOD_BANK:
            processing_share = Decimal(BANK_TRANSFER_PAYMENT_COST_PERCENTAGE) * Decimal(0.01)

        amount_details = None
        if self.pay:
            amount_details = dict(
                dict(
                    currency=CURRENCY_SYMBOLS.get(self.currency, ''),
                    pledge=self.pay,
                    developer=(1 - self.tunga_ratio_dev) * self.pay_dev,
                    pm=(1 - self.tunga_ratio_pm) * self.pay_pm,
                    processing=processing_share * self.pay
                )
            )
            amount_details['tunga'] = self.pay - (amount_details['developer'] + amount_details['pm'])
            amount_details['total'] = self.pay + amount_details['processing']
        return amount_details

    @property
    def summary(self):
        try:
            return self.title or truncatewords(strip_tags(self.description).strip(), 10)
        except:
            return '{} #{}'.format(self.is_task and 'Task' or 'Project', self.id)

    @property
    def excerpt(self):
        try:
            return truncatewords(strip_tags(self.description).strip(), 20)
        except:
            return None

    @property
    def skills_list(self):
        return str(self.skills)

    def payment_status(self):
        return self.paid and self.pay_distributed and 'Paid' or self.paid and 'Processing' or 'Pending'

    @property
    def milestones(self):
        return self.progressevent_set.filter(type__in=[PROGRESS_EVENT_TYPE_MILESTONE, PROGRESS_EVENT_TYPE_SUBMIT])

    @property
    def progress_events(self):
        return self.progressevent_set.all()

    @property
    def participation(self):
        return self.participation_set.filter(Q(accepted=True) | Q(responded=False))

    @property
    def active_participants(self):
        return self.participation_set.filter(accepted=True)

    @property
    def assignee(self):
        try:
            return self.participation_set.get((Q(accepted=True) | Q(responded=False)), assignee=True)
        except:
            return None

    @property
    def invoice(self):
        try:
            return self.taskinvoice_set.all().order_by('-id', '-created_at').first()
        except:
            return None

    @property
    def estimate(self):
        try:
            return self.estimate_set.all().order_by('-id', '-created_at').first()
        except:
            return None

    @property
    def quote(self):
        try:
            return self.quote_set.all().order_by('-id', '-created_at').first()
        except:
            return None

    @property
    def update_schedule_display(self):
        if self.update_interval and self.update_interval_units:
            if self.update_interval == 1 and self.update_interval_units == UPDATE_SCHEDULE_DAILY:
                return 'Daily'
            interval_units = str(self.get_update_interval_units_display()).lower()
            if self.update_interval == 1:
                return 'Every %s' % interval_units
            return 'Every %s %ss' % (self.update_interval, interval_units)
        return None

    @property
    def applications(self):
        return self.application_set.filter(responded=False)

    @property
    def all_uploads(self):
        return Upload.objects.filter(
            Q(tasks=self) | Q(comments__tasks=self) | Q(progress_reports__event__task=self) |
            Q(tasks__parent=self) | Q(comments__tasks__parent=self) | Q(progress_reports__event__task__parent=self)
        )

    @property
    def activity_stream(self):
        return Action.objects.filter(
            Q(tasks=self) | Q(tasks__parent=self) |
            Q(progress_events__task=self) | Q(progress_events__task__parent=self)
        )

    def get_participation_shares(self, return_hash=False):
        participants = self.participation_set.filter(accepted=True).order_by('-share')
        num_participants = participants.count()

        participation_shares = []
        participation_shares_hash = {}

        if participants:
            all_shares = [participant.share or 0 for participant in participants]
            total_shares = all_shares and sum(all_shares) or 0

            for participant in participants:
                if not total_shares:
                    share = 1/Decimal(num_participants)
                else:
                    share = Decimal(participant.share or 0)/Decimal(total_shares)
                share_info = {
                    'participant': participant,
                    'share': share
                }
                participation_shares.append(share_info)
                participation_shares_hash[participant.id] = share_info
        return return_hash and participation_shares_hash or participation_shares

    def get_payment_shares(self):
        participation_shares = self.get_participation_shares()
        payment_shares = []

        if participation_shares:
            for data in participation_shares:
                payment_shares.append({
                    'participant': data['participant'],
                    'share': Decimal(data['share'])*Decimal(1 - self.tunga_ratio_dev)
                })
        return payment_shares

    def get_user_participation_share(self, participation_id):
        participation_shares = self.get_participation_shares(return_hash=True)
        if participation_id and isinstance(participation_shares, dict):
            share_info = participation_shares.get(participation_id, None)
            if share_info:
                return share_info.get('share', 0)
        return 0

    def get_user_payment_share(self, participation_id):
        share = self.get_user_participation_share(participation_id=participation_id)
        if share:
            return share*(Decimal(100 - self.tunga_percentage_dev) / Decimal(100))
        return 0


class TaskAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admins_added')
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.task.summary)

    class Meta:
        unique_together = ('user', 'task')


class Application(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    pitch = models.CharField(max_length=1000, blank=True, null=True)
    hours_needed = models.PositiveIntegerField(blank=True, null=True)
    hours_available = models.PositiveIntegerField(blank=True, null=True)
    days_available = models.PositiveIntegerField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)  # These will also be delivered as messages to the client
    deliver_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    channels = GenericRelation(Channel, related_query_name='task_applications')

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.task.summary)

    class Meta:
        unique_together = ('user', 'task')

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.has_object_update_permission(request)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_DEVELOPER

    @staticmethod
    @allow_staff_or_superuser
    def has_update_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user

    @allow_staff_or_superuser
    def has_object_update_permission(self, request):
        # Task owner can update applications
        return request.user == self.user or request.user == self.task.user


class Participation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    assignee = models.BooleanField(default=False)
    role = models.CharField(max_length=100, default='Developer')
    share = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    satisfaction = models.SmallIntegerField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='participants_added')
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(blank=True, null=True)
    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(blank=True, null=True)

    ratings = GenericRelation(Rating, related_query_name='participants')

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.task.title)

    class Meta:
        unique_together = ('user', 'task')
        verbose_name_plural = 'participation'

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.task.has_object_read_permission(request)

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user or request.user == self.task.user

    @property
    def payment_share(self):
        return self.task.get_user_payment_share(participation_id=self.id) or 0


class WorkActivity(models.Model):
    # The target of the activity (estimate or quote)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name=_('content type'))
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    hours = models.FloatField()
    due_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return 'Activity | {}'.format(self.content_object)


class WorkPlan(models.Model):
    # The target of the activity (estimate or quote)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name=_('content type'))
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return 'WorkPlan | {}'.format(self.content_object)


ESTIMATE_STATUS_CHOICES = (
    (STATUS_INITIAL, 'Initial'),
    (STATUS_SUBMITTED, 'Submitted'),
    # Admins
    (STATUS_APPROVED, 'Approved'),
    (STATUS_DECLINED, 'Declined'),
    # Clients
    (STATUS_ACCEPTED, 'Accepted'),
    (STATUS_REJECTED, 'Rejected'),
)


class AbstractEstimate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    introduction = models.TextField()
    # Status
    status = models.CharField(
        max_length=30, choices=ESTIMATE_STATUS_CHOICES, default=STATUS_INITIAL,
        help_text=', '.join(['%s - %s' % (item[0], item[1]) for item in ESTIMATE_STATUS_CHOICES])
    )
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    submitted_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_email_at = models.DateTimeField(blank=True, null=True)

    # Moderation
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='%(class)s_moderated', on_delete=models.DO_NOTHING, blank=True, null=True
    )
    moderator_comment = models.TextField(blank=True, null=True)
    moderated_at = models.DateTimeField(blank=True, null=True)
    moderator_email_at = models.DateTimeField(blank=True, null=True)

    # Review
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='%(class)s_reviewed', on_delete=models.DO_NOTHING, blank=True, null=True
    )
    reviewer_comment = models.TextField(blank=True, null=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewer_email_at = models.DateTimeField(blank=True, null=True)

    # Relationships
    activity_objects = GenericRelation(
        Action,
        object_id_field='action_object_object_id',
        content_type_field='action_object_content_type',
        related_query_name='%(class)s'
    )
    activities = GenericRelation(WorkActivity, related_query_name='%(class)s')

    def __unicode__(self):
        return '{} | {}'.format('%(class)'.title(), self.task.summary)

    class Meta:
        abstract = True

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return request.user.is_project_manager or request.user.is_project_owner

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.task.has_object_read_permission(request)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_project_manager or request.user.is_project_owner

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user or request.user == self.task.user

    @property
    def dev_hours(self):
        return sum([x.hours for x in self.activities.all()])

    @property
    def pm_hours(self):
        return self.dev_hours*self.task.pm_time_ratio

    @property
    def hours(self):
        return self.dev_hours + self.pm_hours

    @property
    def dev_fee(self):
        return Decimal(self.dev_hours) * self.task.dev_rate

    @property
    def pm_fee(self):
        return Decimal(self.pm_hours)*self.task.pm_rate

    @property
    def fee(self):
        return self.dev_fee + self.pm_fee

    @property
    def fee_details(self):
        return dict(
            dev=dict(
                hours=self.dev_hours,
                fee=self.dev_fee
            ),
            pm=dict(
                hours=self.pm_hours,
                fee=self.pm_fee
            ),
            total=dict(
                hours=self.dev_hours+self.pm_hours,
                fee=self.dev_fee+self.pm_fee
            )
        )


class Estimate(AbstractEstimate):
    pass

QUOTE_STATUS_CHOICES = ESTIMATE_STATUS_CHOICES


class Quote(AbstractEstimate):
    # Scope
    in_scope = models.TextField()
    out_scope = models.TextField()
    assumptions = models.TextField()
    deliverables = models.TextField()
    # Solution
    architecture = models.TextField()
    technology = models.TextField()
    # Methodology
    process = models.TextField()
    reporting = models.TextField()

    # Relationships
    plan = GenericRelation(WorkPlan, related_query_name='quotes')


class TimeEntry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    spent_at = models.DateField()
    hours = models.FloatField()
    description = models.CharField(max_length=1000, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '{} hrs | {} - {}'.format(self.hours, self.task.summary, self.user.get_short_name() or self.user.username)

    class Meta:
        ordering = ['spent_at']

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return request.user == self.user

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_DEVELOPER

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user


PROGRESS_EVENT_TYPE_CHOICES = (
    (PROGRESS_EVENT_TYPE_DEFAULT, 'Update'),
    (PROGRESS_EVENT_TYPE_PERIODIC, 'Periodic Update'),
    (PROGRESS_EVENT_TYPE_MILESTONE, 'Milestone'),
    (PROGRESS_EVENT_TYPE_SUBMIT, 'Final Draft'),
    (PROGRESS_EVENT_TYPE_COMPLETE, 'Submission')
)


class ProgressEvent(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    type = models.PositiveSmallIntegerField(
        choices=PROGRESS_EVENT_TYPE_CHOICES, default=PROGRESS_EVENT_TYPE_DEFAULT,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in PROGRESS_EVENT_TYPE_CHOICES])
    )
    due_at = models.DateTimeField()
    title = models.CharField(max_length=200, blank=True, null=True)
    description = models.CharField(max_length=1000, blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='progress_events_created', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_reminder_at = models.DateTimeField(blank=True, null=True)

    activity_objects = GenericRelation(
        Action,
        object_id_field='target_object_id',
        content_type_field='target_content_type',
        related_query_name='progress_events'
    )

    def __unicode__(self):
        return '%s | %s - %s' % (self.get_type_display(), self.task.summary, self.due_at)

    class Meta:
        unique_together = ('task', 'due_at')
        ordering = ['-due_at']

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.task.has_object_read_permission(request)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_project_owner or request.user.is_project_manager

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.task.user


PROGRESS_REPORT_STATUS_CHOICES = (
    (PROGRESS_REPORT_STATUS_ON_SCHEDULE, 'On schedule'),
    (PROGRESS_REPORT_STATUS_BEHIND, 'Behind'),
    (PROGRESS_REPORT_STATUS_STUCK, 'Stuck')
)


class ProgressReport(models.Model):
    event = models.OneToOneField(ProgressEvent, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    status = models.PositiveSmallIntegerField(
        choices=PROGRESS_REPORT_STATUS_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in PROGRESS_REPORT_STATUS_CHOICES])
    )
    percentage = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    accomplished = models.TextField()
    next_steps = models.TextField(blank=True, null=True)
    obstacles = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    uploads = GenericRelation(Upload, related_query_name='progress_reports')

    def __unicode__(self):
        return '{0} - {1}%'.format(self.event, self.percentage)

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.event.task.has_object_read_permission(request)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_DEVELOPER

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user


class IntegrationEvent(models.Model):
    id = models.CharField(max_length=30, primary_key=True)
    name = models.CharField(max_length=30)
    description = models.CharField(max_length=200, blank=True, null=True)
    created_by = models.ForeignKey(
            settings.AUTH_USER_MODEL, blank=True, null=True, related_name='integration_events_created',
            on_delete=models.DO_NOTHING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s - %s' % (self.id, self.name)

    class Meta:
        ordering = ['id', 'name']


APP_INTEGRATION_PROVIDER_CHOICES = (
    (APP_INTEGRATION_PROVIDER_GITHUB, 'GitHub'),
    (APP_INTEGRATION_PROVIDER_SLACK, 'Slack'),
    (APP_INTEGRATION_PROVIDER_HARVEST, 'Harvest'),
)


INTEGRATION_TYPE_CHOICES = (
    (INTEGRATION_TYPE_REPO, 'Repo'),
    (INTEGRATION_TYPE_ISSUE, 'Issue')
)


class Integration(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    provider = models.CharField(
        max_length=30, choices=APP_INTEGRATION_PROVIDER_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in APP_INTEGRATION_PROVIDER_CHOICES])
    )
    type = models.PositiveSmallIntegerField(
        choices=INTEGRATION_TYPE_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in INTEGRATION_TYPE_CHOICES]),
        blank=True, null=True
    )
    events = models.ManyToManyField(IntegrationEvent, related_name='integrations')
    secret = models.CharField(max_length=30, default=get_random_string)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='integrations_created', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s - %s' % (self.get_provider_display(), self.task.summary)

    class Meta:
        unique_together = ('task', 'provider')
        ordering = ['created_at']

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return request.user == self.task.user

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_project_owner or request.user.is_project_manager

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.task.user

    @property
    def hook_id(self):
        return self.get_meta_value('hook_id')

    @property
    def repo_id(self):
        return self.get_meta_value('repo_id')

    @property
    def repo_full_name(self):
        return self.get_meta_value('repo_full_name')

    @property
    def issue_id(self):
        return self.get_meta_value('issue_id')

    @property
    def issue_number(self):
        return self.get_meta_value('issue_number')

    @property
    def project_id(self):
        return self.get_meta_value('project_id')

    @property
    def project_task_id(self):
        return self.get_meta_value('project_task_id')

    @property
    def team_id(self):
        return self.get_meta_value('team_id')

    @property
    def team_name(self):
        return self.get_meta_value('team_name')

    @property
    def channel_id(self):
        return self.get_meta_value('channel_id')

    @property
    def channel_name(self):
        return self.get_meta_value('channel_name')

    @property
    def token(self):
        return self.get_meta_value('token')

    @property
    def token_secret(self):
        return self.get_meta_value('token_secret')

    @property
    def refresh_token(self):
        return self.get_meta_value('refresh_token')

    @property
    def bot_access_token(self):
        if self.provider == APP_INTEGRATION_PROVIDER_GITHUB:
            return self.get_meta_value('bot_access_token')
        return

    @property
    def token_extra(self):
        return self.get_meta_value('token_extra')

    def get_meta_value(self, key):
        try:
            return self.integrationmeta_set.get(meta_key=key).meta_value
        except:
            return None


class IntegrationMeta(models.Model):
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE)
    meta_key = models.CharField(max_length=30)
    meta_value = models.CharField(max_length=500)
    created_by = models.ForeignKey(
            settings.AUTH_USER_MODEL, related_name='integration_meta_created', blank=True, null=True,
            on_delete=models.DO_NOTHING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s | %s - %s' % (self.integration, self.meta_key, self.meta_value)

    class Meta:
        ordering = ['created_at']


class IntegrationActivity(models.Model):
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='activities')
    event = models.ForeignKey(IntegrationEvent, related_name='integration_activities')
    action = models.CharField(max_length=30, blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    ref = models.CharField(max_length=30, blank=True, null=True)
    ref_name = models.CharField(max_length=50, blank=True, null=True)
    username = models.CharField(max_length=30, blank=True, null=True)
    fullname = models.CharField(max_length=50, blank=True, null=True)
    avatar_url = models.URLField(blank=True, null=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s | ' % (self.integration, )

    class Meta:
        ordering = ['created_at']


class TaskPayment(models.Model):
    task = models.ForeignKey(Task)
    btc_address = models.CharField(max_length=40, validators=[validate_btc_address])
    ref = models.CharField(max_length=255)
    btc_price = models.DecimalField(max_digits=18, decimal_places=8)
    btc_received = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    received_at = models.DateTimeField(blank=True, null=True)

    def __unicode__(self):
        return 'bitcoin:%s - %s' % (self.btc_address, self.task.summary)

    class Meta:
        unique_together = ('btc_address', 'ref')
        ordering = ['created_at']


PAYMENT_STATUS_CHOICES = (
    (STATUS_PENDING, 'Pending'),
    (STATUS_INITIATED, 'Initiated'),
    (STATUS_PROCESSING, 'Processing'),
    (STATUS_COMPLETED, 'Completed'),
    (STATUS_FAILED, 'Failed'),
)


class ParticipantPayment(models.Model):
    participant = models.ForeignKey(Participation)
    source = models.ForeignKey(TaskPayment)
    destination = models.CharField(max_length=40, validators=[validate_btc_address], blank=True, null=True)
    idem_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    ref = models.CharField(max_length=255, blank=True, null=True)
    btc_sent = models.DecimalField(max_digits=18, decimal_places=8, blank=True, null=True)
    btc_received = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    status = models.CharField(
        max_length=30, choices=PAYMENT_STATUS_CHOICES, default=STATUS_PENDING,
        help_text=', '.join(['%s - %s' % (item[0], item[1]) for item in PAYMENT_STATUS_CHOICES])
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    received_at = models.DateTimeField(blank=True, null=True)
    description = models.CharField(max_length=200, blank=True, null=True)
    extra = models.TextField(blank=True, null=True)  # JSON formatted extra details

    def __unicode__(self):
        return 'bitcoin:%s - %s | %s' % (self.destination, self.participant.user, self.description)

    class Meta:
        unique_together = ('participant', 'source')
        ordering = ['created_at']


class TaskInvoice(models.Model):
    task = models.ForeignKey(Task)
    title = models.CharField(max_length=200)
    fee = models.DecimalField(max_digits=19, decimal_places=4)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='client_invoices')
    developer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='developer_invoices')
    currency = models.CharField(max_length=5, choices=CURRENCY_CHOICES, default=CURRENCY_CHOICES[0][0])
    payment_method = models.CharField(
        max_length=30, choices=TASK_PAYMENT_METHOD_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in TASK_PAYMENT_METHOD_CHOICES])
    )
    btc_address = models.CharField(max_length=40, validators=[validate_btc_address])
    btc_price = models.DecimalField(max_digits=18, decimal_places=8, blank=True, null=True)
    number = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.summary

    class Meta:
        ordering = ['created_at']

    @property
    def pay_dev(self):
        return self.fee - self.pay_pm

    @property
    def pay_pm(self):
        if self.task.is_project and self.pm:
            return self.task.pm_time_ratio * self.fee
        return 0

    def display_fee(self, amount=None):
        if amount is None:
            amount = self.fee
        if self.currency in CURRENCY_SYMBOLS:
            return '%s%s' % (CURRENCY_SYMBOLS[self.currency], floatformat(amount, arg=-2))
        return amount
    display_fee.short_description = 'Fee'

    @property
    def amount(self):
        return self.get_amount_details(share=1)

    def get_amount_details(self, share=1):
        share = Decimal(share)
        fee_portion = self.fee * share
        fee_portion_dev = self.pay_dev * share
        fee_portion_pm = self.pay_pm * share

        processing_share = 0
        if self.payment_method == TASK_PAYMENT_METHOD_BITONIC:
            processing_share = Decimal(BITONIC_PAYMENT_COST_PERCENTAGE) * Decimal(0.01)
        elif self.payment_method == TASK_PAYMENT_METHOD_BANK:
            processing_share = Decimal(BANK_TRANSFER_PAYMENT_COST_PERCENTAGE) * Decimal(0.01)
        amount_details = dict(
            currency=CURRENCY_SYMBOLS.get(self.currency, ''),
            share=share,
            pledge=self.fee,
            portion=round_decimal(fee_portion, 2),
            developer=round_decimal((1 - self.task.tunga_ratio_dev) * fee_portion_dev, 2),
            pm=round_decimal((1 - self.task.tunga_ratio_pm) * fee_portion_pm, 2),
            processing=round_decimal(Decimal(processing_share) * fee_portion, 2)
        )

        amount_details['tunga'] = round_decimal(fee_portion - (amount_details['developer'] + amount_details['pm']), 2)
        amount_details['total'] = round_decimal(fee_portion + amount_details['processing'], 2)
        amount_details['total_dev'] = round_decimal(fee_portion_dev + (processing_share * fee_portion_dev), 2)
        amount_details['total_pm'] = round_decimal(fee_portion_pm + (processing_share * fee_portion_pm), 2)
        return amount_details

    @property
    def summary(self):
        return self.number or '%s - Fee: %s' % (self.title, self.display_fee())
