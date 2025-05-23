from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin import widgets as wagtail_admin_widgets

from .views import mailchimp_integration_view


@hooks.register('register_admin_urls')
def urlconf_wagtail_mailchimp():
    return [
        path('mailchimp-integration/<int:page_id>', mailchimp_integration_view, name="mailchimp_integration_view"),
    ]


@hooks.register('register_page_listing_buttons')
def page_listing_buttons(page, user, next_url=None):
    if hasattr(page, "is_mailchimp_integration") and hasattr(page, "audience_list_id"):
        if page.audience_list_id and page.show_page_listing_mailchimp_integration_button():
            url = reverse("mailchimp_integration_view", args=[page.pk, ])
            yield wagtail_admin_widgets.PageListingButton(
                "Mailchimp Integration",
                url,
                priority=60
            )
