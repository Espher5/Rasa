from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.forms import FormAction

import requests

ENDPOINTS = {
    'base': 'https://data.medicare.gov/resource/{}.json',
    'xubh-q36u': {
        'city_query': '?city={}',
        'zip_code_query': '?zip_code={}',
        'id_query': '?provider_id={}'
    },
    'b27b-2uc7': {
        'city_query': '?provider_city={}',
        'zip_code_query': '?provider_zip_code={}',
        'id_query': '?federal_provider_number={}'
    },
    '9wzi-peqs': {
        'city_query': '?city={}',
        'zip_code_query': '?zip={}',
        'id_query': '?provider_number={}'
    }
}


FACILITY_TYPES = {
    'hospital':
        {
            'name': 'hospital',
            'resource': 'xubh-q36u'
        },
    'nursing_home':
        {
            'name': 'nursing home',
            'resource': 'b27b-2uc7'
        },
    'home_health':
        {
            'name': 'home health agency',
            'resource': '9wzi-peqs'
        }
}


def _create_path(base: Text, resource: Text,
                 query: Text, values: Text) -> Text:
    """Creates a path to find provider using the endpoints."""

    if isinstance(values, list):
        return (base + query).format(
            resource, ', '.join('"{0}"'.format(w) for w in values))
    else:
        return (base + query).format(resource, values)


def _find_facilities(location: Text, resource: Text) -> List[Dict]:
    """Returns json of facilities matching the search criteria."""

    if str.isdigit(location):
        full_path = _create_path(ENDPOINTS["base"], resource,
                                 ENDPOINTS[resource]["zip_code_query"],
                                 location)
    else:
        full_path = _create_path(ENDPOINTS["base"], resource,
                                 ENDPOINTS[resource]["city_query"],
                                 location.upper())

    results = requests.get(full_path).json()
    return results


def _resolve_name(facility_types, resource) ->Text:
    for key, value in facility_types.items():
        if value.get("resource") == resource:
            return value.get("name")
    return ""



class ActionHelloWorld(Action):
    def name(self) -> Text:
        return 'action_hello_world'

    def run(self, dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text='Hello World!')
        return []


class ActionFacilitySearch(Action):
    def name(self) -> Text:
        return 'action_facility_search'

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

            facility = tracker.get_slot('facility_type')
            address = '300 Hyde St, San Francisco'
            dispatcher.utter_message('Here is the address of the {}:{}'.format(facility, address))
            return [SlotSet('address', address)]


class FacilityForm(FormAction):
    def name(self) -> Text:
        return 'facility_form'

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        return ['facility_type', 'location']

    def slot_mappings(self) -> Dict[Text, Any]:
        return {'facility_type': self.from_entity(entity='facility_type', intent= ['inform', 'search_provider']),
                'location': self.from_entity(entity='location', intent=['inform', 'search_provider'])}

    def submit(self,
               dispatcher: CollectingDispatcher,
               tracker: Tracker,
               domaon: Dict[Text, Any]
               ) -> List[Dict]:
        
        location = tracker.get_slot('location')
        facility_type = tracker.get_slot('facility_type')

        results = _find_facilities(location, facility_type)
        button_name = _resolve_name(FACILITY_TYPES, facility_type)
        if len(results) == 0:
            dispatcher.utter_message('Sorry, we could not find a {} in {}'.format(button_name, location.title()))
            return []

        buttons = []
        for r in results[:3]:
            if facility_type == FACILITY_TYPES['hospital']['resource']:
                facility_id = r.get('provider_id')
                name = r['hospital_name']
            elif facility_type == FACILITY_TYPES['nursing_home']['resource']:
                facility_id = r['federal_provider_number']
                name = r['provider_name']
            else:
                facility_id = r['provider_number']
                name = r['provider_name']
        
            payload = '/inform{\'facility_id\':\'' + facility_id + '\'}'
            buttons.append(
                {'title': '{}'.format(name.title()), 'payload': payload})

        if len(buttons) == 1:
            message = 'Here is a {} near you:'.format(button_name)
        else:
            if button_name == 'home health agency':
                button_name = 'home health agencie'
            message = 'Here are {} {}s near you:'.format(len(buttons), button_name)

        dispatcher.utter_button_message(message, buttons)
        return []