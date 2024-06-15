from odoo import models

from odoo import fields
class BackupManagement(models.Model):
    _name = "log.backup"
    _description = "Log backup"

    backup_id = fields.Many2one('backup.management', string='Backup')
    status_code = fields.Integer(string='State code')
    message = fields.Text(string='Message')


