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
import thiscovery_dev_tools.testing_tools as test_tools
from http import HTTPStatus
from thiscovery_lib.core_api_utilities import CoreApiClient
from thiscovery_lib.hubspot_utilities import HubSpotClient, TASK_SIGNUP_TLE_TYPE_NAME

import src.common.constants as const
import tests.testing_utilities as test_utils
from notification_process import (
    delete_all_notifications,
    NotificationStatus,
    NotificationAttributes,
    process_notifications,
)
from src.task_signup import record_task_signup_event


test_user_task_dict = {
    "id": "9620089b-e9a4-46fd-bb78-091c8449d777",
    "created": "2018-06-13 14:15:16.171819+00",
    "modified": "2018-06-13 14:15:16.171819+00",
    "user_id": "dceac123-03a7-4e29-ab5a-739e347b374d",
    "user_project_id": "0fdacd2a-6276-485a-aca5-f276dde742e8",
    "project_task_id": "6cf2f34e-e73f-40b1-99a1-d06c1f24381a",
    "task_provider_name": "Cochrane",
    "url": "http://crowd.cochrane.org/index.html?first_name=Steven&user_id=48e30e54-b4fc-4303-963f-2943dda2b139&user_task_id=9620089b-e9a4-46fd-bb78-091c8449d777&external_task_id=ext-5a&env=test-afs25",
    "status": "active",
    "consented": "2018-06-12 16:16:56.087895+01",
    "anon_user_task_id": "78a1ccd7-dee5-49b2-ad5c-8bf4afb3cf93",
    "extra_data": {
        "project_id": "5907275b-6d75-4ec0-ada8-5854b44fb955",
        "project_name": "PSFU-05-pub-act",
        "task_id": "6cf2f34e-e73f-40b1-99a1-d06c1f24381a",
        "task_name": "PSFU-05-A",
        "task_type_id": "a5537c85-7d29-4500-9986-ddc18b27d46f",
        "task_type_name": "Photo upload",
        "crm_id": "74701",
    },
}

test_task_signup_event = {
    "detail-type": "task_signup",
    "time": "2021-07-08T21:20:43Z",
    "version": "0",
    "resources": [],
    "detail": test_user_task_dict,
    "account": "REDACTED",
    "source": "thiscovery",
    "region": "REDACTED",
    "id": "4b37abb5-ebe9-78f1-74c6-d93176514ac9",
}


class TestTaskSignup(test_tools.BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delete_all_notifications(stack_name=const.STACK_NAME)

    def test_01_record_task_signup_event_ok(self):
        ut_id = test_user_task_dict["id"]
        result = test_tools.test_eb_request_v2(
            local_method=record_task_signup_event,
            aws_eb_event=test_task_signup_event,
            lambda_name="RecordTaskSignup",
            aws_processing_delay=5,
            stack_name=const.STACK_NAME,
        )
        self.assertEqual(HTTPStatus.NO_CONTENT, result["statusCode"])
        notification = test_utils.get_expected_notification(ut_id)
        self.assertIsNotNone(notification)

        # process notification
        process_notifications(dict(), None)

        # check user now has sign-up timeline event
        hs_client = HubSpotClient(stack_name=const.STACK_NAME)
        tle_type_id = hs_client.get_timeline_event_type_id(
            TASK_SIGNUP_TLE_TYPE_NAME, correlation_id=None
        )
        result = hs_client.get_timeline_event(tle_type_id, ut_id)
        self.assertEqual(ut_id, result["id"])
        notification_details = notification["details"]
        self.assertEqual(notification_details["project_task_id"], result["task_id"])
        self.assertEqual("CONTACT", result["objectType"])
        self.assertEqual("PSFU-05-pub-act", result["project_name"])

        # check that notification message has been processed
        notification = test_utils.get_expected_notification(ut_id)
        self.assertEqual(
            NotificationStatus.PROCESSED.value,
            notification[NotificationAttributes.STATUS.value],
        )

    def test_record_task_signup_event_no_crm_id(self):
        # setup real crm id in core's rds db
        hs_client = HubSpotClient(stack_name=const.STACK_NAME)
        response = hs_client.get_hubspot_contact_by_email("fred@email.co.uk")
        test_user_crm_id = str(response["canonical-vid"])
        user_jsonpatch = [
            {"op": "replace", "path": "/crm_id", "value": str(test_user_crm_id)},
        ]
        core_client = CoreApiClient()
        core_client.patch_user("dceac123-03a7-4e29-ab5a-739e347b374d", user_jsonpatch)

        # create notification from event where crm_id is null (simulating registration not processed yet)
        ut_id = "e7c7fcf8-023b-46ed-9e20-2d917cb86959"
        test_event = copy.deepcopy(test_task_signup_event)
        test_event["detail"]["extra_data"]["crm_id"] = None
        test_event["detail"]["id"] = ut_id
        result = test_tools.test_eb_request_v2(
            local_method=record_task_signup_event,
            aws_eb_event=test_event,
            lambda_name="RecordTaskSignup",
            aws_processing_delay=5,
            stack_name=const.STACK_NAME,
        )
        self.assertEqual(HTTPStatus.NO_CONTENT, result["statusCode"])
        notification = test_utils.get_expected_notification(ut_id)
        self.assertIsNotNone(notification)

        # process notification
        process_notifications(dict(), None)

        # check user now has sign-up timeline event
        hs_client = HubSpotClient(stack_name=const.STACK_NAME)
        tle_type_id = hs_client.get_timeline_event_type_id(
            TASK_SIGNUP_TLE_TYPE_NAME, correlation_id=None
        )
        result = hs_client.get_timeline_event(tle_type_id, ut_id)
        self.assertEqual(ut_id, result["id"])
        notification_details = notification["details"]
        self.assertEqual(notification_details["project_task_id"], result["task_id"])
        self.assertEqual("CONTACT", result["objectType"])
        self.assertEqual("PSFU-05-pub-act", result["project_name"])

        # check that notification message has been processed
        notification = test_utils.get_expected_notification(ut_id)
        self.assertEqual(
            NotificationStatus.PROCESSED.value,
            notification[NotificationAttributes.STATUS.value],
        )
