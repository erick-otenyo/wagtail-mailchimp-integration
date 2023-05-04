from django.conf import settings
from mailchimp3 import MailChimp
from site_settings.models import IntegrationSettings
from wagtail.models import Site


class MailchimpApi:
    def __init__(self):
        self.client = None
        self.is_active = False

        self.init_api()

    def init_api(self):
        try:
            # Get the current site
            current_site = Site.objects.get(is_default_site=True)

            # Get the SiteSettings for the current site
            settings = IntegrationSettings.for_site(current_site)
            api_key = settings.mailchimp_api

            self.client = MailChimp(mc_api=api_key)
            self.is_active = True
        except Exception as e:
            print("EXCEPTION", e)
            return None

    def get_lists(self, fields='lists.id,lists.name'):
        try:
            result = self.client.lists.all(fields=fields, get_all=True)
            return result['lists']
        except:
            return []

    def get_merge_fields_for_list(self, list_id,
                                  fields="merge_fields.merge_id,"
                                         "merge_fields.tag,"
                                         "merge_fields.name,"
                                         "merge_fields.type,"
                                         "merge_fields.required,"
                                         "merge_fields.public,"
                                         "merge_fields.display_order,"
                                         "merge_fields.options,"
                                         "merge_fields.help_text",
                                  ):
        try:
            result = self.client.lists.merge_fields.all(list_id=list_id, get_all=True, fields=fields)
            return result['merge_fields']
        
        except:
            return []

    def get_interest_categories_for_list(self, list_id,
                                         fields="categories.id,"
                                                "categories.title,"
                                                "categories.type,"
                                                "categories.display_order"):
        try:
            result = self.client.lists.interest_categories.all(list_id=list_id, get_all=True, fields=fields)
            return result['categories']
        except:
            return []

    def get_interests_for_interest_category(self, list_id, interest_category_id,
                                            fields="interests.id,"
                                                   "interests.name,"
                                                   "interests.display_order"):
        try:
            result = self.client.lists.interest_categories.interests.all(list_id=list_id,
                                                                         category_id=interest_category_id,
                                                                         get_all=True,
                                                                         fields=fields)
            return result['interests']
        except:
            return []

    def add_user_to_list(self, list_id, data):
        return self.client.lists.members.create(list_id=list_id, data=data)