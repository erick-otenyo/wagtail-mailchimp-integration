from django.db import models
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel, PageChooserPanel
from django.utils.translation import gettext_lazy as _

class BaseMailChimpPage(models.Model):
    """
    Abstract MailChimp page definition.
    """
    list_id = models.CharField(_('MailChimp List ID'), max_length=50,
                               help_text=_('Enter the MailChimp list ID to use for this form'))
    double_optin = models.BooleanField(_('Double Opt-In'), default=True,
                                       help_text=_('Use double opt-in process for new subscribers'))
    thank_you_text = models.TextField(blank=True, null=True, help_text=_("Message to show on successful submission"),verbose_name=_("Thank you text"))

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
                FieldPanel('list_id'),
                FieldPanel('double_optin')
            ], classname='label-above'),
        ], (_('MailChimp Settings'))),
        FieldPanel('thank_you_text')
    ]