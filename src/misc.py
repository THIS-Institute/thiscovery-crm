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
import time
from http import HTTPStatus
import thiscovery_lib.utilities as utils


@utils.lambda_wrapper
def raise_error(event, context):
    logger = event['logger']
    correlation_id = event['correlation_id']

    params = event['queryStringParameters']
    error_id = params['error_id']
    logger.info('Event info', extra={'error_id': error_id, 'correlation_id': correlation_id, 'event': event})

    errorjson = {'error_id': error_id, 'correlation_id': str(correlation_id)}
    msg = 'no error'

    if error_id == '4xx':
        msg = 'error triggered for testing purposes'
        raise utils.ObjectDoesNotExistError(msg, errorjson)
    elif error_id == '5xx':
        msg = 'error triggered for testing purposes'
        raise Exception(msg)
    elif error_id == 'slow':
        msg = 'slow response triggered for testing purposes'
        time.sleep(2)  # this should trigger lambda duration alarm
    elif error_id == 'timeout':
        msg = 'timeout response triggered for testing purposes'
        time.sleep(10)  # this should trigger lambda timeout

    return {
        "statusCode": HTTPStatus.OK,
        "body": json.dumps(msg)
    }
