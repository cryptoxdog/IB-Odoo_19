"""Run the native-bridge verification cases on the Enterprise fixture.

plasticos_documents_native is installed and upgraded with this module, and the
fixture roster refuses naming it as its own test-module target.
"""

from odoo.addons.plasticos_documents_native.tests.test_verification_delegation import (
    TestNativeVerificationDelegation,
)


class TestNativeVerificationOnEnterpriseFixture(TestNativeVerificationDelegation):
    """Same cases. The class module tag is plasticos_documents so the roster runs them."""

    allow_inherited_tests_method = True
