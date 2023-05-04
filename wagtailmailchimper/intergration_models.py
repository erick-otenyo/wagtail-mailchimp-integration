import json

from django.contrib import messages
from django.db import models
from django.forms import BooleanField
from django.forms.widgets import Input
from django.template import Context, Template
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from mailchimp3.mailchimpclient import MailChimpError
from wagtail.admin.panels import FieldPanel
from wagtail.contrib.forms.models import AbstractForm
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from core.mail import mail_developers
from .api import MailchimpApi
from .models import MailChimpApiContact


class MailchimpSubscriberIntegrationWidget(Input):
    template_name = 'subscriber_integration_widget.html'
    js_template_name = 'subscriber_integration_js.html'

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
        mailchimp = MailchimpApi()
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
    template_name = 'subscriber_optin_widget.html'
    js_template_name = 'subscriber_optin_js.html'

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


class MailchimpSubscriberIntegrationForm(AbstractForm, models.Model):
    class Meta:
        abstract = True

    MAILCHIMP_FIELD_NAME = 'mailchimp_sub_check'
    MAILCHIMP_INTERESTS_FIELD_NAME = 'mailchimp_interests_check'
    DEFAUL_MAILING_LIST_CHECKBOX_LABEL = "Join Our Mailing List"

    subscriber_json_data = models.TextField(
        blank=True,
        verbose_name=_("Mailing List Settings")
    )
    enable_mailing_list_subscription = models.BooleanField(default=False, verbose_name=_("Enable Mailing list subscription"))

    mailing_list_checkbox_label = models.CharField(max_length=200, blank=True, verbose_name=_("Mailing list checkbox label"))

    integration_panels = [
        FieldPanel('enable_mailing_list_subscription'),
        FieldPanel('subscriber_json_data', widget=MailchimpSubscriberIntegrationWidget),
        FieldPanel('mailing_list_checkbox_label')
    ]

    def remove_mailchimp_field(self, form):
        form.fields.pop(self.MAILCHIMP_FIELD_NAME, None)
        return form.cleaned_data.pop(self.MAILCHIMP_FIELD_NAME, None)

    def process_form_submission(self, form, request=None):

        self.remove_mailchimp_field(form)

        form_submission = super(MailchimpSubscriberIntegrationForm, self).process_form_submission(form)

        try:
            self.post_process_submission(form, form_submission)
        except Exception as e:
            print(str(e))

        return form_submission

    def post_process_submission(self, form, form_submission):
        pass

    def should_process_form(self, request, form_data):
        return True

    def render_landing_page(self, request, form_submission=None, *args, form_context=None, **kwargs):
        context = self.get_context(request)
        context['form_submission'] = form_submission
        if form_context:
            context.update(form_context)

        return TemplateResponse(
            request,
            self.get_landing_page_template(request),
            context
        )

    @method_decorator(csrf_exempt)
    def serve(self, request, *args, **kwargs):
        if request.method == 'POST':
            form = self.get_form(request.POST, request.FILES, page=self, user=request.user)

            if form.is_valid():
                form_submission = None
                hide_thank_you_text = False
                if self.should_process_form(request, form.cleaned_data):
                    form_submission = self.process_form_submission(form)
                    form_data = dict(form.data)
                    user_checked_sub = bool(form_data.get(self.MAILCHIMP_FIELD_NAME, False))
                    user_selected_interests = form_data.get(self.MAILCHIMP_INTERESTS_FIELD_NAME, None)

                    if self.enable_mailing_list_subscription and user_checked_sub:
                        self.integration_operation(self, form=form, request=request,
                                                   user_selected_interests=user_selected_interests)
                else:
                    # we have an issue with the form submission.Don't show thank you text
                    hide_thank_you_text = True

                return self.render_landing_page(request, form_submission,
                                                *args,
                                                form_context={'hide_thank_you_text': hide_thank_you_text},
                                                **kwargs)

        form = self.get_form(page=self, user=request.user)
        context = self.get_context(request)

        if self.enable_mailing_list_subscription and self.has_list_id_and_email:
            form.fields[self.MAILCHIMP_FIELD_NAME] = BooleanField(
                label='',
                required=False,
                widget=MailchimpSubscriberOptinWidget(
                    interests=self.combine_interest_categories(),
                    label=self.mailing_list_checkbox_label or self.DEFAUL_MAILING_LIST_CHECKBOX_LABEL,
                    interests_mapping=self.interests_mapping,
                    interests_field_name=self.MAILCHIMP_INTERESTS_FIELD_NAME
                )
            )

        if self.registration_limit:
            context['submission_count'] = self.get_submission_class().objects.filter(page=self).count()

        context['form'] = form
        return TemplateResponse(
            request,
            self.get_template(request),
            context
        )

    def integration_operation(self, instance, **kwargs):
        mailchimp = MailchimpApi()
        if mailchimp.is_active:

            user_selected_interests = kwargs.get('user_selected_interests', None)

            rendered_dictionary = self.render_dictionary(
                self.format_form_submission(kwargs['form']),
                user_selected_interests=user_selected_interests
            )
            request = kwargs.get('request', None)

            try:
                dict_data = json.loads(rendered_dictionary)
                list_id = self.get_list_id()
                mailchimp.add_user_to_list(list_id=list_id, data=dict_data)

                MailChimpApiContact.objects.create(source=self.title, email=dict_data['email_address'],
                                                   list_id=list_id)

                if request:
                    messages.add_message(request, messages.INFO,
                                         'You have been successfully added to our mailing list!')
            except MailChimpError as e:
                if request:
                    if e.args and e.args[0]:
                        error = e.args[0]
                        if error['title']:
                            if error['title'] == "Member Exists":
                                messages.add_message(request, messages.INFO,
                                                     "You are already subscribed to our mailing list. Thank you!")
                        else:
                            messages.add_message(
                                request, messages.ERROR,
                                "You have successfully registered this event, but we are having issues"
                                " adding you to our mailing list. We will try to add you later")
            except Exception as e:
                if request:
                    messages.add_message(
                        request, messages.ERROR,
                        "You have successfully registered this event, but we are having issues"
                        "adding you to our mailing list. We will try to add you later")
                # send dev error email
                mail_developers(subject="Error when adding user to mailing list", message=str(e))

    def format_form_submission(self, form):
        formatted_form_data = {}

        for k, v in form.cleaned_data.items():
            formatted_form_data[k.replace('-', '_')] = v
        return formatted_form_data

    def get_data(self):
        return json.loads(self.subscriber_json_data)

    def get_merge_fields(self):
        if 'merge_fields' in self.get_data():
            return self.get_data()['merge_fields']
        return {}

    def get_email_field_template(self):
        return "{}{}{}".format("{{", self.get_data()['email_field'], "}}")

    def get_merge_fields_template(self):
        fields = self.get_merge_fields()
        for key, value in fields.items():
            if value:
                fields[key] = "{}{}{}".format("{{", value, "}}")
        return fields

    @property
    def has_list_id_and_email(self):
        return self.get_list_id() and self.get_email_address()

    @property
    def interests_mapping(self):
        if 'interests_mapping' in self.get_data():
            return self.get_data()['interests_mapping']
        return None

    def get_list_id(self):
        if 'list_id' in self.get_data():
            return self.get_data()['list_id']
        return None

    def get_email_address(self):
        if 'email_field' in self.get_data():
            return self.get_data()['email_field']
        return None

    def combine_interest_categories(self):
        interest_dict = {}
        for category_id, value in self.get_data()['interest_categories'].items():
            interest_dict.update(value['interests'])

        return interest_dict

    def render_dictionary(self, form_submission, user_selected_interests=None):

        interests = self.combine_interest_categories(),

        if user_selected_interests:
            interests = {}
            for interest in user_selected_interests:
                interests[interest] = True

        rendered_dictionary_template = json.dumps({
            'email_address': self.get_email_field_template(),
            'merge_fields': self.get_merge_fields_template(),
            'interests': interests,
            'status': 'subscribed',
        })
        rendered_dictionary = Template(rendered_dictionary_template).render(Context(form_submission))
        return rendered_dictionary