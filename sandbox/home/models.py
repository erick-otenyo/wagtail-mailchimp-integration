from django.db import models, ProgrammingError
from django.template.loader import render_to_string
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import InlinePanel
from wagtail.contrib.forms.models import AbstractFormField
from wagtail.models import Page, Site
from wagtail.signals import page_published

from wagtailmailchimp.api import MailchimpApi
from wagtailmailchimp.models import AbstractMailChimpPage, AbstractMailchimpIntegrationForm, MailchimpSettings


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


class SampleProductPage(Page):
    template = 'product/product_page.html'
    email_template = "product/product_page_email_template.html"
    content_panels = Page.content_panels


def receiver(sender, **kwargs):
    page = kwargs.get("instance")
    if page.email_template:
        try:
            current_site = Site.objects.get(is_default_site=True)
            email_html = render_to_string(page.email_template, context={"page": page})
            mc_settings = MailchimpSettings.for_site(current_site)
            mailchimp = MailchimpApi(api_key=mc_settings.api_key)

            campaign_data = {
                "recipients":
                    {
                        "list_id": "a15992e5ca"
                    },
                "settings":
                    {
                        "subject_line": page.title,
                        "from_name": "rickotiz@gmail.com",
                        "reply_to": "rickotiz@gmail.com"
                    },
                "type": "regular"
            }

            new_campaign = mailchimp.client.campaigns.create(data=campaign_data)
            update_data = {
                'message': 'Campaign message',
                'html': email_html
            }
            mailchimp.client.campaigns.content.update(campaign_id=new_campaign.get("id"), data=update_data)

        except ProgrammingError:
            pass


# Register listeners for each page model class
page_published.connect(receiver, sender=SampleProductPage)
