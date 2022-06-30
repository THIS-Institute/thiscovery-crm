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
import thiscovery_lib.utilities as utils
from http import HTTPStatus
from thiscovery_lib.eb_utilities import ThiscoveryEvent


@utils.lambda_wrapper
def custom_email(event, context):
    """
    Handles custom email events posted by Qualtrics
    """
    detail = event['detail']
    try:
        template_name = detail.pop('template_name')
    except KeyError as err:
        raise utils.DetailedValueError(f"Missing mandatory data {err} in source event detail", details=event)

    try:
        email_dict = {
            'to_recipient_id': detail.pop('anon_project_specific_user_id')
        }
    except KeyError:
        try:
            email_dict = {
                'to_recipient_email': detail.pop('to_recipient_email')
            }
        except KeyError:
            raise utils.DetailedValueError(
                f"Either to_recipient_id or to_recipient_email must be present "
                f"in source event detail; none found", details=event
            )

    email_dict.update({
        "template_name": template_name,
        "custom_properties": detail,
    })
    email_event = ThiscoveryEvent(
        {
            "detail-type": "transactional_email",
            "detail": email_dict,
        }
    )
    email_event.put_event()
    return {
        "statusCode": HTTPStatus.NO_CONTENT,
    }
