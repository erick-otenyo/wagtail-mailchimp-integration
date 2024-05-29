from django.db.utils import ProgrammingError
from django.forms.widgets import Input, Select
from wagtail.models import Site
from django.utils.translation import gettext as _

from .api import MailchimpApi
from .errors import MailchimpApiError


class CustomSelect(Select):
    def create_option(self, *args, **kwargs):
        option = super().create_option(*args, **kwargs)
        if not option.get('value'):
            option['attrs']['disabled'] = True

        return option


class MailchimpSubscriberOptinWidget(Input):
    input_type = 'checkbox'
    template_name = 'wagtailmailchimp/widgets/subscriber_optin_widget.html'

    def __init__(self, attrs=None, interest_categories=None, label=None, interests_field_name=None):
        super(MailchimpSubscriberOptinWidget, self).__init__()
        self.interest_categories = interest_categories
        self.interests_field_name = interests_field_name
        self.label = label

    def get_context(self, name, value, attrs):
        ctx = super(MailchimpSubscriberOptinWidget, self).get_context(name, value, attrs)
        ctx['widget']['interest_categories'] = self.interest_categories
        ctx['widget']['label'] = self.label
        ctx['widget']['interests_field_name'] = self.interests_field_name
        return ctx


class MailchimpAudienceSelectWidget(Input):
    template_name = 'wagtailmailchimp/widgets/audience_select_widget.html'

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        mailchimp_error = None

        audiences = []

        try:
            audiences = self.get_mailchimp_audience_lists()
        except MailchimpApiError as e:
            mailchimp_error = e.message
        except Exception as e:
            mailchimp_error = _("Error obtaining Mailchimp audiences. Please make sure the Mailchimp API "
                                "key in Mailchimp Settings is correct")

        ctx["widget"].update({
            "value": value,
            "mailchimp_error": mailchimp_error,
            "audiences": audiences,
            "no_audiences_message": _("No Mailchimp audiences found. Please create one on Mailchimp and try again.")
        })

        return ctx

    def get_mailchimp_audience_lists(self):
        from .models import MailchimpSettings

        # catch error where 'wagtailcore_site' relation is not migrated to db yet
        try:
            current_site = Site.objects.get(is_default_site=True)
        except ProgrammingError:
            return []

        mc_settings = MailchimpSettings.for_site(current_site)

        if not mc_settings.api_key:
            raise MailchimpApiError("Mailchimp API key is not set")

        mailchimp = MailchimpApi(api_key=mc_settings.api_key)
        lists = mailchimp.get_lists()

        return lists
