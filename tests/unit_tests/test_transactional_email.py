#
#   Thiscovery API - THIS Institute’s citizen science platform
#   Copyright (C) 2019 THIS Institute
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   A copy of the GNU Affero General Public License is available in the
#   docs folder of this project.  It is also available www.gnu.org/licenses/
#
try:
    import local.dev_config  # sets env variable 'TEST_ON_AWS'
    import local.secrets  # sets AWS profile as env variable
except ModuleNotFoundError:
    pass

import copy
import json
import random
import string


from http import HTTPStatus
from pprint import pprint

import thiscovery_dev_tools.testing_tools as test_tools
import thiscovery_lib.utilities as utils
from thiscovery_lib.core_api_utilities import CoreApiClient

import src.common.constants as const
from src.transactional_email import (
    TransactionalEmail,
    send_transactional_email,
)



test_email_dict = {
    "template_name": "unittests_email_template_1",
    "to_recipient_id": "d1070e81-557e-40eb-a7ba-b951ddb7ebdc",
    "custom_properties": {
        "project_task_description": "Systematic review for CTG monitoring",
        "project_task_name": "CTG Monitoring",
        "project_results_url": "https://www.thiscovery.org/",
    },
}

test_transactional_email_event = {
    "detail-type": "transactional_email",
    "time": "2021-07-08T21:20:43Z",
    "version": "0",
    "resources": [],
    "detail": test_email_dict,
    "account": "REDACTED",
    "source": "thiscovery",
    "region": "REDACTED",
    "id": "4b37abb5-ebe9-78f1-74c6-d93176514ac9",
}


# this is a copy of EXPECTED_USER in thiscovery-core.api.tests.test_scripts.unit_tests.test_user
# Consider adding to test data in thiscovery-dev-tools and importing in both stacks to
# avoid repetition
expected_user = {
    "id": "d1070e81-557e-40eb-a7ba-b951ddb7ebdc",
    "created": f"2018-08-17T12:10:56.798192+00:00",
    "modified": f"2018-08-17T12:10:56.833885+00:00",
    "email": "altha@email.co.uk",
    "title": "Mrs",
    "first_name": "Altha",
    "last_name": "Alcorn",
    "country_code": "GB",
    "country_name": "United Kingdom",
    "auth0_id": None,
    "crm_id": None,
    "status": None,
    "has_demo_project": True,
    "has_live_project": False,
    "avatar_string": "AA",
}


