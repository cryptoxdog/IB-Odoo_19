# Do not copy private inputs into this pack

Customer names, emails, phones, notes, and the historical VanillaSoft CSV stay in the overnight pack's `PRIVATE_INPUTS/` directory. This daytime pack records hashes and points at that directory. Do not duplicate those files here, and do not commit them from either directory.

The pinned crosswalk is an allowlist (`erp_ct_id`, `vanillasoft_contact_id`). It is not a contact payload. The shell fetches each ID from the VanillaSoft API.
