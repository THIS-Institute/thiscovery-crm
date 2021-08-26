#!/usr/bin/env python3

from thiscovery_dev_tools.deploy_to_aws import AwsDeployer

import local.dev_config  # set environment variables
import local.secrets  # set environment variables
from src.common.constants import STACK_NAME


if __name__ == '__main__':
    deployer = AwsDeployer(stack_name=STACK_NAME)
    deployer.main()
