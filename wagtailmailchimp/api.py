from django.core.cache import cache
from mailchimp3 import MailChimp


class MailchimpApi:
    def __init__(self, api_key):
        self.client = MailChimp(mc_api=api_key)

    def get_lists(self, fields='lists.id,lists.name'):
        cache_key = f"get-lists-{fields}"
        lists = cache.get(cache_key)

        if lists is None:
            try:
                result = self.client.lists.all(fields=fields, get_all=True)
                lists = result['lists']
                cache.set(cache_key, lists)
            except:
                return []

        return lists

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
        cache_key = f"get-merge-fields-{list_id}-{fields}"
        merge_fields = cache.get(cache_key)

        if merge_fields is None:
            try:
                result = self.client.lists.merge_fields.all(list_id=list_id, get_all=True, fields=fields)
                merge_fields = result['merge_fields']
                cache.set(cache_key, merge_fields)
            except:
                return []

        return merge_fields

    def get_interest_categories_for_list(self, list_id,
                                         fields="categories.id,"
                                                "categories.title,"
                                                "categories.type,"
                                                "categories.display_order"):
        cache_key = f"get-categories-{list_id}-{fields}"
        categories = cache.get(cache_key)

        if categories is None:
            try:
                result = self.client.lists.interest_categories.all(list_id=list_id, get_all=True, fields=fields)
                categories = result['categories']
                cache.set(cache_key, categories)
            except:
                return []

        return categories

    def get_interests_for_interest_category(self, list_id, interest_category_id,
                                            fields="interests.id,"
                                                   "interests.name,"
                                                   "interests.display_order"):
        cache_key = f"get-interests-{list_id}-{interest_category_id}-{fields}"
        interests = cache.get(cache_key)

        if interests is None:
            try:
                result = self.client.lists.interest_categories.interests.all(list_id=list_id,
                                                                             category_id=interest_category_id,
                                                                             get_all=True,
                                                                             fields=fields)
                interests = result['interests']
                cache.set(cache_key, interests)
            except:
                return []

        return interests

    def get_interests_for_list(self, list_id):
        interest_categories = self.get_interest_categories_for_list(list_id=list_id)

        categories = []

        for category in interest_categories:
            category_id = category.get('id', '')

            interest_category = {
                "id": category_id,
                "title": category.get('title', ''),
                'type': category.get('type', '')
            }

            interests = self.get_interests_for_interest_category(list_id=list_id, interest_category_id=category_id)

            interest_category['interests'] = interests

            categories.append(interest_category)

        return categories

    def add_user_to_list(self, list_id, data):
        return self.client.lists.members.create(list_id=list_id, data=data)

    def ping(self):
        return self.client.ping.get()
