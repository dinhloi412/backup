from odoo import fields, models, api

from .sharepoint import SharePoint
from .management import BackupManagement


class IrAttachment(models.Model):
    _inherit = "ir.attachment"
    url = fields.Char("url", index=True, size=2048)
    sharepoint_id = fields.Char("sharepoint_id")

    def unlink(self):
        system_params = BackupManagement.get_system_params(self)
        if self.sharepoint_id:
            SharePoint().remove_file_sharepoint(self.sharepoint_id, system_params["drive_url"], system_params["client_key"],
                system_params["client_secret"],system_params["tenant_id"], system_params["scope"])
        return super(IrAttachment, self).unlink()
