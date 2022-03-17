#!/usr/bin/env python3
from thiscovery_dev_tools.aws_deployer import AwsDeployer
from src.common.constants import STACK_NAME


if __name__ == '__main__':
    deployer = AwsDeployer(stack_name=STACK_NAME)
    deployer.main(build_in_container=True, skip_confirmation=True, skip_slack_notification=True)
