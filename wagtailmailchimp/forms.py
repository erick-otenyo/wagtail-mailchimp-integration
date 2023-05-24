from collections import OrderedDict

from django import forms
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from wagtailmailchimp.widgets import CustomSelect


class MailChimpForm(forms.Form):
    required_css_class = 'required'

    """
    MailChimp list-based form class.
    """

    def __init__(self, merge_fields, interest_categories=None, *args, **kwargs):
        """
        Initailizes the form instance, adding fields for specified
        MailChimp merge fields and interest categories.

        :param merge_fields: list of merge variable dictionaries.
        :param interest_categories: list of grouping dictionaries.
        """
        # Initialize the form instance.
        super(MailChimpForm, self).__init__(*args, **kwargs)

        # append compulsory email field
        merge_fields.insert(0, ({
            "tag": "EMAIL",
            "name": "Email Address",
            "help_text": "Your Email Address",
            "type": "email",
            "required": "true",
            "options": {"size": 100}
        }))

        # Add merge variable fields.
        for merge_field in merge_fields:
            for data in self.mailchimp_field_factory(merge_field).items():
                name, field = data
                self.fields.update({name: field})

        if interest_categories is not None:
            # Add grouping fields.
            for interest_category in interest_categories:
                name = "INTERESTS"
                field = self.mailchimp_interest_category_factory(interest_category)

                self.fields.update({name: field})

    def mailchimp_field_factory(self, merge_field):
        """
        Returns a form field instance for specified MailChimp merge Field.

        :param merge_field: merge field dictionary.
        :rtype: django.forms.Field.
        """
        fields = OrderedDict()
        mc_type = merge_field.get('type', None)
        name = merge_field.get('tag', '')
        visible = merge_field.get('public', True)
        mc_options = merge_field.get('options', {})
        kwargs = {
            'label': merge_field.get('name', None),
            'required': merge_field.get('required', True),
            'initial': merge_field.get('default_value', None),
            'help_text': merge_field.get('help_text', None)
        }

        if not visible:
            kwargs.update({'widget': forms.HiddenInput})
            fields.update({name: forms.CharField(**kwargs)})
            return fields

        if mc_type == 'email':
            kwargs.update({'max_length': mc_options.get('size', None)})
            fields.update({name: forms.EmailField(**kwargs)})

        if mc_type == 'text':
            kwargs.update({'max_length': mc_options.get('size', None)})
            fields.update({name: forms.CharField(**kwargs)})

        if mc_type == 'number':
            fields.update({name: forms.IntegerField(**kwargs)})

        if mc_type == 'radio':
            kwargs.update({
                'choices': ((x, x) for x in mc_options.get('choices', [])),
                'widget': forms.RadioSelect
            })
            fields.update({name: forms.ChoiceField(**kwargs)})

        if mc_type == 'dropdown':
            kwargs.update({
                'choices': ((x, x) for x in mc_options.get('choices', []))
            })
            fields.update({name: forms.ChoiceField(**kwargs)})

        if mc_type == 'date' or mc_type == 'birthday':
            fields.update({name: forms.DateField(**kwargs)})

        if mc_type == 'address':
            # Define keyword agruments for each charfield component.
            char_fields = [
                {
                    'name': '{0}[addr1]'.format(name),
                    'label': "Street Address",
                    'required': True,
                    'max_length': 70,
                    "placeholder": "Street Address"
                },
                {
                    'name': '{0}[addr2]'.format(name),
                    'label': "Address Line 2",
                    'required': True,
                    'max_length': 70,
                    "placeholder": "Address Line 2"
                },
                {
                    'name': '{0}[city]'.format(name),
                    'label': "City",
                    'required': True,
                    'max_length': 40,
                    'placeholder': "City"
                },
                {
                    'name': '{0}[state]'.format(name),
                    'label': "State/Province/Region",
                    'required': True,
                    'max_length': 20,
                    'placeholder': "State/Province/Region"

                },
                {
                    'name': '{0}[zip]'.format(name),
                    'label': 'Postal/Zip',
                    'required': True,
                    'max_length': 10,
                    'placeholder': "Postal/Zip"
                },
            ]

            # Add the address charfields.
            for kwargs in char_fields:
                field_name = kwargs.pop('name')
                placeholder = kwargs.pop('placeholder', None)

                if placeholder:
                    kwargs.update({'widget': forms.TextInput(attrs={'placeholder': placeholder})})

                fields.update({field_name: forms.CharField(**kwargs)})

            # Finally, add the address country field.
            name = '{0}-country'.format(name)
            fields.update({
                name: CountryField(label=_('Country'))
            })

        if mc_type == 'zip':
            kwargs.update({'max_length': mc_options.get('size', None)})
            fields.update({name: forms.CharField(**kwargs)})

        if mc_type == 'phone':
            kwargs.update({'max_length': mc_options.get('size', None)})
            fields.update({name: forms.CharField(**kwargs)})

        if mc_type == 'url' or mc_type == 'imageurl':
            kwargs.update({'max_length': mc_options.get('size', None)})
            fields.update({name: forms.URLField(**kwargs)})

        return fields

    def mailchimp_interest_category_factory(self, interest_category):

        """
        Returns form field instance for specified MailChimp grouping.

        :param interest_category: interest_category dictionary.
        :param selected_interests: selected_interests list.
        :rtype: django.forms.Field.
        """

        field_type = interest_category.get('type', None)
        title = interest_category.get('title', None)

        interests = interest_category.get('interests', [])
        choices = ((x['id'], x['name']) for x in interests)
        kwargs = {'label': title, 'choices': choices, 'required': False}

        if field_type == 'checkboxes':
            kwargs.update({'widget': forms.CheckboxSelectMultiple})
            return forms.MultipleChoiceField(**kwargs)

        if field_type == 'radio':
            kwargs.update({'widget': forms.RadioSelect})
            return forms.ChoiceField(**kwargs)

        if field_type == 'dropdown':
            kwargs.update({'widget': forms.Select})
            return forms.ChoiceField(**kwargs)

        if field_type == 'hidden':
            kwargs.update({'widget': forms.HiddenInput})
            return forms.ChoiceField(**kwargs)


