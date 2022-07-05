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
from thiscovery_lib.core_api_utilities import CoreApiClient

import common.constants as const
import notification_send as notif_send


@utils.lambda_wrapper
def record_user_login_event(event, context):
    namespace = utils.get_aws_namespace()
    logger = event["logger"]
    logger.info("API call", extra={"namespace": namespace, "event": event})

    # # Note that Auth0 event log sources are either prod or staging. If this code is being invoked in other environments then
    # # it is because events are being forwarded for dev/test purposes.  In this scenario the user referred to in the event will
    # # not exist in this environment's RDS database or HubSpot database.  So ignore.
    # if namespace in ['/prod/', '/staging/']:

    # event will contain an Auth0 event of type 's''
    event_id = event[
        "id"
    ]  # note that event id will be used as correlation id for subsequent processing
    detail_data = event["detail"]["data"]
    event_type = detail_data["type"]
    login_datetime = detail_data["date"].replace("T", " ").replace("Z", "")
    user_email = detail_data["user_name"]
    core_api_client = CoreApiClient(correlation_id=event_id)
    user = core_api_client.get_user_by_email(email=user_email)
    for x in ["has_demo_project", "has_live_project", "title"]:
        del user[x]
    login_info = {
        **user,
        "login_datetime": login_datetime,
    }
    notif_send.notify_user_login(
        login_info,
        event_id,
        stack_name=const.STACK_NAME,
    )
    return {"statusCode": HTTPStatus.OK, "body": json.dumps("")}
