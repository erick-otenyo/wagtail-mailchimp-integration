import json
from datetime import date

from django.core.mail import mail_admins
from django.forms.forms import NON_FIELD_ERRORS
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import FormView
from mailchimp3.mailchimpclient import MailChimpError
from modelcluster.models import get_all_child_relations
from wagtail.contrib.forms.models import AbstractFormField
from wagtail.models import Page

from .api import MailchimpApi
from .forms import MailChimpForm, MailchimpIntegrationForm
from .models import MailchimpSettings


class MailChimpView(FormView):
    """
    Displays and processes a form based on a MailChimp list.
    """
    form_class = MailChimpForm
    page_instance = None
    merge_fields = None
    interest_categories = None
    api = None

    def get_api(self):
        if self.api:
            return self.api
        mc_settings = MailchimpSettings.for_request(self.request)
        self.api = MailchimpApi(api_key=mc_settings.api_key)
        return self.api

    def get_clean_merge_fields(self, form):
        """
        Returns dictionary of MailChimp merge variables with cleaned
        form values.

        :param form: the form instance.
        :rtype: dict.
        """
        merge_fields = {}

        # Add merge variable values.
        for merge_field in self.get_merge_fields():
            mc_type = merge_field.get('type', '')
            name = merge_field.get('tag', '')
            value = form.cleaned_data.get(name, '')

            # Assemble address components into a single string value per
            # http://kb.mailchimp.com/lists/growth/format-list-fields#Address.
            if mc_type == 'address':
                values = []
                for f in ['addr1', 'addr2', 'city', 'state', 'zip', 'country']:
                    key = '{0}-{1}'.format(name, f)
                    val = form.cleaned_data.get(key)
                    if val:
                        values.append(val)
                value = '  '.join(values)

            # Convert date to string.
            if mc_type == 'date' and isinstance(value, date):
                value = value.strftime('%m/%d/%Y')

            # Convert birthday to string.
            if mc_type == 'birthday' and isinstance(value, date):
                value = value.strftime('%m/%d')

            if value:
                merge_fields.update({name: value})

        return merge_fields

    def get_context_data(self, **kwargs):
        """
        Returns view context data dictionary.

        :rtype: dict.
        """
        context = super(MailChimpView, self).get_context_data(**kwargs)
        page = self.page_instance
        context.update({'self': page, 'page': page, })

        return context

    def get_interest_categories(self):
        """
        Returns list of MailChimp grouping dictionaries.

        :rtype: dict.
        """

        api = self.get_api()

        if self.interest_categories is None:
            list_id = self.page_instance.list_id

            interest_categories = api.get_interest_categories_for_list(list_id=list_id)

            categories = []

            for category in interest_categories:
                category_id = category.get('id', '')

                interest_category = {
                    "id": category_id,
                    "title": category.get('title', ''),
                    'type': category.get('type', '')
                }

                interests = api.get_interests_for_interest_category(list_id=list_id,
                                                                    interest_category_id=category_id)

                interest_category['interests'] = interests

                categories.append(interest_category)

            self.interest_categories = categories

        return self.interest_categories

    def get_merge_fields(self):

        """
        Returns list of MailChimp merge fields dictionaries.

        :rtype: dict.
        """

        api = self.get_api()

        if self.merge_fields is None:
            self.merge_fields = api.get_merge_fields_for_list(self.page_instance.list_id)

        # If we don't have any merge variables to build a form from,
        # raise an HTTP 404 error.
        if not self.merge_fields:
            raise Http404

        return self.merge_fields

    def get_form(self, form_class=None):
        """
        Returns MailChimpForm instance.

        :param form_class: name of the form class to use.
        :rtype: MailChimpForm.
        """

        merge_fields = self.get_merge_fields()
        interest_categories = self.get_interest_categories()
        return MailChimpForm(merge_fields, interest_categories, **self.get_form_kwargs())

    def get_template_names(self):
        """
        Returns list of available template names.

        :rtype: list.
        """
        return [self.page_instance.get_template(self.request)]

    def form_valid(self, form):

        """
        Subscribes to MailChimp list if form is valid.

        :param form: the form instance.
        """

        api = self.get_api()

        # Subscribe to the MailChimp list.
        clean_merge_fields = self.get_clean_merge_fields(form)

        # raise Exception(clean_merge_vars)

        status = "subscribed"

        if self.page_instance.double_optin:
            status = 'pending'

        clean_interests = form.cleaned_data.get('INTERESTS', [])

        interests_payload = {}

        for interest in clean_interests:
            interests_payload[interest] = True

        error_traceback = None

        context = {'page': self.page_instance, 'self': self.page_instance}

        # Must have an email address.
        if 'EMAIL' in clean_merge_fields:
            data = {
                'email_address': clean_merge_fields.pop('EMAIL'),
                'merge_fields': clean_merge_fields,
                'status': status,
            }

            if interests_payload:
                data['interests'] = interests_payload

            try:
                list_id = self.page_instance.list_id
                api.add_user_to_list(list_id=list_id, data=data)
            except MailChimpError as e:
                error_traceback = e
                if e.args and e.args[0]:
                    error = e.args[0]
                    if error['title']:
                        if error['title'] == "Member Exists":
                            context.update({
                                "success_message": _("You are already subscribed to our mailing list. Thank you!"),
                                "form": self.get_form(),
                            })
                            return self.render_to_response(context)

            except Exception as e:
                error_traceback = e
        else:
            if not api:
                error_traceback = "MAILCHIMP API not active"
            else:
                error_traceback = "No email in fields"

        if error_traceback:
            mail_admins("Error adding user to mailing list", str(error_traceback), fail_silently=True)

            form.errors[NON_FIELD_ERRORS] = form.error_class(
                [_("We are having issues adding you to our mailing list. Please try later")]
            )
            return super(MailChimpView, self).form_invalid(form)

        default_success_message = _("You have been successfully added to our mailing list")

        context.update({
            "success_message": self.page_instance.thank_you_text or default_success_message,
            "form": self.get_form(),
        })

        return self.render_to_response(context)


