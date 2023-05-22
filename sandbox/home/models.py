from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import InlinePanel
from wagtail.contrib.forms.models import AbstractFormField
from wagtail.models import Page

from wagtailmailchimp.models import AbstractMailChimpPage, AbstractMailchimpIntegrationForm


class HomePage(Page):
    pass


class MailingListSubscribePage(AbstractMailChimpPage, Page):
    parent_page_types = ['home.HomePage']
    template = "subscribe/mailing_list_subscribe_page.html"

    content_panels = Page.content_panels + AbstractMailChimpPage.content_panels


class FormField(AbstractFormField):
    page = ParentalKey('SampleEventFormPageWithMailingListIntegration', on_delete=models.CASCADE,
                       related_name='form_fields')


class SampleEventFormPageWithMailingListIntegration(AbstractMailchimpIntegrationForm):
    parent_page_types = ['home.HomePage']
    template = 'integration/event_registration_page.html'
    landing_page_template = 'integration/form_thank_you_landing.html'

    content_panels = Page.content_panels + AbstractMailchimpIntegrationForm.integration_panels + [
        InlinePanel('form_fields', label="Form fields"),
    ]
