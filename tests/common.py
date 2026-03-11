"""Shared test utilities for PlastOS test suite.

Factory mixins and PlasticosTestCase live in plasticos_base.test_common.
This module keeps assertion helpers for action/state tests.
"""


def assert_action_result(test_case, result, expected_model=None, expected_type="ir.actions.act_window"):
    """Assert that an action method returns a valid action dict.

    Args:
        test_case: The TestCase instance
        result: The action result dict to validate
        expected_model: Expected res_model value (optional)
        expected_type: Expected action type (default: "ir.actions.act_window")
    """
    test_case.assertIsInstance(result, dict, "Action should return a dict")
    test_case.assertEqual(result.get("type"), expected_type, f"Action type should be {expected_type}")
    if expected_model:
        test_case.assertEqual(result.get("res_model"), expected_model, f"Action res_model should be {expected_model}")


def assert_state_transition(test_case, record, action_name, expected_state, msg=None):
    """Assert that calling an action method transitions to expected state.

    Args:
        test_case: The TestCase instance
        record: The record to call the action on
        action_name: Name of the action method (e.g., "action_confirm")
        expected_state: Expected state after action
        msg: Optional assertion message
    """
    if hasattr(record, action_name):
        getattr(record, action_name)()
        test_case.assertEqual(
            record.state,
            expected_state,
            msg or f"{action_name} should transition to {expected_state}",
        )
    else:
        test_case.skipTest(f"{action_name} not available on {record._name}")


def assert_message_posted(test_case, record, keyword=None):
    """Assert that a message was posted to the record's chatter.

    Args:
        test_case: The TestCase instance
        record: The record to check messages on
        keyword: Optional keyword to search for in message body
    """
    test_case.assertTrue(record.message_ids, "Expected at least one message to be posted")
    if keyword:
        matching = record.message_ids.filtered(lambda m: keyword.lower() in (m.body or "").lower())
        test_case.assertTrue(matching, f"Expected message containing '{keyword}'")
