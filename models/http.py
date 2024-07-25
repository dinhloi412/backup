import base64
import logging

from odoo import fields, models, api
from odoo.http import request

from .sharepoint import SharePoint
from .management import BackupManagement
from . import constants as const

_logger = logging.getLogger(__name__)


class Http(models.AbstractModel):
    _inherit = "ir.http"

    @api.model
    def _get_content_common(self, xmlid=None, model='ir.attachment', res_id=None, field='datas', unique=None,
                            filename=None, filename_field='name', download=None, mimetype=None,
                            access_token=None, token=None):
        status, headers, content = self.binary_content(
            xmlid=xmlid, model=model, id=res_id, field=field, unique=unique, filename=filename,
            filename_field=filename_field, download=download, mimetype=mimetype, access_token=access_token
        )
        if status != 200:
            # custom redirect to sharepoint
            if status == 301:
                attachment = self.env[const.ATTACHMENT_MODEL].browse(res_id)
                if attachment.sharepoint_id:           
                    system_params = BackupManagement.get_system_params(self)
                    sharepoint_res = SharePoint().get_file(attachment.sharepoint_id, system_params["drive_url"],system_params["client_key"],
                        system_params["client_secret"], system_params["tenant_id"], system_params["scope"])
                    if sharepoint_res.status_code == 200:
                        json_data = sharepoint_res.json()
                        content = json_data["@microsoft.graph.downloadUrl"]
                        
                    _logger.info(f"Get file from Sharepoint: {sharepoint_res}")
            return self._response_by_status(status, headers, content)
        else:
            content_base64 = base64.b64decode(content)
            headers.append(('Content-Length', len(content_base64)))
            response = request.make_response(content_base64, headers)
        return response

