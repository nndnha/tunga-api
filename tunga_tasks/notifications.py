import datetime

from django.contrib.auth import get_user_model
from django.db.models import When, Case, IntegerField
from django.db.models.aggregates import Sum
from django.db.models.expressions import F
from django.template.defaultfilters import truncatewords
from django_rq.decorators import job

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_URL, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS, SLACK_ATTACHMENT_COLOR_TUNGA, \
    SLACK_ATTACHMENT_COLOR_RED, SLACK_ATTACHMENT_COLOR_GREEN, SLACK_ATTACHMENT_COLOR_NEUTRAL, \
    SLACK_ATTACHMENT_COLOR_BLUE
from tunga_auth.filterbackends import my_connections_q_filter
from tunga_tasks import slugs
from tunga_tasks.models import Task, Participation, Application, ProgressEvent, ProgressReport, Quote, Estimate
from tunga_utils import slack_utils
from tunga_utils.constants import USER_TYPE_DEVELOPER, VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM, TASK_SCOPE_TASK, \
    USER_TYPE_PROJECT_MANAGER, TASK_SOURCE_NEW_USER, STATUS_INITIAL, STATUS_SUBMITTED, STATUS_APPROVED, STATUS_DECLINED, \
    STATUS_ACCEPTED, STATUS_REJECTED
from tunga_utils.emails import send_mail
from tunga_utils.helpers import clean_instance, convert_to_text


@job
def notify_new_task(instance, new_user=False):
    send_new_task_client_receipt_email(instance)
    send_new_task_email(instance, new_user=new_user)
    send_new_task_community_email(instance)


@job
def notify_task_approved(instance, new_user=False):
    send_new_task_client_receipt_email(instance)
    send_new_task_email(instance, new_user=new_user, completed=True)
    send_new_task_community_email(instance)

@job
def send_new_task_client_receipt_email(instance, reminder=False):
    instance = clean_instance(instance, Task)
    subject = "{} Your {} has been posted on Tunga".format(
        EMAIL_SUBJECT_PREFIX, instance.scope == TASK_SCOPE_TASK and 'task' or 'project'
    )
    if instance.is_task and not instance.approved:
        subject = "{} {}Finalize your {}".format(
            EMAIL_SUBJECT_PREFIX, reminder and 'Reminder: ' or '',
            instance.scope == TASK_SCOPE_TASK and 'task' or 'project'
        )
    to = [instance.user.email]

    ctx = {
        'owner': instance.user,
        'task': instance,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.id),
        'task_edit_url': '%s/task/%s/edit/complete-task/' % (TUNGA_URL, instance.id)
    }

    if instance.source == TASK_SOURCE_NEW_USER and not instance.user.is_confirmed:
        url_prefix = '{}/reset-password/confirm/{}/{}?new_user=true&next='.format(
            TUNGA_URL, instance.user.uid, instance.user.generate_reset_token()
        )
        ctx['task_url'] = '{}{}'.format(url_prefix, ctx['task_url'])
        ctx['task_edit_url'] = '{}{}'.format(url_prefix, ctx['task_edit_url'])

    if instance.is_task:
        if instance.approved:
            email_template = 'tunga/email/email_new_task_client_approved'
        else:
            if reminder:
                email_template = 'tunga/email/email_new_task_client_more_info_reminder'
            else:
                email_template = 'tunga/email/email_new_task_client_more_info'
    else:
        email_template = 'tunga/email/email_new_task_client_approved'
    if send_mail(subject, email_template, to, ctx):
        if not instance.approved:
            instance.complete_task_email_at = datetime.datetime.utcnow()
            if reminder:
                instance.reminded_complete_task = True
            instance.save()

