"""Real Odoo tests, intentionally NOT marked as run in the portable build receipt."""
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'broker_intelligence')
class TestBrokerKnowledge(TransactionCase):
    def test_harvest_is_reviewable_but_not_admitted(self):
        seed = self.env.ref('plasticos_broker_intelligence.seed_bi_cap_01')
        self.assertEqual(seed.state, 'draft')
        self.assertFalse(seed.reviewer_id)
        self.assertFalse(seed.reviewed_at)
        self.assertTrue(seed.source_sha256)

    def test_approval_without_documented_review_fails(self):
        seed = self.env.ref('plasticos_broker_intelligence.seed_bi_cap_01')
        with self.assertRaises((AccessError, UserError)):
            seed.action_approve()
        self.assertEqual(seed.state, 'draft')

    def test_direct_state_escalation_and_delete_are_rejected(self):
        seed = self.env.ref('plasticos_broker_intelligence.seed_bi_cap_01')
        with self.assertRaises((AccessError, UserError)):
            seed.write({'state':'approved'})
        with self.assertRaises(UserError):
            seed.unlink()

    def test_direct_review_audit_forgery_is_denied(self):
        seed = self.env.ref('plasticos_broker_intelligence.seed_bi_cap_01')
        with self.assertRaises(AccessError):
            self.env['plasticos.broker.review.event'].sudo().create({
                'knowledge_id': seed.id, 'event': 'approved',
                'actor_id': self.env.user.id, 'company_id': self.env.company.id,
                'reason': 'forged approval', 'source_snapshot': 'forged source',
            })

    def test_material_review_edit_invalidates_attestation(self):
        seed = self.env.ref('plasticos_broker_intelligence.seed_bi_cap_01')
        seed.write({'reviewer_attested': True})
        seed.write({'reviewed_meaning': 'Corrected interpretation requires new review'})
        self.assertFalse(seed.reviewer_attested)
        with self.assertRaises(UserError):
            seed.write({'workflow_scope': 'Updated scope', 'reviewer_attested': True})

    def test_knowledge_scope_uses_source_company_only(self):
        service = self.env['plasticos.broker.advice.service']
        other = self.env['res.company'].create({'name': 'Other Broker Company'})
        scoped = self.env['plasticos.broker.knowledge'].sudo().create({
            'stable_key': 'isolated-scope-check', 'name': 'Scoped candidate',
            'proposed_owner': 'plasticos.broker.knowledge', 'source_file': 'evidence.txt',
            'source_selector': '1', 'source_sha256': 'a' * 64,
            'company_id': other.id,
        })
        service = service.with_context(allowed_company_ids=[self.env.company.id, other.id])
        domain = service._knowledge_company_domain(scoped)
        self.assertEqual(domain, ['|', ('company_id', '=', False), ('company_id', '=', other.id)])
        scoped.write({'company_id': False})
        self.assertEqual(service._knowledge_company_domain(scoped), [
            '|', ('company_id', '=', False), ('company_id', '=', service.env.company.id),
        ])

    def test_source_id_never_coerces_float_or_bool_into_a_real_record(self):
        service = self.env['plasticos.broker.advice.service']
        for identifier in (True, 1.5, '1.5'):
            with self.subTest(identifier=identifier):
                with self.assertRaises(UserError):
                    service.advise_v2('plasticos.intake', identifier, '?')

    def test_no_unreviewed_knowledge_in_normal_advice(self):
        self.assertFalse(self.env['plasticos.broker.knowledge'].search([
            ('stable_key','=','BI-CAP-01'),('state','=','approved')]))

    def test_unsupported_advisory_source_denied(self):
        with self.assertRaises(UserError):
            self.env['plasticos.broker.advice.service'].advise_v2('res.partner',1,'Can I quote?')

    def test_malformed_advisory_source_id_is_user_error(self):
        service = self.env['plasticos.broker.advice.service']
        for identifier in ('nonnumeric', 0, -1, None):
            with self.subTest(identifier=identifier):
                with self.assertRaises(UserError):
                    service.advise_v2('plasticos.intake', identifier, 'Does evidence exist?')
