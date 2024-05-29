import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import BooleanField
from django.template import Context, Template
from django.utils.translation import gettext_lazy as _
from mailchimp3.mailchimpclient import MailChimpError
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel
from wagtail.contrib.forms.models import AbstractForm
from wagtail.contrib.settings.models import BaseSiteSetting
from wagtail.contrib.settings.registry import register_setting

from .api import MailchimpApi
from .widgets import MailchimpSubscriberOptinWidget, MailchimpAudienceSelectWidget


@register_setting
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

    def clean_fields(self, exclude=None):
        super().clean()

        if not self.api_key:
            return

        try:
            # Check if the API key is valid
            api = MailchimpApi(self.api_key)
            api.ping()
        except Exception as e:
            raise ValidationError({'api_key': str(e)})


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

    thank_you_text = models.TextField(blank=True, null=True,
                                      default="You have been successfully added to our mailing list. Thank you!",
                                      help_text=_("Message to show on successful submission"),
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
                FieldPanel('list_id', widget=MailchimpAudienceSelectWidget),
                FieldPanel('double_optin'),
            ], classname='label-above'),
        ], (_('MailChimp Settings'))),
        FieldPanel('thank_you_text')
    ]


class AbstractMailchimpIntegrationForm(AbstractForm):
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
        FieldPanel("audience_list_id", widget=MailchimpAudienceSelectWidget),
    ]

    is_mailchimp_integration = True

    def remove_mailchimp_field(self, form):
        form.fields.pop(self.mailchimp_field_name, None)
        return form.cleaned_data.pop(self.mailchimp_field_name, None)

    def serve(self, request, *args, **kwargs):
        # We need to access the request later on in integration operation
        self.request = request

        return super(AbstractMailchimpIntegrationForm, self).serve(request, *args, **kwargs)

    def should_perform_mailchimp_integration_operation(self, request, form):
        # override this method to add custom logic to determine if the
        # mailchimp integration operation should be performed
        return True

    def show_page_listing_mailchimp_integration_button(self):
        # override this method to add custom logic to determine if the
        # mailchimp integration button should be shown in the page listing
        return True

    def process_form_submission(self, form):
        self.remove_mailchimp_field(form)

        form_submission = super(AbstractMailchimpIntegrationForm, self).process_form_submission(form)

        if self.request:
            try:
                form_data = dict(form.data)
                user_checked_sub = bool(form_data.get(self.mailchimp_field_name, False))
                user_selected_interests = form_data.get(self.mailchimp_interests_field_name, None)

                if user_checked_sub and self.should_perform_mailchimp_integration_operation(self.request, form):
                    self.mailchimp_integration_operation(self, form=form, request=self.request,
                                                         user_selected_interests=user_selected_interests)
            except Exception as e:
                pass

        return form_submission

    def get_form(self, *args, **kwargs):
        form = super(AbstractMailchimpIntegrationForm, self).get_form(*args, **kwargs)

        if self.has_list_id_and_email:
            form.fields[self.mailchimp_field_name] = BooleanField(
                label='',
                required=False,
                widget=MailchimpSubscriberOptinWidget(
                    interest_categories=self.get_mc_data().get("interest_categories", []),
                    label=self.mailing_list_checkbox_label or self.default_mailing_list_checkbox_label,
                    interests_field_name=self.mailchimp_interests_field_name
                )
            )

        return form

    def mailchimp_integration_operation(self, instance, **kwargs):
        request = kwargs.get('request', None)

        mc_settings = MailchimpSettings.for_request(request)

        mailchimp = MailchimpApi(api_key=mc_settings.api_key)

        user_selected_interests = kwargs.get('user_selected_interests', None)

        rendered_dictionary = self.render_mc_dictionary(
            self.format_mc_form_submission(kwargs['form']),
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

    def format_mc_form_submission(self, form):
        formatted_form_data = {}

        for k, v in form.cleaned_data.items():
            formatted_form_data[k.replace('-', '_')] = v
        return formatted_form_data

    def get_mc_data(self):
        data = {
            "email_field": None,
            "merge_fields": {},
            "interest_categories": {}
        }

        merge_fields_mapping = {}
        if self.merge_fields_mapping:
            try:
                merge_fields_mapping = json.loads(self.merge_fields_mapping)
            except Exception:
                pass

        interest_categories = {}
        if self.interest_categories:
            try:
                interest_categories = json.loads(self.interest_categories)
            except Exception:
                pass

        for key, value in merge_fields_mapping.items():
            if key == "EMAIL":
                data.update({"email_field": merge_fields_mapping.get("EMAIL")})
            else:
                data["merge_fields"].update({key: value})

        data.update({"interest_categories": interest_categories})

        return data

    def get_mc_merge_fields(self):
        data = self.get_mc_data()
        if 'merge_fields' in data:
            return data.get('merge_fields')
        return {}

    def get_mc_email_field_template(self):
        return "{}{}{}".format("{{", self.get_mc_data()['email_field'], "}}")

    def get_mc_merge_fields_template(self):
        fields = self.get_mc_merge_fields()
        for key, value in fields.items():
            if value:
                fields[key] = "{}{}{}".format("{{", value, "}}")
        return fields

    @property
    def has_list_id_and_email(self):
        return bool(self.audience_list_id and self.get_mc_email_address())

    def get_mc_email_address(self):
        data = self.get_mc_data()
        if "email_field" in data:
            return data.get("email_field")
        return None

    def combine_mc_interest_categories(self):
        interest_dict = {}
        for interest_category in self.get_mc_data().get('interest_categories', []):
            for interest in interest_category.get("interests", []):
                interest_dict.update({interest.get("id"): interest.get("id")})

        return interest_dict

    def render_mc_dictionary(self, form_submission, user_selected_interests=None):

        interests = self.combine_mc_interest_categories(),

        if user_selected_interests:
            interests = {}
            for interest in user_selected_interests:
                interests[interest] = True

        rendered_dictionary_template = json.dumps({
            'email_address': self.get_mc_email_field_template(),
            'merge_fields': self.get_mc_merge_fields_template(),
            'interests': interests,
            'status': 'subscribed',
        })

        rendered_dictionary = Template(rendered_dictionary_template).render(Context(form_submission))
        return rendered_dictionary
