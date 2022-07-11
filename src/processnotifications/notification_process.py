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
import time

import thiscovery_lib.utilities as utils
import traceback
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from dateutil import parser, tz
from enum import Enum
from http import HTTPStatus
from thiscovery_lib.core_api_utilities import CoreApiClient
from thiscovery_lib.dynamodb_utilities import Dynamodb
from thiscovery_lib.eb_utilities import ThiscoveryEvent
from thiscovery_lib.hubspot_utilities import HubSpotClient
from thiscovery_lib.utilities import (
    get_logger,
    new_correlation_id,
    now_with_tz,
    DetailedValueError,
)

import common.constants as const


NOTIFICATION_TABLE_NAME = "notifications"
MAX_RETRIES = 2


class NotificationType(Enum):
    USER_REGISTRATION = "user-registration"
    TASK_SIGNUP = "task-signup"
    USER_LOGIN = "user-login"
    TRANSACTIONAL_EMAIL = "transactional-email"
    PROCESSING_TEST = "processing-test"


class NotificationStatus(Enum):
    NEW = "new"
    PROCESSING = "processing"
    PROCESSED = "processed"
    RETRYING = "retrying"
    DLQ = "dlq"


class NotificationAttributes(Enum):
    STATUS = "processing_status"
    FAIL_COUNT = "processing_fail_count"
    ERROR_MESSAGE = "processing_error_message"
    TYPE = "type"


def get_notifications_to_process(correlation_id=None, stack_name=const.STACK_NAME):
    ddb = Dynamodb(
        stack_name=stack_name,
        correlation_id=correlation_id,
    )
    notifications_to_process = list()
    for status in [NotificationStatus.NEW.value, NotificationStatus.RETRYING.value]:
        notifications_to_process += ddb.query(
            table_name=NOTIFICATION_TABLE_NAME,
            IndexName="processing-status-index",
            KeyConditionExpression="processing_status = :status",
            ExpressionAttributeValues={
                ":status": status,
            },
        )
    return notifications_to_process


def get_notifications_to_clear(
    datetime_threshold, correlation_id=None, stack_name=const.STACK_NAME
):
    ddb = Dynamodb(stack_name=stack_name, correlation_id=correlation_id)
    return ddb.query(
        table_name=NOTIFICATION_TABLE_NAME,
        IndexName="processing-status-index",
        KeyConditionExpression="processing_status = :status " "AND created < :t1",
        ExpressionAttributeValues={
            ":status": NotificationStatus.PROCESSED.value,
            ":t1": str(datetime_threshold),
        },
        ScanIndexForward=False,
    )


def get_notifications(
    filter_attr_name: str = None,
    filter_attr_values=None,
    correlation_id=None,
    stack_name=const.STACK_NAME,
):
    ddb = Dynamodb(stack_name=stack_name, correlation_id=correlation_id)
    notifications = ddb.scan(
        NOTIFICATION_TABLE_NAME, filter_attr_name, filter_attr_values
    )
    return notifications


def delete_all_notifications(stack_name=const.STACK_NAME):
    ddb = Dynamodb(stack_name=stack_name)
    ddb.delete_all(NOTIFICATION_TABLE_NAME)


def create_notification(label: str):
    notification_item = {
        NotificationAttributes.STATUS.value: NotificationStatus.NEW.value,
        "label": label,
    }
    return notification_item


def put_process_notifications_event():
    event = ThiscoveryEvent(
        {
            "detail-type": "process_notifications",
            "detail": dict(),
        }
    )
    result = event.put_event()
    assert (
        result["ResponseMetadata"]["HTTPStatusCode"] == HTTPStatus.OK
    ), "Failed to put process_notifications event in thiscovery event bus"
    return result


def save_notification(
    key,
    task_type,
    task_signup,
    notification_item,
    correlation_id,
    stack_name=const.STACK_NAME,
):
    ddb = Dynamodb(
        stack_name=stack_name,
        correlation_id=correlation_id,
    )
    ddb.put_item(
        NOTIFICATION_TABLE_NAME,
        key,
        task_type,
        task_signup,
        notification_item,
        False,
        correlation_id,
    )


def get_fail_count(notification):
    if NotificationAttributes.FAIL_COUNT.value in notification:
        return int(notification[NotificationAttributes.FAIL_COUNT.value])
    else:
        return 0


def set_fail_count(notification, new_value):
    notification[NotificationAttributes.FAIL_COUNT.value] = new_value


def mark_notification_processed(
    notification, correlation_id, stack_name=const.STACK_NAME
):
    notification_id = notification["id"]
    notification_updates = {
        NotificationAttributes.STATUS.value: NotificationStatus.PROCESSED.value
    }
    ddb = Dynamodb(stack_name=stack_name)
    return ddb.update_item(
        NOTIFICATION_TABLE_NAME, notification_id, notification_updates, correlation_id
    )


