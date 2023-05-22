import json

from django.forms.widgets import Input, Select
from django.template.loader import render_to_string
from wagtail.models import Site

from .api import MailchimpApi


class CustomSelect(Select):
    def create_option(self, *args, **kwargs):
        option = super().create_option(*args, **kwargs)
        if not option.get('value'):
            option['attrs']['disabled'] = True

        return option


class MailchimpSubscriberIntegrationWidget(Input):
    template_name = 'wagtailmailchimp/widgets/subscriber_integration_widget.html'
    js_template_name = 'wagtailmailchimp/widgets/subscriber_integration_js.html'

    def get_context(self, name, value, attrs):

        ctx = super(MailchimpSubscriberIntegrationWidget, self).get_context(name, value, attrs)

        json_value = self.get_json_value(value)
        list_library = self.build_list_library()
        ctx['widget']['value'] = json.dumps(json_value)
        ctx['widget']['extra_js'] = self.render_js(name, json.dumps(list_library), json_value)
        ctx['widget']['selectable_mailchimp_lists'] = self.get_selectable_mailchimp_lists(list_library)
        ctx['widget']['stored_mailchimp_list'] = self.get_stored_mailchimp_list(json_value)

        return ctx

    def render_js(self, name, list_library, json_value):
        ctx = {
            'widget_name': name,
            'widget_js_name': name.replace('-', '_'),
            'list_library': list_library,
            'stored_mailchimp_list': self.get_stored_mailchimp_list(json_value),
            'stored_merge_fields': self.get_stored_merge_fields(json_value),
        }

        return render_to_string(self.js_template_name, ctx)

    def get_json_value(self, value):
        if value:
            json_value = json.loads(value)
        else:
            json_value = json.loads('{}')
        if 'list_id' not in json_value:
            json_value['list_id'] = ""
        if 'merge_fields' not in json_value:
            json_value['merge_fields'] = {}
        if 'email_field' not in json_value:
            json_value['email_field'] = ""
        if 'interest_categories' not in json_value:
            json_value['interest_categories'] = {}
        if 'interests_mapping' not in json_value:
            json_value['interests_mapping'] = {}
        return json_value

    def get_stored_mailchimp_list(self, value):
        if 'list_id' in value:
            return str(value['list_id'])

    def get_stored_merge_fields(self, value):
        if 'merge_fields' in value:
            return json.dumps(value['merge_fields'])
        return json.dumps({})

    def get_selectable_mailchimp_lists(self, library):
        selectable_lists = [('', 'Please select one of your Mailchimp Lists.')]
        for k, v in library.items():
            selectable_lists.append((k, v['name']))

        return selectable_lists

    def build_list_library(self):
        from .models import MailchimpSettings

        current_site = Site.objects.get(is_default_site=True)

        mc_settings = MailchimpSettings.for_site(current_site)
        mailchimp = MailchimpApi(api_key=mc_settings.api_key)
        list_library = {}
        if mailchimp.is_active:
            lists = mailchimp.get_lists()
            for mlist in lists:
                list_library[mlist['id']] = {
                    'name': mlist['name'],
                    'merge_fields': {},
                    'interest_categories': {}
                }

                list_library[mlist['id']]['merge_fields'] = mailchimp.get_merge_fields_for_list(
                    mlist['id'],
                    fields="merge_fields.merge_id,"
                           "merge_fields.tag,"
                           "merge_fields.required,"
                           "merge_fields.name,")

                list_library[mlist['id']]['interest_categories'] = \
                    mailchimp.get_interest_categories_for_list(mlist['id'], fields="categories.id,"
                                                                                   "categories.title,")

                for category in list_library[mlist['id']]['interest_categories']:
                    category['interests'] = mailchimp.get_interests_for_interest_category(
                        mlist['id'], category['id'],
                        fields="interests.id,"
                               "interests.name,")

        return list_library


class MailchimpSubscriberOptinWidget(Input):
    input_type = 'checkbox'
    template_name = 'wagtailmailchimp/widgets/subscriber_optin_widget.html'
    js_template_name = 'wagtailmailchimp/widgets/subscriber_optin_js.html'

    def __init__(self, attrs=None, interests=None, label=None, interests_mapping=None, interests_field_name=None):
        super(MailchimpSubscriberOptinWidget, self).__init__()
        self.interests = interests
        self.interests_mapping = interests_mapping
        self.interests_field_name = interests_field_name
        self.label = label

    def get_context(self, name, value, attrs):
        ctx = super(MailchimpSubscriberOptinWidget, self).get_context(name, value, attrs)
        ctx['widget']['interests'] = self.interests
        ctx['widget']['label'] = self.label
        ctx['widget']['interests_mapping'] = self.interests_mapping
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
