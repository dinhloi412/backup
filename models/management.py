import http
import os
import mimetypes
import uuid
import threading
import logging
import odoo
import base64

from odoo.http import request
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError
from apscheduler.schedulers.background import BackgroundScheduler

from . import utils
from .sharepoint import SharePoint
from . import constants as const

DATA_DIR = odoo.tools.config["data_dir"]

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
        print("just inherited")

        if status != 200:
            return self._response_by_status(status, headers, content)
        else:
            content_base64 = base64.b64decode(content)
            headers.append(('Content-Length', len(content_base64)))
            response = request.make_response(content_base64, headers)
        return response


class IrAttachment(models.Model):
    _inherit = "ir.attachment"
    url = fields.Char("url", index=True, size=2048)
    sharepoint_id = fields.Char("sharepoint_id")

    def unlink(self):
        system_params = BackupManagement.get_system_params(self)
        if self.sharepoint_id:
            SharePoint().remove_file_sharepoint(
                self.sharepoint_id,
                system_params["drive_url"],
                system_params["client_key"],
                system_params["client_secret"],
                system_params["tenant_id"],
                system_params["scope"],
            )
        return super(IrAttachment, self).unlink()


class ModelAttachment(models.Model):
    _name = "ir.model.attachment"
    _description = "Model attachment"

    model_id = fields.Many2many("ir.attachment")
    name = fields.Char(string="Model name")
    backup_management_id = fields.Many2one("backup.management", string="Backup Management ID")