@job
def send_new_task_email(instance, new_user=False, completed=False):
    instance = clean_instance(instance, Task)

    subject = "{} {} {} {} by {}{}".format(
        EMAIL_SUBJECT_PREFIX,
        completed and 'New wizard' or 'New',
        instance.scope == TASK_SCOPE_TASK and 'task' or 'project',
        completed and 'details completed' or 'created',
        instance.user.first_name, new_user and ' (New user)' or ''
    )

    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'owner': instance.user,
        'task': instance,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.id),
        'completed': completed
    }
    send_mail(subject, 'tunga/email/email_new_task', to, ctx)


@job
def send_new_task_community_email(instance):
    instance = clean_instance(instance, Task)

    # Notify Tunga and Devs or PMs
    community_receivers = None
    if (not instance.is_developer_ready) or (instance.approved and instance.visibility in [VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM]):

        # Filter users based on nature of work
        queryset = get_user_model().objects.filter(
            type=instance.is_developer_ready and USER_TYPE_DEVELOPER or USER_TYPE_PROJECT_MANAGER
        )

        # Only developers on client's team
        if instance.is_developer_ready and instance.visibility == VISIBILITY_MY_TEAM:
            queryset = queryset.filter(
                my_connections_q_filter(instance.user)
            )

        ordering = []

        # Order by matching skills
        task_skills = instance.skills.all()
        if task_skills:
            when = []
            for skill in task_skills:
                new_when = When(
                        userprofile__skills=skill,
                        then=1
                    )
                when.append(new_when)
            queryset = queryset.annotate(matches=Sum(
                Case(
                    *when,
                    default=0,
                    output_field=IntegerField()
                )
            ))
            ordering.append('-matches')

        # Order developers by tasks completed
        if instance.is_developer_ready:
            queryset = queryset.annotate(
                tasks_completed=Sum(
                    Case(
                        When(
                            participation__task__closed=True,
                            participation__user__id=F('id'),
                            participation__accepted=True,
                            then=1
                        ),
                        default=0,
                        output_field=IntegerField()
                    )
                )
            )
            ordering.append('-tasks_completed')

        if ordering:
            queryset = queryset.order_by(*ordering)
        if queryset:
            community_receivers = queryset[:15]

    subject = "{} New {} created by {}".format(
        EMAIL_SUBJECT_PREFIX, instance.scope == TASK_SCOPE_TASK and 'task' or 'project', instance.user.first_name
    )

    if community_receivers:
        to = [community_receivers[0].email]
        bcc = None
        if len(community_receivers) > 1:
            bcc = [user.email for user in community_receivers[1:]] if community_receivers[1:] else None
        ctx = {
            'owner': instance.user,
            'task': instance,
            'task_url': '%s/task/%s/' % (TUNGA_URL, instance.id)
        }
        send_mail(subject, 'tunga/email/email_new_task', to, ctx, bcc=bcc)


VERB_MAP_STATUS_CHANGE = {
    STATUS_SUBMITTED: 'submitted',
    STATUS_APPROVED: 'approved',
    STATUS_DECLINED: 'declined',
    STATUS_ACCEPTED: 'accepted',
    STATUS_REJECTED: 'rejected'
}


