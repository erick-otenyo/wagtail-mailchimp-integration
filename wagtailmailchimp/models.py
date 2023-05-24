import json

from django.contrib import messages
from django.db import models
from django.forms import BooleanField
from django.template import Context, Template
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from mailchimp3.mailchimpclient import MailChimpError
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel
from wagtail.contrib.forms.models import AbstractForm
from wagtail.contrib.settings.models import BaseSiteSetting
from wagtail.contrib.settings.registry import register_setting

from .api import MailchimpApi
from .widgets import MailchimpSubscriberOptinWidget, MailchimpAudienceListWidget


@register_setting(icon="cogs")
class MailchimpSettings(BaseSiteSetting):
    api_key = models.CharField(verbose_name=_("Mailchimp API Key"), max_length=50, blank=True, null=True,
                               help_text=_("Mailchimp API Key "))
    default_audience_id = models.CharField(verbose_name=_("Default Mailchimp Audience Id"), max_length=100, blank=True,
                                           null=True,
                                           help_text=_("Default Mailchimp Audience Id"))

    panels = [
        FieldPanel("api_key"),
        FieldPanel("default_audience_id"),
    ]


class AbstractMailChimpPage(models.Model):
    """
    Abstract MailChimp page definition.
    """
    list_id = models.CharField(_('MailChimp Audience'), max_length=50,
                               help_text=_('Select MailChimp Audience to use for this form'))
    double_optin = models.BooleanField(_('Double Opt-In'), default=False,
                                       help_text=_(
                                           'Check to use double opt-in process for new subscribers. '
                                           'If enabled, users must confirm their subscription via '
                                           'an email sent by MailChimp'))

    success_redirect_page = models.ForeignKey(
        'wagtailcore.Page',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_("Success Redirect Page"),
        help_text=_(
            "Page to redirect to after successful submission.Leave unselected to show this page with an empty form")
    )

    thank_you_text = models.TextField(blank=True, null=True, help_text=_("Message to show on successful submission"),
                                      verbose_name=_("Thank you text"))

    class Meta(object):
        abstract = True

    def serve(self, request):
        """
        Serves the page as a MailChimpView.

        :param request: the request object.
        :rtype: django.http.HttpResponse.
        """

        from .views import MailChimpView

        view = MailChimpView.as_view(page_instance=self)
        return view(request)

    content_panels = [
        MultiFieldPanel([
            FieldRowPanel([
                FieldPanel('list_id', widget=MailchimpAudienceListWidget),
                FieldPanel('double_optin'),
            ], classname='label-above'),
            FieldPanel('success_redirect_page')
        ], (_('MailChimp Settings'))),
        FieldPanel('thank_you_text')
    ]


class AbstractMailchimpIntegrationForm(AbstractForm, models.Model):
    class Meta:
        abstract = True

    mailchimp_field_name = 'mailchimp_subscribe_check'
    mailchimp_interests_field_name = 'mailchimp_interests_check'
    default_mailing_list_checkbox_label = _("Join Our Mailing List")

    audience_list_id = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('MailChimp Audience'),
                                        help_text=_('Select MailChimp Audience to add users to'))
    merge_fields_mapping = models.TextField(blank=True, null=True)
    interest_categories = models.TextField(blank=True, null=True)

    mailing_list_checkbox_label = models.CharField(max_length=200, blank=True,
                                                   verbose_name=_("Mailing list checkbox label"))

    integration_panels = [
        FieldPanel("audience_list_id", widget=MailchimpAudienceListWidget),
    ]

    def remove_mailchimp_field(self, form):
        form.fields.pop(self.mailchimp_field_name, None)
        return form.cleaned_data.pop(self.mailchimp_field_name, None)

    def process_form_submission(self, form, request=None):

        self.remove_mailchimp_field(form)

        form_submission = super(AbstractMailchimpIntegrationForm, self).process_form_submission(form)

        try:
            self.post_process_submission(form, form_submission)
        except Exception as e:
            pass

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
                    user_checked_sub = bool(form_data.get(self.mailchimp_field_name, False))
                    user_selected_interests = form_data.get(self.mailchimp_interests_field_name, None)

                    if user_checked_sub:
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

        if self.has_list_id_and_email:
            form.fields[self.mailchimp_field_name] = BooleanField(
                label='',
                required=False,
                widget=MailchimpSubscriberOptinWidget(
                    interest_categories=self.get_data().get("interest_categories", []),
                    label=self.mailing_list_checkbox_label or self.default_mailing_list_checkbox_label,
                    interests_field_name=self.mailchimp_interests_field_name
                )
            )

        context['form'] = form
        return TemplateResponse(
            request,
            self.get_template(request),
            context
        )

    def integration_operation(self, instance, **kwargs):
        request = kwargs.get('request', None)

        mc_settings = MailchimpSettings.for_request(request)

        mailchimp = MailchimpApi(api_key=mc_settings.api_key)

        user_selected_interests = kwargs.get('user_selected_interests', None)

        rendered_dictionary = self.render_dictionary(
            self.format_form_submission(kwargs['form']),
            user_selected_interests=user_selected_interests
        )

        try:
            dict_data = json.loads(rendered_dictionary)
            list_id = self.audience_list_id
            mailchimp.add_user_to_list(list_id=list_id, data=dict_data)
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
                    "We are having issues adding you to our mailing list. We will try to add you later")

    def format_form_submission(self, form):
        formatted_form_data = {}

        for k, v in form.cleaned_data.items():
            formatted_form_data[k.replace('-', '_')] = v
        return formatted_form_data

    def get_data(self):
        data = {
            "email_field": None,
            "merge_fields": {},
            "interest_categories": {}
        }

        merge_fields_mapping = json.loads(self.merge_fields_mapping)

        interest_categories = json.loads(self.interest_categories)

        for key, value in merge_fields_mapping.items():
            if key == "EMAIL":
                data.update({"email_field": merge_fields_mapping.get("EMAIL")})
            else:
                data["merge_fields"].update({key: value})

        data.update({"interest_categories": interest_categories})

        return data

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
        return self.audience_list_id and self.get_email_address()

    def get_email_address(self):
        if "email_field" in self.get_data():
            return self.get_data().get("email_field")
        return None

    def combine_interest_categories(self):
        interest_dict = {}
        for interest_category in self.get_data().get('interest_categories', []):
            for interest in interest_category.get("interests", []):
                interest_dict.update({interest.get("id"): interest.get("id")})

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
