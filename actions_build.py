#!/usr/bin/env python3
from thiscovery_dev_tools.aws_deployer import AwsDeployer
from src.common.constants import STACK_NAME


def main():
    deployer = AwsDeployer(stack_name=STACK_NAME)
    deployer.parse_sam_template()
    deployer.validate_template()
    deployer.build(build_in_container=True)


if __name__ == '__main__':
    main()
