from odoo import models

from odoo import fields


class LogManagement(models.Model):
    _name = "log.backup"
    _description = "Log backup"

    backup_id = fields.Many2one('backup.management', string='Backup')
    status_code = fields.Integer(string='State code')
    message = fields.Text(string='Message')
    attachment_name = fields.Char(string='Attachment name')
    log_type = fields.Char(string='Log type')
    url = fields.Char(string='URL')

    def create_log(self, data: dict):
        try:
            self["log.backup"].create(data)
            self.cr.commit()
            return
        except Exception as e:
            return e