def mark_notification_failure(
    notification, error_message, correlation_id, stack_name=const.STACK_NAME
):
    def update_notification_item(status_, fail_count_, error_message_=error_message):
        notification_updates = {
            NotificationAttributes.STATUS.value: status_,
            NotificationAttributes.FAIL_COUNT.value: fail_count_,
            NotificationAttributes.ERROR_MESSAGE.value: error_message_,
        }
        ddb = Dynamodb(stack_name=stack_name)
        return ddb.update_item(
            NOTIFICATION_TABLE_NAME,
            notification_id,
            notification_updates,
            correlation_id,
        )

    logger = utils.get_logger()
    logger.debug(
        f"Error processing notification",
        extra={
            "error_message": error_message,
            "notification": notification,
            "correlation_id": correlation_id,
        },
    )
    notification_id = notification["id"]
    fail_count = get_fail_count(notification) + 1
    set_fail_count(notification, fail_count)
    if fail_count > MAX_RETRIES:
        logger.error(
            f"Failed to process notification after {MAX_RETRIES} attempts",
            extra={
                "error_message": error_message,
                "notification": notification,
                "correlation_id": correlation_id,
            },
        )
        status = NotificationStatus.DLQ.value
        update_notification_item(status, fail_count)
        errorjson = {"fail_count": fail_count, **notification}
        raise utils.DetailedValueError(f"Notification processing failed", errorjson)
    else:
        status = NotificationStatus.RETRYING.value
        return update_notification_item(status, fail_count)


# region processing
@utils.lambda_wrapper
@utils.api_error_handler
def process_notifications(event, context):
    logger = get_logger()
    notifications = get_notifications_to_process(stack_name=const.STACK_NAME)
    logger.info("process_notifications", extra={"count": str(len(notifications))})

    # note that we need to process all registrations first, then do task signups (otherwise we might try to process a signup for someone not yet registered)
    signup_notifications = list()
    login_notifications = list()
    transactional_emails = list()
    processing_tests = list()
    for notification in notifications:
        notification_type = notification["type"]
        if notification_type == NotificationType.USER_REGISTRATION.value:
            process_user_registration(notification)
        elif notification_type == NotificationType.TASK_SIGNUP.value:
            # add to list for later processing
            signup_notifications.append(notification)
        elif notification_type == NotificationType.USER_LOGIN.value:
            # add to list for later processing
            login_notifications.append(notification)
        elif notification_type == NotificationType.TRANSACTIONAL_EMAIL.value:
            transactional_emails.append(notification)
        elif notification_type == NotificationType.PROCESSING_TEST.value:
            processing_tests.append(notification)
        else:
            error_message = (
                f"Processing of {notification_type} notifications not implemented yet"
            )
            logger.error(error_message)
            raise NotImplementedError(error_message)

    for signup_notification in signup_notifications:
        process_task_signup(signup_notification)

    for login_notification in login_notifications:
        process_user_login(login_notification)

    for email in transactional_emails:
        process_transactional_email(email)

    for test in processing_tests:
        process_test(test)

    return {
        "statusCode": HTTPStatus.OK,
    }


def process_test(notification):
    logger = get_logger()
    correlation_id = new_correlation_id()
    mark_notification_being_processed(notification)
    ddb_client = Dynamodb(stack_name=const.STACK_NAME)
    test_processing_count = ddb_client.get_item(
        table_name="lookups",
        key="test_simultaneous_notification_processing_count",
    )
    new_count = int(test_processing_count["processing_attempts"]) + 1
    ddb_client.put_item(
        table_name="lookups",
        key="test_simultaneous_notification_processing_count",
        item_type="unittest_data",
        item_details=dict(),
        item={
            "processing_attempts": new_count,
        },
        update_allowed=True,
    )
    time.sleep(5)  # simulate a 5-seconds processing routine
    return mark_notification_processed(notification, str(utils.new_correlation_id()))


def mark_notification_being_processed(notification, correlation_id=None):
    logger = get_logger()
    notification_id = notification["id"]
    notification_updates = {
        NotificationAttributes.STATUS.value: NotificationStatus.PROCESSING.value
    }
    ddb_client = Dynamodb(stack_name=const.STACK_NAME)
    try:
        update_response = ddb_client.update_item(
            NOTIFICATION_TABLE_NAME,
            notification_id,
            notification_updates,
            correlation_id,
            ConditionExpression=f"({NotificationAttributes.STATUS.value} IN (:cat1, :cat2))",
            ExpressionAttributeValues={
                ":cat1": NotificationStatus.NEW.value,
                ":cat2": NotificationStatus.RETRYING.value,
            },
        )
    except ClientError as ex:
        if ex.response["Error"]["Code"] == "ConditionalCheckFailedException":
            error_message = (
                "Aborted notification processing (already marked as being processed)"
            )
        else:
            error_message = "Failed to mark notification as being processed"
        raise utils.DetailedIntegrityError(
            error_message,
            details={"notification": notification, "ddb_response": ex.response},
        )
    else:
        return update_response


