`skipped` means the source row was kept and did not create a new partner. Both counts are accounted for on the clone.

**Contacts, 1,116.** The importer creates one person per company and name. The first and last word are the identity, so extra rows for that same person are aliases, not new partners.

*   **1,111** are those extra `CT_ID`s. Each one got a `legacy_erp_contact_*` marker pointing at the person already created. That is why the database has 2,615 distinct contact partners and 3,726 contact markers: 2,615 + 1,111.
*   **5** were not stored as people. A contact title with no letter is treated as a phone number and written onto the company. A name that is a site mailbox is written onto that location. Neither path creates a person.

**Locations, 39.** An address is folded onto the company when it is the company's remit, or when its name is the company name. These 39 did not change the company: street, city, zip, phone, and email were already filled by an earlier address of that same company, and this row's street was blank or the same, so no child location was created. The `AddressID` marker still points at the company.

The other addresses went the other two ways: **1,297** folded onto the company and filled at least one blank field (`updated`), and **1,266** became child locations (`created`). That is 1,336 markers on companies and 1,266 on children, 2,602 in total.
