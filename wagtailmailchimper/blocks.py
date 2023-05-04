from wagtail import blocks

from core.blocks import AbstractFormBlock


class FormBlock(AbstractFormBlock):
    heading = blocks.CharBlock()

    class Meta:
        handler = 'wagtailmailchimper.handlers.MailingListSubscriptionHandler'
        template = 'mailing_list_subscription_form.html'
        # defaults
        method = 'POST'
        icon = 'form'

    def get_context(self, request, *args, **kwargs):
        context = super(FormBlock, self).get_context(request, *args, **kwargs)
        return context