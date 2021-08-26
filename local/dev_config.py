# add/edit your dev configuration parameters here
import os

SECRETS_NAMESPACE = '/test-afs25/'
UNIT_TEST_NAMESPACE = '/test-afs25/'

# Settings for tests
# TEST_ON_AWS = False
TEST_ON_AWS = True
AWS_TEST_API = 'https://test-afs25-api.thiscovery.org/'

os.environ['TEST_ON_AWS'] = str(TEST_ON_AWS)
os.environ['SECRETS_NAMESPACE'] = SECRETS_NAMESPACE
os.environ['UNIT_TEST_NAMESPACE'] = UNIT_TEST_NAMESPACE
os.environ['AWS_TEST_API'] = AWS_TEST_API