class TestTransactionalEmail(test_tools.BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.email = TransactionalEmail(
            email_dict=test_email_dict, send_id=utils.new_correlation_id()
        )
        cls.core_client = CoreApiClient()

    def test_01_get_template_details_ok(self):
        template = self.email._get_template_details()
        expected_template = {
            "bcc": ["thiscovery_dev@email.com"],
            "cc": ["this_researcher@email.com"],
            "contact_properties": [],
            "custom_properties": [
                {"name": "project_task_name", "required": True},
                {"name": "project_task_description", "required": True},
                {"name": "project_results_url", "required": False},
            ],
            "from": "Sender Name <sender@hubspot.com>",
            "hs_template_id": "33531457008",
            "id": "unittests_email_template_1",
        }
        self.assertDictEqual(expected_template, template)

    def test_02_get_template_details_not_found(self):
        email_dict = copy.deepcopy(test_email_dict)
        email_dict["template_name"] = "non_existent_email_template"
        email = TransactionalEmail(
            email_dict=email_dict, send_id=utils.new_correlation_id()
        )
        with self.assertRaises(utils.ObjectDoesNotExistError) as context:
            email._get_template_details()
        err = context.exception
        err_msg = err.args[0]
        self.assertIn("Template not found", err_msg)

    def test_03_validate_properties_ok(self):
        self.assertTrue(self.email._validate_properties())

    def test_04_validate_properties_missing_required_property(self):
        email_dict = copy.deepcopy(test_email_dict)
        del email_dict["custom_properties"]["project_task_description"]
        email = TransactionalEmail(
            email_dict=email_dict, send_id=utils.new_correlation_id()
        )
        with self.assertRaises(utils.DetailedValueError) as context:
            email._validate_properties()
        err = context.exception
        err_msg = err.args[0]
        self.assertIn(
            "Required custom property project_task_description not found in call body",
            err_msg,
        )

    def test_05_validate_properties_non_specified_property(self):
        email_dict = copy.deepcopy(test_email_dict)
        email_dict["custom_properties"][
            "unspecified_property"
        ] = "This property is not defined in the template"
        email = TransactionalEmail(
            email_dict=email_dict, send_id=utils.new_correlation_id()
        )
        self.logger.warning(
            "Email object email_dict", extra={"email_dict": email.email_dict}
        )
        with self.assertRaises(utils.DetailedIntegrityError) as context:
            email._validate_properties()
        err = context.exception
        err_msg = err.args[0]
        self.assertIn(
            "Call custom property unspecified_property is not specified in email template",
            err_msg,
        )

    def test_06_get_user_by_user_id_ok(self):
        self.assertCountEqual(expected_user, self.email._get_user())

    def test_07_get_user_by_anon_project_specific_user_id_ok(self):
        email_dict = copy.deepcopy(test_email_dict)
        email_dict["to_recipient_id"] = "2c8bba57-58a9-4ac7-98e8-beb34f0692c1"
        email = TransactionalEmail(
            email_dict=email_dict, send_id=utils.new_correlation_id()
        )
        self.assertCountEqual(expected_user, email._get_user())

    def test_08_get_user_not_found(self):
        email_dict = copy.deepcopy(test_email_dict)
        email_dict["to_recipient_id"] = "49ad25c2-560f-4ed1-8e6f-46debf1f2445"
        email = TransactionalEmail(
            email_dict=email_dict, send_id=utils.new_correlation_id()
        )
        with self.assertRaises(utils.ObjectDoesNotExistError) as context:
            email._get_user()
        err = context.exception
        err_msg = err.args[0]
        self.assertIn(
            "Recipient id does not match any known user_id or anon_project_specific_user_id",
            err_msg,
        )

    def test_09_format_properties_to_name_value(self):
        expected_result = [
            {
                "name": "project_task_description",
                "value": "Systematic review for CTG monitoring",
            },
            {"name": "project_task_name", "value": "CTG Monitoring"},
            {"name": "project_results_url", "value": "https://www.thiscovery.org/"},
        ]
        self.assertCountEqual(
            expected_result,
            TransactionalEmail._format_properties_to_name_value(
                test_email_dict["custom_properties"]
            ),
        )

    def test_10_send_email_ok(self):
        email_dict = copy.deepcopy(test_email_dict)
        email_dict["to_recipient_id"] = "dceac123-03a7-4e29-ab5a-739e347b374d"
        email = TransactionalEmail(
            email_dict=email_dict, send_id=str(utils.new_correlation_id())
        )
        response = email.send(mock_server=True)
        self.assertEqual(HTTPStatus.OK, response.status_code)

    def test_11_send_email_user_without_hubspot_id(self):
        # generate random email prefix to avoid database validation errors on subsequent runs
        letters = string.ascii_lowercase
        email_prefix = "".join(random.choice(letters) for i in range(10))
        email_address = f"test_send_email_user_without_hubspot_id_{email_prefix}@email.co.uk"
        result = self.core_client.post_user(
            user_dict={
                "email": email_address,
                "title": "Mr",
                "first_name": "Steven",
                "last_name": "Walcorn",
                "auth0_id": "1234abcd",
                "country_code": "IT",
                "status": "new",
            }
        )
        user_id = json.loads(result['body'])["id"]
        email_dict = copy.deepcopy(test_email_dict)
        email_dict["to_recipient_id"] = user_id
        t_email = TransactionalEmail(
            email_dict=email_dict, send_id=utils.new_correlation_id()
        )
        with self.assertRaises(utils.ObjectDoesNotExistError) as context:
            t_email.send()
        err = context.exception
        err_msg = err.args[0]
        self.assertIn("Recipient does not have a HubSpot id", err_msg)

    def test_12_send_transactional_email_api_locally(self):
        test_event = copy.deepcopy(test_transactional_email_event)
        test_event["detail"]["to_recipient_id"] = "dceac123-03a7-4e29-ab5a-739e347b374d"
        test_event["detail"]["mock_server"] = True
        result = test_tools.test_eb_request_v2(
            local_method=send_transactional_email,
            aws_eb_event=test_event,
            lambda_name="SendTransactionalEmail",
            stack_name=const.STACK_NAME,
            aws_processing_delay=15,
        )
        self.assertEqual(HTTPStatus.NO_CONTENT, result["statusCode"])

    def test_13_template_name_missing_from_email_dict(self):
        email_dict = copy.deepcopy(test_email_dict)
        del email_dict["template_name"]
        with self.assertRaises(utils.DetailedValueError) as context:
            TransactionalEmail(
                email_dict=email_dict, send_id=utils.new_correlation_id()
            )
        err = context.exception
        err_msg = err.args[0]
        self.assertIn("template_name must be present in email_dict", err_msg)

    def test_lookup_of_user_attributes_missing_from_email_dict(self):
        email_dict = copy.deepcopy(test_email_dict)
        email_dict["template_name"] = "unittests_email_template_2"
        email_dict["to_recipient_id"] = "dceac123-03a7-4e29-ab5a-739e347b374d"
        email = TransactionalEmail(
            email_dict=email_dict, send_id=str(utils.new_correlation_id())
        )
        response = email.send(mock_server=True)
        self.assertEqual(HTTPStatus.OK, response.status_code)

    def test_lookup_of_project_attributes_missing_from_email_dict(self):
        email_dict = copy.deepcopy(test_email_dict)
        email_dict["template_name"] = "unittests_email_template_3"
        email_dict["to_recipient_id"] = "dceac123-03a7-4e29-ab5a-739e347b374d"
        email_dict["custom_properties"][
            "project_task_id"
        ] = "c92c8289-3590-4a85-b699-98bc8171ccde"
        del email_dict["custom_properties"]["project_task_name"]
        email = TransactionalEmail(
            email_dict=email_dict, send_id=str(utils.new_correlation_id())
        )
        response = email.send(mock_server=True)
        self.assertEqual(HTTPStatus.OK, response.status_code)

    def test_14_recipient_missing_from_email_dict(self):
        email_dict = copy.deepcopy(test_email_dict)
        del email_dict["to_recipient_id"]
        with self.assertRaises(utils.DetailedValueError) as context:
            TransactionalEmail(
                email_dict=email_dict, send_id=utils.new_correlation_id()
            )
        err = context.exception
        err_msg = err.args[0]
        self.assertIn(
            "Either to_recipient_id or to_recipient_email must be present in email_dict",
            err_msg,
        )

    def test_15_send_email_to_email_address_ok(self):
        email_dict = copy.deepcopy(test_email_dict)
        del email_dict["to_recipient_id"]
        email_dict["to_recipient_email"] = "thiscovery_dev@email.com"
        email = TransactionalEmail(
            email_dict=email_dict, send_id=str(utils.new_correlation_id())
        )
        response = email.send(mock_server=True)
        self.assertEqual(HTTPStatus.OK, response.status_code)

    def test_16_send_email_to_invalid_email_address_fails(self):
        email_dict = copy.deepcopy(test_email_dict)
        del email_dict["to_recipient_id"]
        email_dict["to_recipient_email"] = "thiscovery_dev@emailcom"
        email = TransactionalEmail(
            email_dict=email_dict, send_id=utils.new_correlation_id()
        )
        with self.assertRaises(utils.DetailedValueError) as context:
            response = email.send(mock_server=True)
        err = context.exception
        err_msg = err.args[0]
        self.assertIn("to_recipient_email is not a valid email address", err_msg)