def mailchimp_integration_view(request, page_id):
    page = Page.objects.get(pk=page_id)
    form_page = page.specific
    edit_url = reverse("wagtailadmin_pages:edit", args=[form_page.pk])
    context = {"page": form_page, "page_edit_url": edit_url}
    template_name = "wagtailmailchimp/mailchimp_integration_form.html"

    parent_page = form_page.get_parent()
    explore_url = reverse("wagtailadmin_explore", args=[parent_page.id])

    form_fields_rel_name = None
    # get form fields relation name
    relations = get_all_child_relations(form_page)
    for relation in relations:
        related_name = relation.related_name
        rels = getattr(form_page, related_name)
        # check if is instance of AbstractFormField
        if isinstance(rels.first(), AbstractFormField):
            form_fields_rel_name = related_name
            break

    merge_fields = None
    form_fields = None
    has_form_fields = False
    interest_categories = None

    if form_fields_rel_name and hasattr(form_page, form_fields_rel_name):
        form_fields = getattr(form_page, form_fields_rel_name).all()
        mc_settings = MailchimpSettings.for_request(request)
        api = MailchimpApi(api_key=mc_settings.api_key)
        lists = api.get_lists()

        for audience in lists:
            if audience.get("id") == form_page.audience_list_id:
                context.update({"audience": audience})
                break
        merge_fields = api.get_merge_fields_for_list(form_page.audience_list_id)
        interest_categories = api.get_interests_for_list(form_page.audience_list_id)

    if form_fields is not None:
        has_form_fields = True

    context.update({"has_form_fields": has_form_fields})

    if request.method == 'POST':
        form = MailchimpIntegrationForm(merge_fields=merge_fields, form_fields=form_fields, data=request.POST)

        if form.is_valid():
            merge_fields_data = json.dumps(form.cleaned_data)
            interest_categories_data = json.dumps(interest_categories)
            form_page.merge_fields_mapping = merge_fields_data
            form_page.interest_categories = interest_categories_data
            form_page.save()

            return HttpResponseRedirect(explore_url)
        else:
            context.update({"form": form})
            return render(request, template_name, context=context)

    initial_data = None
    if form_page.merge_fields_mapping:
        try:
            initial_data = json.loads(form_page.merge_fields_mapping)
        except Exception:
            pass

    form = MailchimpIntegrationForm(merge_fields=merge_fields, form_fields=form_fields, initial=initial_data)
    context.update({"form": form})

    return render(request, template_name, context=context)
