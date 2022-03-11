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
import json
from http import HTTPStatus
import thiscovery_lib.utilities as utils

from thiscovery_lib.notification_send import (
    notify_new_user_registration,
)

import common


@utils.lambda_wrapper
def record_user_registration_event(event, context):
    user_data = event["details"]["detail"]["data"]["details"]["body"]["user_metadata"]

    details = {
        "email": event["user_name"],
        "created": event["created"],
        "first_name": user_data["first_name"],
        "last_name": user_data["last_name"],
        "country_name": user_data["country"],
        "id": user_data["citsci_uuid"],
    }

    notify_new_user_registration(
        details, event["id"], stack_name=common.constants.STACK_NAME
    )

    return {"statusCode": HTTPStatus.OK, "body": json.dumps("")}
