# Native-first logistics cross-domain acceptance matrix

**All cases are planned, NOT_RUN on Odoo 19 Enterprise.** Every code PR shall link original and native-first rule IDs, run focused positive and negative tests, and preserve exact logs/head.

## AC-AL-01: PO-only native release

**Logistics rules:** `BRS-01-R001`, `BRS-01-R065`

**Given:** Authorized native PO reaches purchase without SO, transaction or load.
**Expected:** One supplier issue request/queued mail; no fake other records.
**Counterexample:** Draft/import/confirmation replay sends none.

*Runtime proof:* NOT_RUN.

## AC-AL-02: SO-only native release

**Logistics rules:** `BRS-01-R001`, `BRS-01-R065`

**Given:** Native SO confirmation completes without PO/load.
**Expected:** One buyer issue; independent of PO.
**Counterexample:** No non-native auto-approval or duplicate confirmation.

*Runtime proof:* NOT_RUN.

## AC-AL-03: Cross-company isolation

**Logistics rules:** `BRS-01-R003`, `BRS-07-R047`

**Given:** Two companies share partner/order text.
**Expected:** Only exact company evidence binds.
**Counterexample:** Company-less ambiguous item cannot link.

*Runtime proof:* NOT_RUN.

## AC-AL-04: PO-only stock evidence

**Logistics rules:** `BRS-07-R047`

**Given:** PO receipt but no real picking yet.
**Expected:** PO-scoped inbox evidence pending picking.
**Counterexample:** Invented load/stock receipt rejected.

*Runtime proof:* NOT_RUN.

## AC-AL-05: One original many links

**Logistics rules:** `BRS-07-R046`, `BRS-07-R049`

**Given:** One document cites two legitimate loads.
**Expected:** One native original, two exact typed evidence links.
**Counterexample:** No duplicate original and no single-pointer loss.

*Runtime proof:* NOT_RUN.

## AC-AL-06: Alias ambiguous inbox

**Logistics rules:** `BRS-07-R047`

**Given:** Incoming alias file has two same-partner candidates.
**Expected:** Unlinked with one Activity.
**Counterexample:** Never select newest open transaction.

*Runtime proof:* NOT_RUN.

## AC-AL-07: Single verification writer

**Logistics rules:** `BRS-07-R049`, `BRS-07-R050`

**Given:** Unverified document gets native tag.
**Expected:** Business verified stays false pending authorized verification.
**Counterexample:** Native tag/write cannot mark verified.

*Runtime proof:* NOT_RUN.

## AC-AL-08: Internal Request only

**Logistics rules:** `BRS-07-R046`, `BRS-07-R051`

**Given:** Supplier missing file; internal staff request created.
**Expected:** Internal placeholder and one Activity; Linda external Mail only.
**Counterexample:** No native Documents external request invitation.

*Runtime proof:* NOT_RUN.

## AC-AL-09: Verified Request completion

**Logistics rules:** `BRS-07-R049`, `BRS-07-R051`

**Given:** File uploaded into internal Request.
**Expected:** Stay open until exact verified current evidence.
**Counterexample:** Upload alone cannot close requested evidence.

*Runtime proof:* NOT_RUN.

## AC-AL-10: Supplier doc SLA

**Logistics rules:** `BRS-07-R051`

**Given:** Actual pickup Friday; supplier doc missing.
**Expected:** First BD due Monday; +5 after pickup; one external touch.
**Counterexample:** Transaction create_date cannot anchor clock.

*Runtime proof:* NOT_RUN.

## AC-AL-11: Carrier doc SLA

**Logistics rules:** `BRS-07-R051`

**Given:** Actual pickup Friday, CST missing.
**Expected:** First BD due Tuesday, +6 escalate; no invoice blocker.
**Counterexample:** Scale tag cannot prove certified CST or penalty.

*Runtime proof:* NOT_RUN.

## AC-AL-12: Buyer doc SLA

**Logistics rules:** `BRS-07-R051`, `BRS-07-R045`

**Given:** Actual delivery Friday, Receiving missing.
**Expected:** First BD due Monday; +5 escalate, quantity scoped.
**Counterexample:** Supplier pickup cannot anchor buyer timer.

*Runtime proof:* NOT_RUN.

## AC-AL-13: No duplicate reminder

**Logistics rules:** `BRS-06-R038`, `BRS-07-R051`

**Given:** Two same-minute crons after due.
**Expected:** One outgoing intent and one internal Activity.
**Counterexample:** Concurrent jobs cannot send two notices.

*Runtime proof:* NOT_RUN.

## AC-AL-14: Distinct readiness cadence

**Logistics rules:** `BRS-02-R007`, `BRS-06-R039`

**Given:** Supplier not READY, no document yet due.
**Expected:** Monday local status request only.
**Counterexample:** Cannot replace it with +1 BD postpickup document chase.

*Runtime proof:* NOT_RUN.

## AC-AL-15: Carrier ACK

**Logistics rules:** `BRS-05-R030`, `BRS-06-R039`

**Given:** Carrier packet actually sent at T.
**Expected:** T+2h reminder and T+4h escalation; one packet.
**Counterexample:** Reservation/queue time or four-hour packet resend invalid.

*Runtime proof:* NOT_RUN.

## AC-AL-16: No assigned dispatch

**Logistics rules:** `BRS-05-R029`, `BRS-02-R004`

**Given:** Picking moves to assigned but custodian not READY.
**Expected:** No dispatch packet or dispatch_sent stamp.
**Counterexample:** Assigned state never triggers carrier mail.

*Runtime proof:* NOT_RUN.

## AC-AL-17: Dropship report redaction

