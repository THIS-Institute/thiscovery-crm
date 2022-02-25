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
import local.dev_config
import local.secrets
import thiscovery_lib.notifications as notif
import thiscovery_lib.utilities as utils
from thiscovery_dev_tools import testing_tools as test_tools
from thiscovery_dev_tools.test_data.auth0_events import SUCCESSFUL_REGISTRATION
from thiscovery_lib.lambda_utilities import Lambda

import src.common.constants as const
import src.user_registration as ur

from tests.unit_tests.test_user_login import TEST_USER_01_JSON


class TestUserRegistration(test_tools.BaseTestCase):
    """
    This test checks that lambda function RecordUserRegistration can receive
    a ss Auth0 event as input and save a registration notification to the queue
    of notifications to be processed in the Dynamodb notifications table. If we
    keep the notification structure the same as it is at present in thiscovery-core,
    it will look like this:
    {
        "id": "89ed5ae0-1f37-489f-ba58-16c5ac7bad60",
        "processing_status": "new",
        "label": "altha@email.co.uk",
        "created": "2022-02-25 10:48:31.407821+00:00",
        "details": {
            "created": "2022-02-25 10:48:31.164191+00:00",
            "avatar_string": "AA",
            "last_name": "Alcorn",
            "title": null,
            "country_code": "GB",
            "crm_id": null,
            "country_name": "United Kingdom - England",
            "modified": "2022-02-25 10:48:31.164191+00:00",
            "id": "89ed5ae0-1f37-489f-ba58-16c5ac7bad60",
            "auth0_id": "6218b3ff6a20e40071c72e51",
            "first_name": "Altha",
            "email": "Altha",
            "status": "new"
        },
        "modified": "2022-02-25 10:53:17.312532+00:00",
        "type": "user-registration"
    }

    Note that:
        - this test only checks the notification was added to the processing queue.
            The correct processing of notifications of this type needs to be tested
            separately
        - when this notification is processed, we will receive a crm_id back from
            HubSpot for this user. That needs to be passed back to thiscovery-core
            so that it can be stored in RDS. I suggest doing so via an EventBridge
            event
    """
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        notif.delete_all_notifications(stack_name=const.STACK_NAME)

    def test_record_user_registration_ok(self):
        user_json = TEST_USER_01_JSON
        if utils.running_on_aws():
            lambda_client = Lambda(stack_name=const.STACK_NAME)
            lambda_client.invoke(
                function_name="RecordUserRegistration",
                invocation_type="Event",
                payload=SUCCESSFUL_REGISTRATION,
            )
        else:
            ur.record_user_registration_event(SUCCESSFUL_REGISTRATION, None)
        notifications = notif.get_notifications(stack_name=const.STACK_NAME)
        self.assertEqual(1, len(notifications))

        notification = notifications[0]
        self.assertEqual("user-registration", notification["type"])
        self.assertEqual(user_json["email"], notification["label"])
        self.assertEqual(
            notif.NotificationStatus.NEW.value,
            notification[notif.NotificationAttributes.STATUS.value],
        )
        self.assertEqual(user_json["email"], notification["details"]["email"])
        self.assertEqual(user_json["id"], notification["details"]["id"])
        self.now_datetime_test_and_remove(notification, "created", tolerance=10)