@job
def send_estimate_status_email(instance, estimate_type='estimate', target_admins=False):
    instance = clean_instance(instance, estimate_type == 'quote' and Quote or Estimate)
    if instance.status == STATUS_INITIAL:
        return

    actor = None
    target = None
    action_verb = VERB_MAP_STATUS_CHANGE.get(instance.status, None)
    recipients = None

    if instance.status in [STATUS_SUBMITTED]:
        actor = instance.user
        recipients = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    elif instance.status in [STATUS_APPROVED, STATUS_DECLINED]:
        actor = instance.moderated_by
        target = instance.user
        recipients = [instance.user.email]
    elif instance.status in [STATUS_ACCEPTED, STATUS_REJECTED]:
        actor = instance.reviewed_by
        if target_admins:
            recipients = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
        else:
            target = instance.user
            recipients = [instance.user.email]

            # Notify staff in a separate email
            send_estimate_status_email.delay(instance.id, estimate_type=estimate_type, target_admins=True)

    subject = "{} {} {} {}".format(
        EMAIL_SUBJECT_PREFIX,
        actor.first_name,
        action_verb,
        estimate_type == 'estimate' and 'an estimate' or 'a quote'
    )
    to = recipients

    ctx = {
        'owner': instance.user,
        'estimate': instance,
        'task': instance.task,
        'estimate_url': '{}/work/{}/{}/{}'.format(TUNGA_URL, instance.task.id, estimate_type, instance.id),
        'actor': actor,
        'target': target,
        'verb': action_verb,
        'noun': estimate_type
    }

    if send_mail(subject, 'tunga/email/email_estimate_status', to, ctx):
        if instance.status == STATUS_SUBMITTED:
            instance.moderator_email_at = datetime.datetime.utcnow()
            instance.save()
        if instance.status in [STATUS_ACCEPTED, STATUS_REJECTED]:
            instance.reviewed_email_at = datetime.datetime.utcnow()
            instance.save()

    if instance.status == STATUS_APPROVED:
        send_estimate_approved_client_email(instance, estimate_type=estimate_type)


def send_estimate_approved_client_email(instance, estimate_type='estimate'):
    instance = clean_instance(instance, estimate_type == 'quote' and Quote or Estimate)
    if instance.status != STATUS_APPROVED:
        return
    subject = "{} {} submitted {}".format(
        EMAIL_SUBJECT_PREFIX,
        instance.user.first_name,
        estimate_type == 'estimate' and 'an estimate' or 'a quote'
    )
    to = [instance.task.user.email]
    ctx = {
        'owner': instance.user,
        'estimate': instance,
        'task': instance.task,
        'estimate_url': '{}/work/{}/{}/{}'.format(TUNGA_URL, instance.task.id, estimate_type, instance.id),
        'actor': instance.user,
        'target': instance.task.user,
        'verb': 'submitted',
        'noun': estimate_type
    }

    if instance.task.source == TASK_SOURCE_NEW_USER and not instance.task.user.is_confirmed:
        url_prefix = '{}/reset-password/confirm/{}/{}?new_user=true&next='.format(
            TUNGA_URL, instance.user.uid, instance.user.generate_reset_token()
        )
        ctx['estimate_url'] = '{}{}'.format(url_prefix, ctx['estimate_url'])

    if send_mail(subject, 'tunga/email/email_estimate_status', to, ctx):
        instance.reviewer_email_at = datetime.datetime.utcnow()
        instance.save()


