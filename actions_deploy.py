#!/usr/bin/env python3
from thiscovery_dev_tools.aws_deployer import AwsDeployer
from src.common.constants import STACK_NAME


def main():
    deployer = AwsDeployer(stack_name=STACK_NAME)
    deployer.deploy(confirm_cf_changeset=False)


if __name__ == '__main__':
    main()