def process_user_registration(notification):
    logger = get_logger()
    correlation_id = new_correlation_id()
    mark_notification_being_processed(notification, correlation_id)
    try:
        notification_id = notification["id"]
        details = notification["details"]
        user_id = details["id"]
        logger.info(
            "process_user_registration: post to hubspot",
            extra={
                "notification_id": str(notification_id),
                "user_id": str(user_id),
                "email": details["email"],
                "correlation_id": str(correlation_id),
            },
        )
        hs_client = HubSpotClient(correlation_id=correlation_id)
        hubspot_id, is_new = hs_client.post_new_user_to_crm(details)
        logger.info(
            "process_user_registration: hubspot details",
            extra={
                "notification_id": str(notification_id),
                "hubspot_id": str(hubspot_id),
                "isNew": str(is_new),
                "correlation_id": str(correlation_id),
            },
        )

        if hubspot_id == -1:
            errorjson = {"user_id": user_id, "correlation_id": str(correlation_id)}
            raise DetailedValueError("could not find user in HubSpot", errorjson)

        user_jsonpatch = [
            {"op": "replace", "path": "/crm_id", "value": str(hubspot_id)},
        ]

        core_client = CoreApiClient(correlation_id=str(correlation_id))
        patch_user_response = core_client.patch_user(user_id, user_jsonpatch)
        marking_result = mark_notification_processed(notification, correlation_id)
        return patch_user_response, marking_result

    except Exception as ex:
        error_message = str(ex)
        mark_notification_failure(notification, error_message, correlation_id)


def process_task_signup(notification):
    logger = get_logger()
    correlation_id = new_correlation_id()
    mark_notification_being_processed(notification, correlation_id)
    logger.info(
        "Processing task signup notification",
        extra={"notification": notification, "correlation_id": correlation_id},
    )
    posting_result = None
    marking_result = None
    try:
        # get basic data out of notification
        signup_details = notification["details"]
        user_task_id = signup_details["id"]

        # get additional data that hubspot needs from database
        extra_data = signup_details["extra_data"]

        # put it all together for dispatch to HubSpot
        signup_details.update(extra_data)
        signup_details["signup_event_type"] = "Sign-up"

        # fetch hubspot id if not present in event
        if signup_details["crm_id"] is None:
            core_client = CoreApiClient(correlation_id=str(correlation_id))
            user = core_client.get_user_by_user_id(user_id=signup_details["user_id"])
            signup_details["crm_id"] = user["crm_id"]
            if signup_details["crm_id"] is None:
                errorjson = {
                    "user": user,
                    "user_task_id": user_task_id,
                    "correlation_id": str(correlation_id),
                }
                raise DetailedValueError("user does not have crm_id yet", errorjson)
        hs_client = HubSpotClient(correlation_id=correlation_id)
        posting_result = hs_client.post_task_signup_to_crm(signup_details)
        logger.debug(
            "Response from HubSpot API",
            extra={
                "posting_result": posting_result,
                "correlation_id": correlation_id,
            },
        )
        if posting_result == http.HTTPStatus.NO_CONTENT:
            marking_result = mark_notification_processed(notification, correlation_id)
    except Exception as ex:
        error_message = str(ex)
        marking_result = mark_notification_failure(
            notification, error_message, correlation_id
        )
    finally:
        return posting_result, marking_result


def process_user_login(notification):
    logger = get_logger()
    correlation_id = new_correlation_id()
    mark_notification_being_processed(notification, correlation_id)
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


def process_transactional_email(notification, mock_server=False):
    logger = get_logger()
    correlation_id = new_correlation_id()
    mark_notification_being_processed(notification, correlation_id)
    logger.info(
        "Processing transactional email",
        extra={"notification": notification, "correlation_id": correlation_id},
    )
    posting_result = None
    marking_result = None
    try:
        from transactional_email import TransactionalEmail

        email = TransactionalEmail(
            email_dict=notification["details"],
            send_id=notification["id"],
            correlation_id=correlation_id,
        )
        posting_result = email.send(mock_server=mock_server)
        logger.debug(
            "Response from HubSpot API",
            extra={"posting_result": posting_result, "correlation_id": correlation_id},
        )
        if posting_result.status_code == http.HTTPStatus.OK:
            marking_result = mark_notification_processed(notification, correlation_id)
    except Exception as ex:
        error_message = str(ex)
        marking_result = mark_notification_failure(
            notification, error_message, correlation_id
        )
    finally:
        return posting_result, marking_result


# endregion


# region cleanup
@utils.lambda_wrapper
def clear_notification_queue(event, context):
    logger = event["logger"]
    correlation_id = event["correlation_id"]
    seven_days_ago = now_with_tz() - timedelta(days=7)
    # processed_notifications = get_notifications('processing_status', ['processed'])
    processed_notifications = get_notifications_to_clear(
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
            NOTIFICATION_TABLE_NAME, n["id"], correlation_id=correlation_id
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