@job
def send_new_task_invitation_email(instance):
    instance = clean_instance(instance, Participation)
    subject = "%s Task invitation from %s" % (EMAIL_SUBJECT_PREFIX, instance.created_by.first_name)
    to = [instance.user.email]
    ctx = {
        'inviter': instance.created_by,
        'invitee': instance.user,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_new_task_invitation', to, ctx)


@job
def notify_task_invitation_response(instance):
    notify_task_invitation_response_email(instance)
    notify_task_invitation_response_slack(instance)


@job
def notify_task_invitation_response_email(instance):
    instance = clean_instance(instance, Participation)
    subject = "%s Task invitation %s by %s" % (
        EMAIL_SUBJECT_PREFIX, instance.accepted and 'accepted' or 'rejected', instance.user.first_name)
    to = list({instance.task.user.email, instance.created_by.email})
    ctx = {
        'inviter': instance.created_by,
        'invitee': instance.user,
        'accepted': instance.accepted,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_task_invitation_response', to, ctx)


@job
def notify_task_invitation_response_slack(instance):
    instance = clean_instance(instance, Participation)

    if not slack_utils.is_task_notification_enabled(instance.task, slugs.EVENT_APPLICATION):
        return

    task_url = '%s/work/%s/' % (TUNGA_URL, instance.task_id)
    slack_msg = "Task invitation %s by %s %s\n\n<%s|View details on Tunga>" % (
        instance.accepted and 'accepted' or 'rejected', instance.user.short_name,
        instance.accepted and ':smiley: :fireworks:' or ':unamused:',
        task_url
    )
    slack_utils.send_integration_message(instance.task, message=slack_msg)


@job
def notify_new_task_application(instance):
    notify_new_task_application_email(instance)
    notify_new_task_application_slack(instance)


@job
def notify_new_task_application_email(instance):
    instance = clean_instance(instance, Application)
    subject = "%s New application from %s" % (EMAIL_SUBJECT_PREFIX, instance.user.short_name)
    to = [instance.task.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'task': instance.task,
        'task_url': '%s/work/%s/applications/' % (TUNGA_URL, instance.task_id)
    }

    if instance.task.source == TASK_SOURCE_NEW_USER and not instance.user.is_confirmed:
        url_prefix = '{}/reset-password/confirm/{}/{}?new_user=true&next='.format(
            TUNGA_URL, instance.user.uid, instance.user.generate_reset_token()
        )
        ctx['task_url'] = '{}{}'.format(url_prefix, ctx['task_url'])
    send_mail(subject, 'tunga/email/email_new_task_application', to, ctx)


@job
def notify_new_task_application_slack(instance):
    instance = clean_instance(instance, Application)

    if not slack_utils.is_task_notification_enabled(instance.task, slugs.EVENT_APPLICATION):
        return

    application_url = '%s/work/%s/applications/' % (TUNGA_URL, instance.task_id)
    slack_msg = "New application from %s" % instance.user.short_name
    attachments = [
        {
            slack_utils.KEY_TITLE: instance.task.summary,
            slack_utils.KEY_TITLE_LINK: application_url,
            slack_utils.KEY_TEXT: '%s%s%s%s\n\n<%s|View details on Tunga>' %
                                  (truncatewords(convert_to_text(instance.pitch), 100),
                                   instance.hours_needed and '\n*Workload:* {} hrs'.format(instance.hours_needed) or '',
                                   instance.deliver_at and '\n*Delivery Date:* {}'.format(
                                       instance.deliver_at.strftime("%d %b, %Y at %H:%M GMT")
                                   ) or '',
                                   instance.remarks and '\n*Remarks:* {}'.format(
                                       truncatewords(convert_to_text(instance.remarks), 100)
                                   ) or '',
                                   application_url),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA
        }
    ]
    slack_utils.send_integration_message(instance.task, message=slack_msg, attachments=attachments)


@job
def send_new_task_application_response_email(instance):
    instance = clean_instance(instance, Application)
    subject = "%s Task application %s" % (EMAIL_SUBJECT_PREFIX, instance.accepted and 'accepted' or 'rejected')
    to = [instance.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'accepted': instance.accepted,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_task_application_response', to, ctx)


@job
def send_new_task_application_applicant_email(instance):
    instance = clean_instance(instance, Application)
    subject = "%s You applied for a task: %s" % (EMAIL_SUBJECT_PREFIX, instance.task.summary)
    to = [instance.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_new_task_application_applicant', to, ctx)


@job
def send_task_application_not_selected_email(instance):
    instance = clean_instance(instance, Task)
    rejected_applicants = instance.application_set.filter(
        responded=False
    )
    if rejected_applicants:
        subject = "%s Your application was not accepted for: %s" % (EMAIL_SUBJECT_PREFIX, instance.summary)
        to = [rejected_applicants[0].user.email]
        bcc = [dev.user.email for dev in rejected_applicants[1:]] if len(rejected_applicants) > 1 else None
        ctx = {
            'task': instance,
            'task_url': '%s/work/%s/' % (TUNGA_URL, instance.id)
        }
        send_mail(subject, 'tunga/email/email_task_application_not_selected', to, ctx, bcc=bcc)


@job
def send_progress_event_reminder(instance):
    send_progress_event_reminder_email(instance)


@job
def send_progress_event_reminder_email(instance):
    instance = clean_instance(instance, ProgressEvent)
    subject = "%s Upcoming Task Update" % (EMAIL_SUBJECT_PREFIX,)
    participants = instance.task.participation_set.filter(accepted=True)
    if participants:
        to = [participants[0].user.email]
        bcc = [participant.user.email for participant in participants[1:]] if participants.count() > 1 else None
        ctx = {
            'owner': instance.task.user,
            'event': instance,
            'update_url': '%s/work/%s/event/%s/' % (TUNGA_URL, instance.task.id, instance.id)
        }
        if send_mail(subject, 'tunga/email/email_progress_event_reminder', to, ctx, bcc=bcc):
            instance.last_reminder_at = datetime.datetime.utcnow()
            instance.save()


@job
def notify_new_progress_report(instance):
    notify_new_progress_report_email(instance)
    notify_new_progress_report_slack(instance)

@job
def notify_new_progress_report_email(instance):
    instance = clean_instance(instance, ProgressReport)
    subject = "%s %s submitted a Progress Report" % (EMAIL_SUBJECT_PREFIX, instance.user.display_name)
    to = [instance.event.task.user.email]
    ctx = {
        'owner': instance.event.task.user,
        'reporter': instance.user,
        'event': instance.event,
        'report': instance,
        'update_url': '%s/work/%s/event/%s/' % (TUNGA_URL, instance.event.task.id, instance.event.id)
    }
    send_mail(subject, 'tunga/email/email_new_progress_report', to, ctx)

@job
def notify_new_progress_report_slack(instance):
    instance = clean_instance(instance, ProgressReport)

    if not slack_utils.is_task_notification_enabled(instance.event.task, slugs.EVENT_PROGRESS):
        return

    report_url = '%s/work/%s/event/%s/' % (TUNGA_URL, instance.event.task_id, instance.event_id)
    slack_msg = "%s submitted a Progress Report | %s" % (
        instance.user.display_name, '<{}|View details on Tunga>'.format(report_url)
    )
    attachments = [
        {
            slack_utils.KEY_TITLE: instance.event.task.summary,
            slack_utils.KEY_TITLE_LINK: report_url,
            slack_utils.KEY_TEXT: '*Status:* %s'
                                  '\n*Percentage completed:* %s%s' %
                                  (instance.get_status_display(), instance.percentage, '%'),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
        }
    ]
    if instance.accomplished:
        attachments.append({
            slack_utils.KEY_TITLE: 'What has been accomplished since last update?',
            slack_utils.KEY_TEXT: convert_to_text(instance.accomplished),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
        })
    if instance.next_steps:
        attachments.append({
            slack_utils.KEY_TITLE: 'What are the next next steps?',
            slack_utils.KEY_TEXT: convert_to_text(instance.next_steps),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
        })
    if instance.obstacles:
        attachments.append({
            slack_utils.KEY_TITLE: 'What obstacles are impeding your progress?',
            slack_utils.KEY_TEXT: convert_to_text(instance.obstacles),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
        })
    if instance.remarks:
        attachments.append({
            slack_utils.KEY_TITLE: 'Other remarks or questions',
            slack_utils.KEY_TEXT: convert_to_text(instance.remarks),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_NEUTRAL
        })
    slack_utils.send_integration_message(instance.event.task, message=slack_msg, attachments=attachments)


@job
def send_task_invoice_request_email(instance):
    instance = clean_instance(instance, Task)
    subject = "%s %s requested for an invoice" % (EMAIL_SUBJECT_PREFIX, instance.user.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'owner': instance.user,
        'task': instance,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.id),
        'invoice_url': '%s/api/task/%s/download/invoice/?format=pdf' % (TUNGA_URL, instance.id)
    }
    send_mail(subject, 'tunga/email/email_task_invoice_request', to, ctx)