class BackupManagement(models.Model):
    _name = "backup.management"
    _description = "Backup management"
    _inherit = ["mail.thread"]

    scheduler = BackgroundScheduler()

    name = fields.Char(string="Name", required=True)
    from_date = fields.Datetime(string="From Date", required=True)
    to_date = fields.Datetime(string="To Date", required=True)
    total_files = fields.Integer(string="Total Files")
    total_size = fields.Float(string="Total Size (GB)")
    total_success = fields.Integer(string="Total Success")
    total_time = fields.Char(string="Upload time")
    executed_at = fields.Datetime(string="Execute At")
    is_scheduled = fields.Boolean(string="Scheduled", default=False)
    status = fields.Selection(
        selection=[
            ("created", "Created"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        required=True,
        default="created",
    )
    cron_id = fields.Char(string="Cron ID")
    model_ids = fields.Many2many("ir.model", string="Model name")
    conflict_behavior = fields.Selection(
        selection=[("fail", "Fail"), ("replace", "Replace"), ("rename", "Rename")],
        string="Conflict Behavior",
        required=True,
        default="rename",
    )
    is_valid = threading.Event()

    @api.constrains("from_date", "to_date")
    def _validate_date(self):
        for record in self:
            if record.from_date > record.to_date:
                raise ValidationError("From date must be less than to date!")

    def _get_cron(self):
        if self.scheduler.get_job(self.cron_id):
            return True
        return False

    def action_cancel(self):
        for record in self:
            if record.status == const.CANCELED_STATUS or record.status == const.DONE_STATUS:
                raise ValidationError("cannot cancel this record")
            if record.scheduler.get_job(record.cron_id) is not None:
                record.scheduler.remove_job(record.cron_id)
            record.status = const.CANCELED_STATUS
        self.is_valid.set()
        return True

    def get_attachments(self, start_date: str, end_date: str, model_ids: list):
        converted_str = utils.convert_query_db(const.EXCEPT_EXTENSION)
        query = """select id from ir_attachment where type = '%s' and mimetype not in (%s)""" % (
            const.ATTACHMENT_BINAYRY_TYPE,
            converted_str,
        )
        if start_date != "" and end_date != "":
            query += """ AND ir_attachment.create_date >= '%s' AND ir_attachment.create_date <= '%s'""" % (
                start_date,
                end_date,
            )

        if len(model_ids) > 0:
            models_name = self.get_model_name(model_ids)
            if len(models_name) > 0:
                converted_str = utils.convert_query_db(models_name)
                query += """ AND ir_attachment.res_model in (%s)""" % converted_str
        self.env.cr.execute(query)
        attrs = self.env.cr.dictfetchall()
        return attrs

    def get_attachment_by_id(self, new_cr, id: int):
        attachment = self.env[const.ATTACHMENT_MODEL].browse(id).with_env(self.env(cr=new_cr))
        if not attachment:
            _logger.warning(f"Attachment with ID {id} not found")
            return None
        return attachment

    def get_model_name(self, ids: list):
        models_name = self.env["ir.model"].search([("id", "in", ids)])
        names = [x["model"] for x in models_name]
        return names

    def update_backup_management(self, new_cr, backup_id: int, data: dict):
        backup_management = self.env[self._name].browse(backup_id).with_env(self.env(cr=new_cr))
        if backup_management:
            backup_management.write(data)
        return self.env.cr.commit()

    def add_cron(
            self,
            executed_at,
            data: list,
            backup_id: int,
            cron_id: str,
            behavior: str,
            system_params: dict,
    ):
        self.scheduler.add_job(
            self.sharepoint_upload,
            trigger="date",
            run_date=datetime(
                int(executed_at.year),
                int(executed_at.month),
                int(executed_at.day),
                int(executed_at.hour),
                int(executed_at.minute),
                int(executed_at.second),
            ),
            args=[data, backup_id, behavior, system_params],
            id=cron_id,
        )
        if self.scheduler.state == 0:
            self.scheduler.start()

    def sharepoint_upload(self, att_ids: list, backup_id: int, behavior: str, system_params: dict):
        start_time = datetime.now()
        drive_url = system_params["drive_url"]
        root_folder = system_params["root_folder"]
        threads = system_params["threads"]
        host_name = system_params["host_name"]
        client_key = system_params["client_key"]
        client_secret = system_params["client_secret"]
        tenant_id = system_params["tenant_id"]
        scope = system_params["scope"]

        new_cr = self.pool.cursor()
        self = self.with_env(self.env(cr=new_cr))
        update_record = {"status": const.RUNNING_STATUS}
        self.update_backup_management(new_cr, backup_id, update_record)  # update status -> running

        processes = []
        upload_url = f"{drive_url}/root:/{root_folder}"
        total_success = 0

        with ThreadPoolExecutor(max_workers=int(threads)) as executor:
            for id in att_ids:
                if self.is_valid.is_set():
                    break
                processes.append(
                    executor.submit(self.handle_request_sharepoint, int(id["id"]), upload_url, host_name, client_key,
                                    client_secret, tenant_id, scope, behavior, backup_id,
                                    )
                )
        for process in as_completed(processes):
            if self.is_valid.is_set():
                break
            result = process.result()
            if result:
                total_success += 1
        if not self.is_valid.is_set():
            total_time = datetime.now() - start_time
            update_record = {
                "status": const.DONE_STATUS,
                "total_success": total_success,
                "total_time": utils.convert_time_measure(total_time),
            }
            self.update_backup_management(new_cr, backup_id, update_record)  # update status -> finished
        new_cr.commit()
        new_cr.close()

        return True

    def get_system_params(self):
        config_parameter = self.env["ir.config_parameter"].sudo()
        system_params = {
            "host_name": utils.get_host_name(config_parameter.get_param("web.base.url")),
            "client_key": config_parameter.get_param("sharepoint.client_key"),
            "client_secret": config_parameter.get_param("sharepoint.client_secret"),
            "tenant_id": config_parameter.get_param("sharepoint.tenant_id"),
            "upload_url": config_parameter.get_param("sharepoint.upload_url"),
            "site_url": config_parameter.get_param("sharepoint.site_url"),
            "scope": config_parameter.get_param("sharepoint.scope"),
            "threads": config_parameter.get_param("sharepoint.threads"),
            "drive_url": config_parameter.get_param("sharepoint.drive_url"),
            "root_folder": config_parameter.get_param("sharepoint.root_folder"),
        }
        return system_params

    def handle_request_sharepoint(
            self, id: int, upload_url, host_name, client_key, client_secret, tenant_id, scope, behavior, backup_id: str
    ):
        if self.is_valid.is_set():
            return
        with self.pool.cursor() as new_cr:
            self = self.with_env(self.env(cr=new_cr))
            attachment = self.sudo().get_attachment_by_id(new_cr, id)
            _logger.info("attachment_id: %s", attachment.id)
            year = utils.get_year(str(attachment.create_date))
            upload_path = f"{upload_url}/{host_name}/{attachment.res_model}/{year}/{attachment.name}"
            _logger.info(f"upload_path: {upload_path}")
            valid = True
            sharepoint_res = SharePoint().upload_file_to_sharepoint(
                upload_path, client_key, client_secret, tenant_id, scope, behavior, attachment.datas
            )
            download_url = None
            if sharepoint_res:
                if (
                        sharepoint_res.status_code == http.HTTPStatus.OK
                        or sharepoint_res.status_code == http.HTTPStatus.CREATED
                ):
                    valid = True
                    json_data = sharepoint_res.json()
                    download_url = json_data["@microsoft.graph.downloadUrl"]
                    sharepoint_id = json_data["id"]
                    _logger.info(f"sharepoint_id: {sharepoint_id}")

                    if attachment.store_fname:
                        db_name = self.env.cr.dbname
                        path_gen = os.path.join(DATA_DIR, "filestore", db_name)
                        file_path = os.path.join(path_gen, attachment.store_fname)
                        _logger.info(file_path)
                        utils.delete_file(file_path)

                    attachment.write(
                        {
                            "url": download_url,
                            "sharepoint_id": sharepoint_id,
                            "type": const.ATTACHMENT_URL_TYPE,
                            "db_datas": False,
                            "store_fname": False,
                        }
                    )
                else:
                    valid = False
            if not sharepoint_res or not valid:
                valid = False
                status_code = None
                message = "cannot request to sharepoint"
                if sharepoint_res:
                    status_code = sharepoint_res.status_code
                    message = sharepoint_res.json()["error"]["message"]
                self.env["log.backup"].create(
                    {
                        "backup_id": backup_id,
                        "status_code": status_code,
                        "message": message,
                        "log_type": const.SHAREPOINT_TYPE,
                        "url": download_url,
                        "attachment_id": attachment.id,
                        "attachment_name": attachment.name,
                    }
                )
            new_cr.commit()
        return valid

    def open_log_wizard(self):
        return {
            "name": "Logs",
            "view_mode": "tree",
            "res_model": "log.backup",
            "domain": [("backup_id", "=", self.id)],
            "type": "ir.actions.act_window",
            "view_id": self.env.ref("backup.log_back_up_view_tree", False).id,
            "target": "new",
        }

    @api.model
    def create(self, vals):
        current_time = datetime.now()
        model_ids = []
        if len(vals["model_ids"][0][2]) > 0:
            model_ids = vals["model_ids"][0][2]
        attachments = self.get_attachments(vals["from_date"], vals["to_date"], model_ids)
        _logger.info(f"length of attachments: {len(attachments)}")
        if len(attachments) == 0:
            raise UserError("No attachments found")

        vals["total_files"] = len(attachments)
        if not vals["executed_at"]:
            new_time = current_time + timedelta(seconds=3)
            new_time = new_time.replace(microsecond=0)
            vals["executed_at"] = str(new_time)

        vals["cron_id"] = str(uuid.uuid4())
        res = super(BackupManagement, self).create(vals)
        executed_at = datetime.strptime(str(vals["executed_at"]), "%Y-%m-%d %H:%M:%S")
        system_params = self.get_system_params()

        self.add_cron(executed_at, attachments, res.id, vals["cron_id"], vals["conflict_behavior"], system_params)
        return res
