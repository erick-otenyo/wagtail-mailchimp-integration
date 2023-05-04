from datetime import date

from django.contrib import messages
from django.core.mail import mail_admins
from django.forms.forms import NON_FIELD_ERRORS
from django.http import Http404
from django.shortcuts import render
from django.views.generic import FormView
from mailchimp3.mailchimpclient import MailChimpError

from .api import MailchimpApi
from .forms import MailChimpForm 
from .models import MailChimpApiContact

api = MailchimpApi()


class MailChimpView(FormView):
    """
    Displays and processes a form based on a MailChimp list.
    """
    form_class = MailChimpForm
    page_instance = None
    merge_fields = None
    interest_categories = None

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

        if self.interest_categories is None and api.is_active:
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
        if self.merge_fields is None and api.is_active:
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

        # Must have an email address.
        if api.is_active and 'EMAIL' in clean_merge_fields:
            data = {
                'email_address': clean_merge_fields.pop('EMAIL'),
                'merge_fields': clean_merge_fields,
                'status': status,
            }

            if interests_payload:
                data['interests'] = interests_payload

            context = {'page': self.page_instance, 'self': self.page_instance}

            try:
                list_id = self.page_instance.list_id
                api.add_user_to_list(list_id=list_id, data=data)
                MailChimpApiContact.objects.create(source=self.page_instance.title, email=data['email_address'],
                                                   list_id=list_id)
            except MailChimpError as e:
                error_traceback = e
                if e.args and e.args[0]:
                    error = e.args[0]
                    if error['title']:
                        if error['title'] == "Member Exists":
                            messages.add_message(self.request, messages.INFO,
                                                 "You are already subscribed to our mailing list. Thank you!")
                            context.update({'hide_thank_you_text': True})
                            return render(self.request, 'form_thank_you_landing.html', context=context)
            except Exception as e:
                error_traceback = e
        else:
            if not api.is_active:
                error_traceback = "MAILCHIMP API not active"
            else:
                error_traceback = "No email in fields"

        if error_traceback:
            mail_admins("Error adding user to mailing list", str(error_traceback), fail_silently=True)

            form.errors[NON_FIELD_ERRORS] = form.error_class(
                ["We are having issues adding you to our mailing list. Please try later"]
            )
            return super(MailChimpView, self).form_invalid(form)

        # added user to mailing list successfully
        return render(self.request, 'form_thank_you_landing.html',
                      context={'page': self.page_instance, 'self': self.page_instance})