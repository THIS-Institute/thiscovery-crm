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
import copy

CUSTOM_EMAIL_EB_EVENT = {
    "version": "0",
    "id": "0d24c07d-bba0-6ae8-3c1c-ec2282016258",
    "detail-type": "REDACTED",
    "source": "qualtrics",
    "account": "REDACTED",
    "time": "2021-08-26T14:18:42Z",
    "region": "REDACTED",
    "resources": [],
    "detail": {
        "template_name": "test_custom_email",
        "file_name": "Interview form",
        "file_description": "This is the interview form you will need to print before your appointment",
        "file_instruction": "Please do NOT print this double-sided",
        "file_download_url": "https://www.thiscovery.org",
        "anon_project_specific_user_id": "1ef35c8b-6f78-4c45-8de0-9e7e4f297b20",
        "project_task_id": "b335c46a-bc1b-4f3d-ad0f-0b8d0826a908",
    }
}

CUSTOM_EMAIL_EB_EVENT_NO_ID = copy.deepcopy(CUSTOM_EMAIL_EB_EVENT)
CUSTOM_EMAIL_EB_EVENT_NO_ID['detail'] = {
        "template_name": "test_custom_email",
        "to_recipient_email": "clive@email.com",
        "subject": "[thiscovery notification] ABC WP1.4a participant was redirected to interview booking",
        "title": "ABC WP1.4a participant was redirected to interview booking",
        "message_body": "Participant 9313c872-c7b3-4b29-afc7-c42aeef326ba has just been redirect to interview booking. "
                        "Please check Qualtrics for their choice on how to receive the forms"
    }