class MailchimpIntegrationForm(forms.Form):
    def __init__(self, merge_fields=None, form_fields=None, *args, **kwargs):
        # Initialize the form instance.
        super(MailchimpIntegrationForm, self).__init__(*args, **kwargs)

        if merge_fields and form_fields:
            merge_fields.insert(0, ({
                "tag": "EMAIL",
                "name": "Email Address",
                "type": "email",
                "required": "true",
            }))

            for field in merge_fields:
                choices = [("", "-- Select field to merge--")]

                if field.get("type") == "email":
                    for form_field in form_fields:
                        if form_field.field_type == 'email':
                            choices.append((form_field.clean_name, form_field.label))
                elif field.get("type") == "number":
                    for form_field in form_fields:
                        if form_field.field_type == 'number':
                            choices.append((form_field.clean_name, form_field.label))
                elif field.get("type") == "url":
                    for form_field in form_fields:
                        if form_field.field_type == 'url':
                            choices.append((form_field.clean_name, form_field.label))
                elif field.get("type") == "radio":
                    for form_field in form_fields:
                        if form_field.field_type == 'radio':
                            choices.append((form_field.clean_name, form_field.label))
                elif field.get("type") == "dropdown":
                    for form_field in form_fields:
                        if form_field.field_type == 'dropdown':
                            choices.append((form_field.clean_name, form_field.label))
                elif field.get("type") == "checkboxes":
                    for form_field in form_fields:
                        if form_field.field_type == 'checkboxes':
                            choices.append((form_field.clean_name, form_field.label))
                elif field.get("type") == "date" or field.get("type") == "birthday":
                    for form_field in form_fields:
                        if form_field.field_type == 'date':
                            choices.append((form_field.clean_name, form_field.label))
                else:
                    for form_field in form_fields:
                        if form_field.field_type == 'singleline' or form_field.field_type == "multiline":
                            choices.append((form_field.clean_name, form_field.label))

                kwargs = {
                    'label': field.get('name', None),
                    'required': field.get('required', True)
                }

                name = field.get("tag")

                self.fields.update({name: forms.ChoiceField(choices=choices, widget=CustomSelect, **kwargs)})
                self.fields[name].label = field.get("name")
