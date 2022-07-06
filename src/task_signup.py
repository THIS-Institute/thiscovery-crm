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
from http import HTTPStatus
import thiscovery_lib.utilities as utils

from notification_send import notify_new_task_signup


@utils.lambda_wrapper
@utils.api_error_handler
def record_task_signup_event(event, context):
    """
    Processes task_signup events posted by create_user_task in thiscovery-core
    """
    correlation_id = event["id"]
    new_user_task = event["detail"]
    notify_new_task_signup(new_user_task, correlation_id)
    return {
        "statusCode": HTTPStatus.NO_CONTENT,
    }
