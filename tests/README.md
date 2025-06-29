# Camp44 Functional Tests

This directory contains functional tests for the Camp44 API. These tests verify complete end-to-end functionality of API endpoints rather than isolated unit tests of specific components.

## Test Files

The following functional tests are available:

1. **test_login.py**: Tests authentication endpoints (login, token generation)
2. **test_oidc.py**: Tests OpenID Connect authentication flow
3. **test_passkey.py**: Tests WebAuthn/Passkey authentication
4. **test_apps.py**: Tests application CRUD operations
5. **test_entities.py**: Tests entity management within applications
6. **test_metering.py**: Tests usage metering functionality

## Recommended Run Order

For the most reliable test execution, run the tests in the following order:

```bash
# 1. Run authentication-related tests first
python -m pytest tests/api/v1/test_login.py -v
python -m pytest tests/api/v1/test_oidc.py -v
python -m pytest tests/api/v1/test_passkey.py -v

# 2. Run app management tests
python -m pytest tests/api/v1/test_apps.py -v

# 3. Run entity tests
python -m pytest tests/api/v1/test_entities.py -v

# 4. Run metering tests
python -m pytest tests/api/v1/test_metering.py -v
```

For a complete test run of all functional tests:

```bash
python -m pytest tests/api/v1 -v
```

## Test Environment

The tests rely on fixtures defined in `conftest.py` that set up:
- Database connections
- Test users
- Test applications
- Authentication helpers

All tests have been converted to use synchronous code patterns to match the synchronous API implementation.
