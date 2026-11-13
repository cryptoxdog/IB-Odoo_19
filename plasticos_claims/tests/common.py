"""Shared fixtures for claims tests."""


def create_claims_manager(env, login="claims_test_manager", name="Claims Test Manager"):
    """Create an internal user who holds the Claims Manager group."""
    return env["res.users"].create(
        {
            "name": name,
            "login": login,
            "group_ids": [
                (
                    6,
                    0,
                    [
                        env.ref("base.group_user").id,
                        env.ref("plasticos_claims.group_claims_manager").id,
                    ],
                )
            ],
        }
    )
