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
import validators
from http import HTTPStatus
from typing import Dict

import thiscovery_lib.hubspot_utilities as hs
import thiscovery_lib.utilities as utils
import notification_process as np
from thiscovery_lib.core_api_utilities import CoreApiClient
from thiscovery_lib.dynamodb_utilities import Dynamodb

import common.constants as const
from notification_send import new_transactional_email_notification


class TransactionalEmail:
    templates_table = "HubspotEmailTemplates"

    def __init__(self, email_dict, send_id, correlation_id=None):
        """
        Args:
            email_dict (dict): must contain either a to_recipient_id (user_id or anon_project_specific_user_id) or a to_recipient_email.
                    If both to_recipient_id and to_recipient_email are present, to_recipient_id will be used
            send_id (str): The ID of a particular send. No more than one email with a given sendId will be send per portal,
                    so including a sendId is a good way to prevent duplicate email sends. This will normally be the item id of the
                    notification table.
            correlation_id:
        """
        self.send_id = str(send_id)
        self.template_name = email_dict.get("template_name")
        self.to_recipient_id = email_dict.get("to_recipient_id")
        self.to_recipient_email = email_dict.get("to_recipient_email")
        if (self.to_recipient_id is None) and (self.to_recipient_email is None):
            raise utils.DetailedValueError(
                "Either to_recipient_id or to_recipient_email must be present in email_dict",
                details={"email_dict": email_dict, "correlation_id": correlation_id},
            )
        if self.template_name is None:
            raise utils.DetailedValueError(
                "template_name must be present in email_dict",
                details={"email_dict": email_dict, "correlation_id": correlation_id},
            )

        self.email_dict = email_dict
        self.logger = utils.get_logger()
        self.correlation_id = str(correlation_id)
        self.core_client = CoreApiClient(correlation_id=correlation_id)
        self.ddb_client = Dynamodb(correlation_id=correlation_id, stack_name=const.STACK_NAME)
        self.ss_client = hs.SingleSendClient(correlation_id=correlation_id)
        self.template = None
        self.user = None
        self.project = None
        self.template_lookup_map = {
            "user_email": self._lookup_user_email,
            "user_first_name": self._lookup_user_first_name,
            "user_last_name": self._lookup_user_last_name,
            "project_name": self._lookup_project_name,
        }
        self.lookup_properties = (
            list()
        )  # properties in email_dict that were used for lookups

    def _lookup_project_name(self):
        if not self.project:
            self._get_project()
        return self.project["project_name"]

    def _lookup_user_email(self):
        if not self.user:
            self._get_user()
        return self.user["email"]

    def _lookup_user_first_name(self):
        if not self.user:
            self._get_user()
        return self.user["first_name"]

    def _lookup_user_last_name(self):
        if not self.user:
            self._get_user()
        return self.user["last_name"]

    def _get_template_details(self):
        self.template = self.ddb_client.get_item(
            table_name=self.templates_table,
            key=self.template_name,
            correlation_id=self.correlation_id,
        )
        if self.template is None:
            raise utils.ObjectDoesNotExistError(
                "Template not found", details={"template_name": self.template_name}
            )
        return self.template

    def _validate_properties(self):
        if self.template is None:
            self._get_template_details()
        for p_type in ["contact_properties", "custom_properties"]:
            type_name = p_type.split("_")[0]
            required_p_names = list()
            optional_p_names = list()
            # check all required properties are present in body of call
            for p in self.template[p_type]:
                if p["required"] is True:
                    required_p_names.append(p["name"])
                else:
                    optional_p_names.append(p["name"])
            self.logger.debug(
                f"{type_name} properties in template",
                extra={
                    "required_p_names": required_p_names,
                    "optional_p_names": optional_p_names,
                },
            )

            for p_name in required_p_names:
                try:  # get property value from email_dict
                    p_value = self.email_dict[p_type][p_name]
                except KeyError:
                    try:  # lookup property value using appropriate class method
                        p_value = self.template_lookup_map[p_name]()
                    except KeyError:
                        raise utils.DetailedValueError(
                            f"Required {type_name} property {p_name} not found in call body",
                            details={
                                "email_dict": self.email_dict,
                                "correlation_id": self.correlation_id,
                            },
                        )

                if not p_value:
                    raise utils.DetailedValueError(
                        f"Required {type_name} property {p_name} cannot be null",
                        details={
                            "email_dict": self.email_dict,
                            "correlation_id": self.correlation_id,
                        },
                    )
                else:
                    self.email_dict[p_type][p_name] = p_value

            # check all properties in body of call are either specified in template or used for lookup
            properties_in_call = self.email_dict.get(p_type)
            if properties_in_call is not None:
                p_names_in_call = self.email_dict.get(p_type).keys()
                for p in p_names_in_call:
                    if p not in [
                        *required_p_names,
                        *optional_p_names,
                        *self.lookup_properties,
                    ]:
                        raise utils.DetailedIntegrityError(
                            f"Call {type_name} property {p} is not specified in email template",
                            details={
                                "email_dict": self.email_dict,
                                f"template_required_{type_name}_properties": self.template[
                                    p_type
                                ],
                                "correlation_id": self.correlation_id,
                            },
                        )
        return True

    def _get_project(self) -> Dict[str, str]:
        """
        Resolves the project name of the project task id provided in email_dict.
        """
        pt_id_name = "project_task_id"
        self.lookup_properties.append(pt_id_name)
        pt_id = self.email_dict["custom_properties"].get(pt_id_name)
        projects = self.core_client.get_projects()
        for p in projects:
            for t in p["tasks"]:
                if t["id"] == pt_id:
                    self.project = {"project_name": p["name"]}
                    return self.project

    def _get_user(self):
        try:
            self.user = self.core_client.get_user_by_user_id(
                self.to_recipient_id
            )
        except AssertionError:
            try:
                self.user = self.core_client.get_user_by_anon_project_specific_user_id(
                    self.to_recipient_id
                )
            except AssertionError:
                raise utils.ObjectDoesNotExistError(
                    "Recipient id does not match any known user_id or anon_project_specific_user_id",
                    details={
                        "to_recipient_id": self.to_recipient_id,
                        "correlation_id": self.correlation_id,
                    },
                )
        return self.user

    @staticmethod
    def _format_properties_to_name_value(properties_dict):
        if properties_dict:
            output_list = list()
            for k, v in properties_dict.items():
                output_list.append(
                    {
                        "name": k,
                        "value": v,
                    }
                )
            return output_list

    def send(self, mock_server=False):
        if mock_server:
            self.ss_client.mock_server = True
        self._get_template_details()
        self._validate_properties()
        if self.to_recipient_id:
            user = self._get_user()
            if not user["crm_id"]:
                raise utils.ObjectDoesNotExistError(
                    "Recipient does not have a HubSpot id",
                    details={
                        "user": user,
                        "correlation_id": self.correlation_id,
                    },
                )
            self.to_recipient_email = user["email"]
        else:
            if validators.email(self.to_recipient_email) is not True:
                raise utils.DetailedValueError(
                    "to_recipient_email is not a valid email address",
                    details={
                        "email_dict": self.email_dict,
                        "correlation_id": self.correlation_id,
                    },
                )

        return self.ss_client.send_email(
            template_id=self.template["hs_template_id"],
            message={
                "from": self.template["from"],
                "to": self.to_recipient_email,
                "cc": self.template["cc"],
                "bcc": self.template["bcc"],
                "sendId": self.send_id,
            },
            contactProperties=self._format_properties_to_name_value(
                self.email_dict.get("contact_properties")
            ),
            customProperties=self._format_properties_to_name_value(
                self.email_dict.get("custom_properties")
            ),
        )


@utils.lambda_wrapper
# @utils.api_error_handler
def send_transactional_email(event, context):
    """
    Processes transactional_email events
    """
    logger = event["logger"]
    correlation_id = event["correlation_id"]
    email_dict = event["detail"]
    alarm_test = email_dict.get("brew_coffee")
    if alarm_test:
        raise utils.DeliberateError("Coffee is not available", details={})
    new_transactional_email_notification(email_dict, correlation_id)
    # todo: decouple notification creation from processing by posting an event that triggers processing rather than calling processing method directly
    np.process_notifications(event, context)
    return {
        "statusCode": HTTPStatus.NO_CONTENT,
    }
