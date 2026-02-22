# ============================================
# Canonical Header (v4.0 Production Baseline)
# ============================================
# File Name: governance_edit_lock_v4.5.py
# Version: 4.6
# Created: 2025-10-17
# Author: Igor Beylin
# Domain: Plastic Recycling / AI-Augmented ERP
# Purpose: Restricts governance model edits to authorized users only
# Related Files: ../configs/role_access_matrix_v4.5.yaml, ../security/security.xml, governance_audit_hooks_v4.0C.py
# ============================================

from odoo import api, models
from odoo.exceptions import AccessError


class GovernanceEditLock(models.AbstractModel):
    _name = "plasticos.governance_edit_lock"
    _description = "Governance Edit Lock"

    @api.model
    def check_governance_edit_permission(self, user):
        if user.login not in ["igor@plasticos.ai", "Igor-01"]:
            raise AccessError("Only Igor may modify governance policies.")
        return True
