import re
import json
from decimal import Decimal

from allauth.socialaccount.models import SocialToken
from django.apps import apps as django_apps
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.template.defaultfilters import urlizetrunc, safe
from django.utils.html import strip_tags


def get_tunga_model(model):
    """
    Returns the Model class.
    """
    try:
        return django_apps.get_model(model)
    except ValueError:
        raise ImproperlyConfigured("Model must be of the form 'app_label.model_name'")
    except LookupError:
        raise ImproperlyConfigured("Model has not been installed")


def clean_instance(instance, model):
    if instance and model:
        if isinstance(instance, model):
            return instance
        else:
            try:
                return model.objects.get(id=instance)
            except:
                return None
    else:
        return None


def pdf_base64encode(pdf_filename):
    return open(pdf_filename, "rb").read().encode("base64")


def swagger_permission_denied_handler(request):
    return HttpResponseRedirect('%s://%s/api/login/?next=/api/docs/' % (request.scheme, request.get_host()))


class Echo(object):
    """An object that implements just the write method of the file-like
    interface.
    """
    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


class GenericObject:
    def __init__(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)


def get_social_token(user, provider):
    try:
        return SocialToken.objects.filter(account__user=user, account__provider=provider).latest('expires_at')
    except SocialToken.DoesNotExist:
        return None


def convert_to_text(body):
    return strip_tags(re.sub(r'<br\s*/>', '\n', body, flags=re.IGNORECASE))


def convert_to_html(body):
    return safe(
        re.sub(
            r'<a([^>]+)>(?:http|ftp)s?://([^<]+)</a>',
            '<a\\1>\\2</a>',
            re.sub(
                r'<a([^>]+)(?<!target=)>',
                '<a target="_blank"\\1>',
                urlizetrunc(re.sub(r'(<br\s*/>)?\n', '<br/>', body, flags=re.IGNORECASE), limit=50, autoescape=False),
                flags=re.IGNORECASE
            ),
            re.IGNORECASE
        )
    )


def round_decimal(number, ndigits):
    formatter = '{0:.%sf}' % ndigits
    return Decimal(formatter.format(Decimal(number)))


def get_serialized_id(number, max_digits=4):
    remainder_max_digits = number % (10 ** max_digits)
    divider_max_digits = (number // (10 ** max_digits))
    letters = convert_to_base_alphabet(divider_max_digits)
    return '{}{:04d}'.format(letters, remainder_max_digits)


def convert_to_base_alphabet(number):
    remainder_letters = number % 26
    divider_letters = number // 26

    last_letter = chr(ord('A') + remainder_letters)
    base_alphabet_string = last_letter

    if divider_letters > 0:
        base_alphabet_string = '{}{}'.format(convert_to_base_alphabet(divider_letters-1), base_alphabet_string)
    return base_alphabet_string


def clean_meta_value(meta_value):
    if isinstance(meta_value, (str, unicode, int, float)):
        return meta_value
    elif isinstance(meta_value, dict):
        try:
            return json.dumps(meta_value)
        except:
            pass
    return str(meta_value)
