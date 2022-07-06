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

from thiscovery_dev_tools import testing_tools as test_tools
from thiscovery_dev_tools.test_data.auth0_events import SUCCESSFUL_LOGIN
from thiscovery_lib.lambda_utilities import Lambda

import src.common.constants as const
import src.notification_process as notif
import src.user_login as ul
import tests.testing_utilities as test_utils


# region test users
TEST_USER_01_JSON = {
    "id": "d1070e81-557e-40eb-a7ba-b951ddb7ebdc",
    "email": "altha@email.co.uk",
    "first_name": "Altha",
    "last_name": "Alcorn",
    "country_code": "GB",
}
# endregion


class TestUserEvents(test_tools.BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        notif.delete_all_notifications(stack_name=const.STACK_NAME)

    def test_record_user_login_ok(self):
        user_json = TEST_USER_01_JSON
        if test_tools.tests_running_on_aws():
            lambda_client = Lambda(stack_name=const.STACK_NAME)
            lambda_client.invoke(
                function_name="RecordUserLogin",
                payload=SUCCESSFUL_LOGIN,
            )
        else:
            ul.record_user_login_event(SUCCESSFUL_LOGIN, None)
        notification = test_utils.get_expected_user_login_notification(TEST_USER_01_JSON["id"])
        self.assertEqual("user-login", notification["type"])
        self.assertEqual(user_json["email"], notification["label"])
        self.assertEqual(
            notif.NotificationStatus.NEW.value,
            notification[notif.NotificationAttributes.STATUS.value],
        )
        self.assertEqual(user_json["email"], notification["details"]["email"])
        self.assertEqual(user_json["id"], notification["details"]["id"])
        self.now_datetime_test_and_remove(notification, "created", tolerance=10)
