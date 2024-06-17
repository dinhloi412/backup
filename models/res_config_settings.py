# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sharepoint_client_key = fields.Char(string="Sharepoint client key", config_parameter='sharepoint.client_key')
    sharepoint_client_secret = fields.Char(string="Sharepoint client secret", config_parameter='sharepoint.client_secret')
    sharepoint_tenant_id = fields.Char(string="Sharepoint tenant id", config_parameter='sharepoint.tenant_id')
    sharepoint_scope = fields.Char(string="Sharepoint scope", config_parameter='sharepoint.scope')
    sharepoint_site_url = fields.Char(string="Sharepoint site url", config_parameter='sharepoint.site_url')
    sharepoint_upload_url = fields.Char(string="Sharepoint upload url", config_parameter='sharepoint.upload_url')
    sharepoint_threads = fields.Integer(string="Sharepoint threads", config_parameter='sharepoint.threads')


