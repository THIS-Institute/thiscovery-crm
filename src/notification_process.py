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

import http
import sys
import json
import traceback
from datetime import datetime, timedelta
from dateutil import parser, tz

import thiscovery_lib.notifications as c_notif
import thiscovery_lib.utilities as utils
from thiscovery_lib.dynamodb_utilities import Dynamodb
from thiscovery_lib.hubspot_utilities import HubSpotClient
from thiscovery_lib.notifications import (
    get_notifications,
    NotificationType,
    NotificationStatus,
    NotificationAttributes,
    mark_notification_processed,
    mark_notification_failure,
)
from thiscovery_lib.utilities import (
    get_logger,
    new_correlation_id,
    now_with_tz,
    DetailedValueError,
)

import common.constants as const


# region processing
def process_notifications(event, context):
    logger = get_logger()
    notifications = c_notif.get_notifications_to_process(stack_name=const.STACK_NAME)
    logger.info("process_notifications", extra={"count": str(len(notifications))})

    # note that we need to process all registrations first, then do task signups (otherwise we might try to process a signup for someone not yet registered)
    signup_notifications = list()
    login_notifications = list()
    transactional_emails = list()
    for notification in notifications:
        notification_type = notification["type"]
        if notification_type == NotificationType.USER_REGISTRATION.value:
            pass
            # process_user_registration(notification)
        elif notification_type == NotificationType.TASK_SIGNUP.value:
            # add to list for later processing
            signup_notifications.append(notification)
        elif notification_type == NotificationType.USER_LOGIN.value:
            # add to list for later processing
            login_notifications.append(notification)
        elif notification_type == NotificationType.TRANSACTIONAL_EMAIL.value:
            transactional_emails.append(notification)
        else:
            error_message = (
                f"Processing of {notification_type} notifications not implemented yet"
            )
            logger.error(error_message)
            raise NotImplementedError(error_message)

    for signup_notification in signup_notifications:
        pass
        # process_task_signup(signup_notification)

    for login_notification in login_notifications:
        process_user_login(login_notification)

    for email in transactional_emails:
        pass
        # process_transactional_email(email)


def process_user_login(notification):
    logger = get_logger()
    correlation_id = new_correlation_id()
    logger.info(
        "Processing user login notification",
        extra={"notification": notification, "correlation_id": correlation_id},
    )
    posting_result = None
    marking_result = None
    try:
        # get basic data out of notification
        login_details = notification["details"]
        hs_client = HubSpotClient(
            correlation_id=correlation_id, stack_name=const.STACK_NAME
        )
        posting_result = hs_client.post_user_login_to_crm(login_details)
        logger.debug(
            "Response from HubSpot API",
            extra={"posting_result": posting_result, "correlation_id": correlation_id},
        )
        if posting_result == http.HTTPStatus.NO_CONTENT:
            marking_result = mark_notification_processed(
                notification, correlation_id, stack_name=const.STACK_NAME
            )
    except Exception as ex:
        logger.debug("Traceback", extra={"traceback": traceback.format_exc()})
        error_message = str(ex)
        marking_result = mark_notification_failure(
            notification, error_message, correlation_id, stack_name=const.STACK_NAME
        )
    finally:
        return posting_result, marking_result


# def process_transactional_email(notification, mock_server=False):
#     logger = get_logger()
#     correlation_id = new_correlation_id()
#     logger.info('Processing transactional email', extra={'notification': notification, 'correlation_id': correlation_id})
#     posting_result = None
#     marking_result = None
#     try:
#         from transactional_email import TransactionalEmail
#         email = TransactionalEmail(
#             email_dict=notification['details'],
#             send_id=notification['id'],
#             correlation_id=correlation_id
#         )
#         posting_result = email.send(mock_server=mock_server)
#         logger.debug('Response from HubSpot API', extra={'posting_result': posting_result, 'correlation_id': correlation_id})
#         if posting_result.status_code == http.HTTPStatus.OK:
#             marking_result = mark_notification_processed(notification, correlation_id)
#     except Exception as ex:
#         error_message = str(ex)
#         marking_result = mark_notification_failure(notification, error_message, correlation_id)
#     finally:
#         return posting_result, marking_result
# endregion


# region cleanup
@utils.lambda_wrapper
def clear_notification_queue(event, context):
    logger = event["logger"]
    correlation_id = event["correlation_id"]
    seven_days_ago = now_with_tz() - timedelta(days=7)
    # processed_notifications = get_notifications('processing_status', ['processed'])
    processed_notifications = c_notif.get_notifications_to_clear(
        datetime_threshold=seven_days_ago, stack_name=const.STACK_NAME
    )
    notifications_to_delete = [
        x
        for x in processed_notifications
        if (parser.isoparse(x["modified"]) < seven_days_ago)
        and (
            x[NotificationAttributes.TYPE.value]
            != NotificationType.TRANSACTIONAL_EMAIL.value
        )
    ]
    deleted_notifications = list()
    ddb_client = Dynamodb(stack_name=const.STACK_NAME)
    for n in notifications_to_delete:
        response = ddb_client.delete_item(
            c_notif.NOTIFICATION_TABLE_NAME, n["id"], correlation_id=correlation_id
        )
        if response["ResponseMetadata"]["HTTPStatusCode"] == http.HTTPStatus.OK:
            deleted_notifications.append(n)
        else:
            logger.info(
                f"Notifications deleted before an error occurred",
                extra={
                    "deleted_notifications": deleted_notifications,
                    "correlation_id": correlation_id,
                },
            )
            logger.error(
                "Failed to delete notification",
                extra={"notification": n, "response": response},
            )
            raise Exception(
                f"Failed to delete notification {n}; received response: {response}"
            )
    return deleted_notifications


# endregion
