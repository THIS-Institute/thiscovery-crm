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
import local.dev_config  # sets env variable 'TEST_ON_AWS'
import local.secrets  # sets AWS profile as env variable
import json
import os
import unittest
import requests

from src.common.constants import STACK_NAME
from thiscovery_lib.lambda_utilities import Lambda


class MiscTestCase(unittest.TestCase):

    @unittest.skipUnless(os.environ['TEST_ON_AWS'] == 'True', 'Invokes lambda on AWS')
    def test_01_raise_error(self):
        lambda_client = Lambda(stack_name=STACK_NAME)
        response = lambda_client.invoke(
            function_name='RaiseError',
            payload={
                'queryStringParameters': {
                    'error_id': '4xx',
                }
            }
        )
        from pprint import pprint
        pprint(response)
        self.assertIn('FunctionError', response.keys())
        self.assertEqual('ObjectDoesNotExistError', response['Payload']['errorType'])

    def test_02_call_ping_endpoint_of_core_api(self):
        """
        This is an example of a call to the ping endpoint of the thiscovery core API.
        It is not really a test.
        """
        full_url = os.environ['AWS_TEST_API'] + 'v1/ping'
        response = requests.request(
            method='get',
            url=full_url,
        )
        if response.ok:
            print(response.json())
