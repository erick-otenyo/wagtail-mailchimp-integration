from django.forms.widgets import Input, Select
from wagtail.models import Site

from .api import MailchimpApi


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


class MailchimpAudienceListWidget(Select):
    def __init__(self, attrs=None, choices=()):
        super().__init__(attrs, choices)

        audience_lists = self.get_mailchimp_audience_lists()
        audience_choices = [("", "-- None --")]

        for audience in audience_lists:
            audience_choices.append([audience.get("id"), audience.get("name")])

        self.choices = audience_choices

    def get_mailchimp_audience_lists(self):
        from .models import MailchimpSettings

        current_site = Site.objects.get(is_default_site=True)

        mc_settings = MailchimpSettings.for_site(current_site)
        mailchimp = MailchimpApi(api_key=mc_settings.api_key)
        lists = mailchimp.get_lists()

        return lists
