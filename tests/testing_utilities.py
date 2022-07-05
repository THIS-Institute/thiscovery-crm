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
import csv
import os
import thiscovery_lib.utilities as utils
from thiscovery_lib.core_api_utilities import CoreApiClient
from thiscovery_lib.hubspot_utilities import HubSpotClient

from src.notification_process import get_notifications


BASE_FOLDER = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "..", "..", ".."
)  # thiscovery-core/
TEST_DATA_FOLDER = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "..", "test_data"
)


def post_sample_users_to_crm(user_test_data_csv, hs_client=None):
    if hs_client is None:
        hs_client = HubSpotClient()
    with open(user_test_data_csv) as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            user_json = {
                "id": row[0],
                "created": row[1],
                "email": row[3],
                "first_name": row[5],
                "last_name": row[6],
                "country_code": row[9],
                "country_name": utils.get_country_name(row[9]),
                "avatar_string": f"{row[5][0].upper()}{row[6][0].upper()}",
                "status": "new",
            }

            hubspot_id, _ = hs_client.post_new_user_to_crm(user_json)
            user_jsonpatch = [
                {"op": "replace", "path": "/crm_id", "value": str(hubspot_id)},
            ]
            core_client = CoreApiClient()
            core_client.patch_user(
                user_json["id"],
                user_jsonpatch,
            )


def get_expected_notification(expected_id):
    notifications = get_notifications()
    for n in notifications:
        if n["id"] == expected_id:
            return n


def get_expected_user_login_notification(expected_user_id):
    notifications = get_notifications()
    for n in notifications:
        if (n["type"] == "user-login") and (n["details"]["id"] == expected_user_id):
            return n
