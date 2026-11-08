# RecycleOS Export Addendum: acceptance probes and counterexamples

These are **proposed** behavior tests, not executed tests. All outcomes: `NOT_RUN`. They do not authorize implementation, real carrier contact, physical releases or filings.

| ID | Scenario and expected behavior | Negative control |
| --- | --- | --- |
| EXP-01 | Create a booking using all six operator-critical fields: Booking No., Steamship Line, Port of Loading, Port of Discharge, Cut Off and Earliest Return Date. A draft can be saved before provider values are fully confirmed; dispatch validation knows which required evidence is missing. | Do not invent missing carrier schedule values. |
| EXP-02 | One booking contains two ocean containers; each contains independently scanned and uniquely identified Odoo physical packages; aggregate weight and manifest reflect actual scans. | Do not confuse booking number, ocean container number, stock package and material lot. |
| EXP-03 | An already labeled Gaylord is scanned onto the container; its material, lot and net weight resolve to the same authoritative source; authorized native delivery uses that stock. | No duplicate package identity, duplicated stock quant, or duplicate shipment completion on rescans. |
| EXP-04 | Exact ERD and cargo gate-in cutoff establish a receiving window for the correct terminal, booking and revision. | A gate event earlier than ERD cannot be reported as accepted by inference; a later-than-cutoff event cannot be silently treated as on time. |
| EXP-05 | The carrier updates ERD/cutoff after the container was stuffed; the view shows the old and new schedule with provenance and requires review of affected appointments. | No destructive overwrite, phantom permission, hidden rescheduling or silent release. |
| EXP-06 | Carrier and terminal supply different ERD/cutoff observations. System records both and flags ambiguity for verification. | No latest-timestamp-wins shortcut; do not auto-assert a valid window. |
| EXP-07 | Terminal provides a date-only cutoff while the shipping line provides a timed cutoff; represent precision and timezone explicitly. | Do not manufacture an implied 23:59 deadline or discard daylight-saving context. |
| EXP-08 | A sailing is rolled: prior booking/sailing timeline and package manifest remain reconstructable, while approved new association revalidates movement and papers. | No loss of original booking evidence and no silent reallocation to another customer. |
| EXP-09 | Scanned cargo package weights and container tare are available; system retains estimate, certification source and method for any VGM separately. | Sum of net cargo weights is not automatically treated as certified VGM. |
| EXP-10 | Ocean export shipment retains carrier-issued ocean B/L distinct from a domestic pickup/delivery BOL; supporting docs have typed authoritative links. | No fabricated or auto-issued carrier B/L from local trucking PDF. |
| EXP-11 | The same booking's cargo cutoff, VGM cutoff and shipping-instruction cutoff differ. All are individually displayed and checked for the relevant operation. | Do not collapse distinct deadline types into a single Cut Off. |
| EXP-12 | A controlled material or jurisdiction triggers verification of applicable export filings/permits by an authorized owner. | No universal auto-clearance, no assumption all plastic scrap is freely exportable, no unauthenticated submission. |
| EXP-13 | One of the booked containers is partially loaded and shipping is delayed. Actual physical stock and package assignments remain correct and reversible only by authorized traceable actions. | No phantom container departure or involuntary financial posting. |
| EXP-14 | Incoming or outbound truck/platform scale evidence differs from negotiated supplier/buyer settlement weight. Preserve all observations and independently authorized commercial quantity. | No automatic invoice/AP/AR mutation by device update. |
| EXP-15 | Employee attempts to associate one physical package with two simultaneously active actual export container loads. | No impossible double physical assignment or double movement. |

## Decision-grade early demonstration (not completed)

On one properly configured Odoo 19 instance, use one export sale and booked ocean movement: (1) record the six fields and a source revision; (2) scan three existing QR-labeled Gaylords onto ocean container A, one onto container B; (3) record seals, weights, and typed photos/tickets; (4) prove packages and actual stock moves are singly and correctly accounted; (5) modify ERD and cutoff from a revised carrier source and verify warning + evidence history; (6) generate a source-linked packing manifest; (7) verify that no B/L, export clearance or financial posting was fabricated. Record actual test environment and receipts before claiming PASS.

## Counterinterpretation

An exporter could need more value from compliance automation or carrier milestone integration than from scanning. The dock-first candidate should be compared with an import/export document-coordination-only workflow using the same existing Odoo records. No market response, technical run or customer willingness-to-pay evidence exists in this packet.
