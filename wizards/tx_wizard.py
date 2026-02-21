"""
Linda Logistics Agent v6.0 - Transaction Wizards
Wizards for transaction operations and bulk actions
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TransactionBulkUpdateWizard(models.TransientModel):
    _name = 'sm.tx.bulk.update.wizard'
    _description = 'Bulk Update Transaction Status'
    
    new_state = fields.Selection([
        ('pending_supplier', 'Pending Supplier'),
        ('supplier_ready', 'Supplier Ready'),
        ('do_created', 'DO Created'),
        ('dispatch_sent', 'Dispatch Sent'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ], string='New Status', required=True)
    
    reason = fields.Text(string='Reason', required=True)
    
    tx_ids = fields.Many2many('sm.tx', string='Transactions')
    
    def action_update_status(self):
        """Update status for selected transactions"""
        if not self.tx_ids:
            raise UserError(_('No transactions selected'))
        
        logistics_engine = self.env['sm.logistics.automation']
        
        for tx in self.tx_ids:
            result = logistics_engine.update_odoo_status(
                'sm.tx', 
                tx.id, 
                self.new_state,
                {'reason': self.reason}
            )
            
            if result.get('errors'):
                raise UserError(_('Error updating transaction %s: %s') % (tx.name, result['errors'][0]))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d transactions updated successfully') % len(self.tx_ids),
                'type': 'success'
            }
        }