**Logistics rules:** `BRS-05-R031`, `BRS-05-R033`

**Given:** Confirmed native dropship PO with buyer destination.
**Expected:** Supplier QWeb variant omits buyer identity; lawful PO route preserved.
**Counterexample:** Default report leaks buyer address or blanket route ban.

*Runtime proof:* NOT_RUN.

## AC-AL-18: No native confirmation duplicates

**Logistics rules:** `BRS-05-R034`, `BRS-01-R001`

**Given:** SO action_confirm send_email True in off, shadow, live.
**Expected:** Exactly one authorized sender per mode.
**Counterexample:** Legacy plus native plus Linda triplicate prohibited.

*Runtime proof:* NOT_RUN.

## AC-AL-19: Personal server throttle

**Logistics rules:** `BRS-05-R034`, `BRS-05-R035`

**Given:** Personal mail server owner rate limit defers outgoing mail.
**Expected:** No SMTP attempt recorded; queue remains retryable.
**Counterexample:** Deferral must not become unknown delivery.

*Runtime proof:* NOT_RUN.

## AC-AL-20: Unknown SMTP outcome

**Logistics rules:** `BRS-05-R035`

**Given:** Actual SMTP disconnect after possible delivery.
**Expected:** Unknown until explicit recovery; no automatic retry.
**Counterexample:** Unknown cannot become sent or be blindly duplicated.

*Runtime proof:* NOT_RUN.

## AC-AL-21: Native MIME reply ancestry

**Logistics rules:** `BRS-02-R009`, `BRS-02-R011`, `BRS-02-R014`

**Given:** Parallel requests; original message references one.
**Expected:** Candidate binds exact known request/revision.
**Counterexample:** Most recent chatter or plain From cannot authenticate.

*Runtime proof:* NOT_RUN.

## AC-AL-22: Native AI absent

**Logistics rules:** `BRS-02-R012`, `BRS-02-R062`

**Given:** Free-form reply with AI module unverified.
**Expected:** ai_not_run/unresolved; no business changes.
**Counterexample:** No fallback custom inference or fabricated AI proof.

*Runtime proof:* NOT_RUN.

## AC-AL-23: Native AI adversarial

**Logistics rules:** `BRS-02-R012`, `BRS-02-R062`

**Given:** Installed Manager chooses Worker with malicious stale company args.
**Expected:** Worker rejects before any business writes.
**Counterexample:** AI cannot change READY/rate/stock/posting.

*Runtime proof:* NOT_RUN.

## AC-AL-24: Partial buyer receipt

**Logistics rules:** `BRS-07-R045`, `BRS-07-R048`

**Given:** Buyer report covers 40% actual delivery.
**Expected:** Verify covered quantity only.
**Counterexample:** Whole load invoicing/close cannot infer 100%.

*Runtime proof:* NOT_RUN.

## AC-AL-25: CST independent

**Logistics rules:** `BRS-07-R048`, `BRS-07-R054`

**Given:** Buyer Receiving verified, carrier CST absent.
**Expected:** Buyer eligible per scoped rule; carrier document claim stays open.
**Counterexample:** CST missing does not auto post 150 or globally block close.

*Runtime proof:* NOT_RUN.

## AC-AL-26: No financial auto-post

**Logistics rules:** `BRS-07-R054`

**Given:** Document verified, compliance recompute, Linda response.
**Expected:** No account.move.action_post or adjustment.
**Counterexample:** Computation cannot create/post invoices/credits/penalties.

*Runtime proof:* NOT_RUN.

## AC-AL-27: QuickBooks settlement remains

**Logistics rules:** `BRS-07-R054`

**Given:** Preapproved QB-exit pending, invoice exists.
**Expected:** Odoo does not collect/mark paid by inference.
**Counterexample:** No Odoo bank dunning dual-write before cutover.

*Runtime proof:* NOT_RUN.

## AC-AL-28: Weights are distinct

**Logistics rules:** `BRS-02-R008`, `BRS-07-R052`

**Given:** Supplier weight differs from buyer and certified scale.
**Expected:** AP supplier, AR buyer, scale reference; >5% review.
**Counterexample:** No final_weight auto substitution or AI-extracted money.

*Runtime proof:* NOT_RUN.

## AC-AL-29: Original history preserved

**Logistics rules:** `BRS-07-R050`, `BRS-07-R056`

**Given:** Old import document or superseded document exists.
**Expected:** Historical source kept without current verification.
**Counterexample:** Old bytes not resurrected, no historic live chase.

*Runtime proof:* NOT_RUN.

## AC-AL-30: Cancel/reopen notice sequence

**Logistics rules:** `BRS-05-R034`, `BRS-05-R035`, `BRS-01-R001`

**Given:** Cancel sent issue and reconfirm same terms.
**Expected:** Historical party notice once, then one new release.
**Counterexample:** New issue cannot overtake unsent cancellation notice.

*Runtime proof:* NOT_RUN.

## AC-AL-31: BRS-only install inert

**Logistics rules:** `BRS-05-R029`, `BRS-07-R054`

**Given:** Only BRS repo files installed.
**Expected:** No Odoo model/XML/cron/finance change.
**Counterexample:** No live send/stock/QB operation authorized by install.

*Runtime proof:* NOT_RUN.

## AC-AL-32: Source byte preservation

**Logistics rules:** `BRS-07-R046`, `BRS-01-R003`

**Given:** Install proposal onto exact #305 descendant.
**Expected:** 7 original BRS and rules.json bytes untouched.
**Counterexample:** Reject stale parent, altered old source, wrong branch.

*Runtime proof:* NOT_RUN.

