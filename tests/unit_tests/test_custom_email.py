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

import thiscovery_dev_tools.testing_tools as test_tools
from http import HTTPStatus
from pprint import pprint

from custom_email import custom_email
import tests.test_data as td


class CustomEmailTestCase(test_tools.BaseTestCase):
    """
    These tests only test that a notification was created successfully
    in Dynamodb; they don't test processing of notifications
    """
    def test_custom_email_event_handled_ok(self):
        r = custom_email(td.CUSTOM_EMAIL_EB_EVENT, None)
        self.assertEqual(HTTPStatus.NO_CONTENT, r['statusCode'])

    def test_custom_email_event_without_id_handled_ok(self):
        r = custom_email(td.CUSTOM_EMAIL_EB_EVENT_NO_ID, None)
        self.assertEqual(HTTPStatus.NO_CONTENT, r['statusCode'])
