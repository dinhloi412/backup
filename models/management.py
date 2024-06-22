import http
import os
import mimetypes
import uuid
import threading

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import odoo
from odoo import fields, models, api
from odoo.exceptions import UserError
from apscheduler.schedulers.background import BackgroundScheduler

from . import utils
from .sharepoint import SharePoint
from . import constants as const

DATA_DIR = odoo.tools.config["data_dir"]


class IrAttachment(models.Model):
    _inherit = "ir.attachment"
    url = fields.Char('url', index=True, size=2048)
    sharepoint_id = fields.Char('sharepoint_id')

    def unlink(self):
        _, client_key, client_secret, tenant_id, _, _, scope, _, drive_url, _ = BackupManagement.get_system_params(self)
        if self.sharepoint_id:
            SharePoint().remove_file_sharepoint(self.sharepoint_id, drive_url, client_key, client_secret, tenant_id,
                                                scope)
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
    year_selection = []
    current_year = datetime.now().year
    for year in range(current_year - 10, current_year + 1):
        year_selection.append((str(year), str(year)))

    name = fields.Char(string="Name", required=True)
    from_year = fields.Selection(year_selection, string="From Year", required=True, default=str(current_year - 1))
    to_year = fields.Selection(year_selection, string="To Year", required=True, default=str(current_year))
    total_files = fields.Integer(string="Total Files")
    total_size = fields.Float(string="Total Size (GB)")
    total_success = fields.Integer(string="Total Success")
    total_time = fields.Char(string="Upload time")
    executed_at = fields.Datetime(string="Execute At")
    is_scheduled = fields.Boolean(string="Scheduled", default=False)
    status = fields.Selection(selection=[
        ('created', 'Created'),
        ('running', 'Running'),
        ('done', 'Done'), ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', required=True,
        default='created')
    cron_id = fields.Char(string="Cron ID")

    model_ids = fields.Many2many("ir.model", string="Model Ids")

    conflict_behavior = fields.Selection(selection=[
        ('fail', 'Fail'),
        ('replace', "Replace"),
        ('rename', 'Rename')
    ], string="Conflict Behavior", required=True, default='rename')
    is_valid = threading.Event()

    # def _get_models(self):
    #     installed_modules = self.sudo().env['ir.module.module'].search([('state', '=', 'installed')])
    #     installed_module_names = list(set(installed_modules.mapped('name')))
    #     models = self.sudo().env['ir.model'].search([])
    #     model_ids = models.filtered(lambda model: model.modules in installed_module_names)
    #     return [(model.model, model.name) for model in model_ids]

    def delete_atts(self):
        data = self.env["ir.attachment"].search([("res_model", "=", "backup.management")])
        for idx in data:
            super(IrAttachment, idx).unlink()
        return

    def _action_notification(self, message: str):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": message,
                "type": 'success',
                "sticky": False
            }
        }

    def _get_cron(self):
        if self.scheduler.get_job(self.cron_id):
            return True
        return False

    def action_migrate(self):
        for b in self:
            from_date, to_date = utils.convert_time(b.from_year, b.to_year)
            res = b._get_cron()
            if res:
                raise UserError("please cancel backup first")
            attachments = b.get_attachments(from_date, to_date, b.model_ids.ids)
            size_bytes = 0
            for idx in attachments:
                if idx["file_size"]:
                    size_bytes += int(idx["file_size"])
            res = utils.convert_bytes_to_gb(size_bytes)

            new_time = datetime.now() + timedelta(seconds=10)
            new_time = new_time.replace(microsecond=0)
            executed_at = datetime.strptime(str(new_time), '%Y-%m-%d %H:%M:%S')

            cron_id = uuid.uuid4()
            domain = {
                "total_size": res,
                "total_files": len(attachments),
                "executed_at": executed_at,
                "status": const.RUNNING_STATUS,
                "cron_id": cron_id,
                "total_success": 0,
            }
            b.update_backup_management(b.id, domain)
            b.add_cron(executed_at, attachments, b.id, str(cron_id), b.conflict_behavior)

    @api.model
    def create(self, vals):
        try:
            # self._get_models()
            current_time = datetime.now()
            from_date = ""
            to_date = ""
            model_ids = []
            if vals["from_year"] and vals["to_year"]:
                from_date, to_date = utils.convert_time(vals["from_year"], vals["to_year"])
            if len(vals["model_ids"][0][2]) > 0:
                model_ids = vals["model_ids"][0][2]
            attachments = self.get_attachments(from_date, to_date, model_ids)
            vals["total_files"] = len(attachments)
            size_bytes = 0
            for idx in attachments:
                if idx["file_size"]:
                    size_bytes += int(idx["file_size"])
            res = utils.convert_bytes_to_gb(size_bytes)
            vals["total_size"] = res
            if vals["executed_at"] != "":
                new_time = current_time + timedelta(seconds=10)
                new_time = new_time.replace(microsecond=0)
                vals["executed_at"] = str(new_time)
            if vals["executed_at"] == "":
                raise UserError("executed_at cannot be empty")
            vals["cron_id"] = str(uuid.uuid4())
            res = super(BackupManagement, self).create(vals)
            executed_at = datetime.strptime(vals["executed_at"], '%Y-%m-%d %H:%M:%S')
            self.add_cron(executed_at, attachments, res.id, vals["cron_id"], vals["conflict_behavior"])
            return res
        except Exception as e:
            raise UserError(f"something went wrong: {e}")

    def action_cancel_cron(self):
        try:
            for i in self:
                if i.scheduler.get_job(i.cron_id) is not None:
                    i.scheduler.remove_job(i.cron_id)
                i.status = const.CANCELED_STATUS
            self.is_valid.set()
            return True
        except Exception as e:
            raise UserError(f"cannot cancel cron: {e}")

    def get_attachments(self, from_date: str, to_date: str, model_ids: list):
        try:
            converted_str = utils.convert_query_db(const.EXCEPT_EXTENSION)
            query = """select * from ir_attachment where type = '%s' and mimetype not in (%s)""" % (
                const.ATTACHMENT_BINAYRY_TYPE, converted_str)
            if from_date != "" and to_date != "":
                query += """ AND ir_attachment.create_date >= '%s' AND ir_attachment.create_date <= '%s'""" % (
                    from_date, to_date)

            if len(model_ids) > 0:
                models_name = self.get_model_name(model_ids)
                if len(models_name) > 0:
                    converted_str = utils.convert_query_db(models_name)
                    query += """ AND ir_attachment.res_model in (%s)""" % converted_str
            self.env.cr.execute(query)
            attrs = self.env.cr.dictfetchall()
            return attrs
        except Exception as e:
            return f"cannot get attachments: {e}"

    def get_model_name(self, ids: list):
        try:
            models_name = self.env["ir.model"].search([("id", "in", ids)])
            names = [x["model"] for x in models_name]
            return names
        except Exception as e:
            return e

    def update_backup_management(self, backup_id: int, data: dict):
        try:
            backup_management = self.env[self._name].browse(backup_id)
            if backup_management:
                backup_management.write(data)
            self.env.cr.commit()
        except Exception as e:
            print(f"Error updating backup management: {e}")
            raise Exception(f"Error updating backup management: {e}")

    def update_atts(self, id: int, url: str, sharepoint_id: str):
        try:
            null_value = 'NULL'
            query = """update %s set url = '%s', type = '%s', store_fname = '%s', db_datas = %s, sharepoint_id = '%s' where id = %s """ % (
                const.ATTACHMENT_TABLE_NAME, url, const.ATTACHMENT_URL_TYPE, "", null_value, sharepoint_id, id)
            self.sudo().env.cr.execute(query)
            return True
        except Exception as e:
            print(f"Error updating attachments: {e}")
            return f"Error updating attachments: {e}"

    @api.constrains('from_year', 'to_year')
    def _check_years_order(self):
        for record in self:
            if int(record.from_year) >= int(record.to_year):
                raise UserError("From Year must be less than To Year!")

    def add_cron(self, executed_at, data: list, backup_id: int, cron_id: str, behavior: str):
        self.scheduler.add_job(self.sharepoint_upload, trigger="date",
                               run_date=datetime(int(executed_at.year), int(executed_at.month), int(executed_at.day),
                                                 int(executed_at.hour), int(executed_at.minute),
                                                 int(executed_at.second)),
                               args=[data, backup_id, behavior],
                               id=cron_id)
        if self.scheduler.state == 0:
            self.scheduler.start()

    def sharepoint_upload(self, data: list, backup_id: int, behavior: str):
        new_cr = self.pool.cursor()
        start_time = datetime.now()
        try:
            # new_env = self.sudo().env(cr=new_cr)
            self = self.with_env(self.env(cr=new_cr))
            host_name, client_key, client_secret, tenant_id, _, upload_url, scope, threads, drive_url, root_folder = self.get_system_params()
            update_record = {"status": const.RUNNING_STATUS}
            self.update_backup_management(backup_id, update_record)  # update status -> running
            db_name = self.env.cr.dbname
            processes = []
            # url_test2 = "https://graph.microsoft.com/v1.0/drives/b!IJWKFS9o9ESgbLk8b6sLTph4xN05W3RPuyn_G18c2-igsr8sgTbnQrBcjG-DqtVC/root:/TestFolder"
            upload_url = f"{drive_url}/root:/{root_folder}"
            path_gen = os.path.join(DATA_DIR, "filestore", db_name)
            total_success = 0
            with ThreadPoolExecutor(max_workers=int(threads)) as executor:
                for attachment in data:
                    if self.is_valid.is_set():
                        break
                    processes.append(
                        executor.submit(self.handle_request_sharepoint, path_gen, attachment['store_fname'],
                                        attachment["name"], attachment["mimetype"], attachment["create_date"],
                                        attachment["res_model"], upload_url, host_name, client_key, client_secret,
                                        tenant_id, scope, behavior, attachment["id"], backup_id,
                                        attachment["db_datas"], attachment["checksum"]))
            for process in as_completed(processes):
                if self.is_valid.is_set():
                    break
                result = process.result()
                if result:
                    total_success += 1
            if not self.is_valid.is_set():
                total_time = datetime.now() - start_time
                update_record = {"status": const.DONE_STATUS, "total_success": total_success,
                                 "total_time": utils.convert_time_measure(total_time)}
                self.update_backup_management(backup_id, update_record)  # update status -> finished
            return
        except Exception as e:
            print(f"something went wrong: {e}")
        finally:
            new_cr.close()  # Closing the cursor when done
        return True

    def get_system_params(self):
        sys_params = self.env['ir.config_parameter'].sudo()
        host_name = utils.get_host_name(sys_params.get_param('web.base.url'))
        client_key = sys_params.get_param('sharepoint.client_key')
        client_secret = sys_params.get_param('sharepoint.client_secret')
        tenant_id = sys_params.get_param('sharepoint.tenant_id')
        upload_url = sys_params.get_param('sharepoint.upload_url')
        site_url = sys_params.get_param('sharepoint.site_url')
        scope = sys_params.get_param('sharepoint.scope')
        threads = sys_params.get_param('sharepoint.threads')
        drive_url = sys_params.get_param('sharepoint.drive_url')
        root_folder = sys_params.get_param('sharepoint.root_folder')

        return host_name, client_key, client_secret, tenant_id, site_url, upload_url, scope, threads, drive_url, root_folder

    def handle_request_sharepoint(self, path_gen: str, store_fname: str, name: str, mimetype, create_date: datetime,
                                  res_model: str, upload_url, host_name, client_key, client_secret, tenant_id, scope,
                                  behavior, attachment_id: int, backup_id: str, db_datas, checksum: str):
        try:
            if self.is_valid.is_set():
                return
            file_content = db_datas
            file_path = None
            if store_fname:
                file_path = os.path.join(path_gen, store_fname)
                file_content = utils.read_file(file_path)
                if not file_content:
                    atts = self.env[const.ATTACHMENT_MODEL].search(
                        [("checksum", "=", checksum), ("type", "=", const.ATTACHMENT_URL_TYPE)])
                    self.update_atts(attachment_id, atts[0]["url"], atts[0]["sharepoint_id"])
                    return True
            # extension = mimetypes.guess_extension(mimetype)
            year = utils.get_year(str(create_date))
            upload_path = f"{upload_url}/{host_name}/{res_model}/{year}/{name}"
            print(upload_path, "upload_path")

            sharepoint_res = SharePoint().upload_file_to_sharepoint(upload_path, file_path, client_key,
                                                                    client_secret, tenant_id, scope, behavior,
                                                                    file_content)
            download_url = None
            if sharepoint_res.status_code == http.HTTPStatus.OK or sharepoint_res.status_code == http.HTTPStatus.CREATED:
                json_data = sharepoint_res.json()
                download_url = json_data["@microsoft.graph.downloadUrl"]
                sharepoint_id = json_data["id"]
                self.update_atts(attachment_id, download_url, sharepoint_id)
                if store_fname:
                    utils.delete_file(file_path)
                return True
            self.env["log.backup"].create({
                'backup_id': backup_id,
                "status_code": sharepoint_res.status_code,
                "message": sharepoint_res.json()["error"]["message"],
                "log_type": const.SHAREPOINT_TYPE,
                "url": download_url,
                "attachment_name": name,
            })
            self.env.cr.commit()
            return False
        except Exception as e:
            return e

    def open_log_wizard(self):
        return {
            'name': "Logs",
            'view_mode': 'tree',
            'res_model': 'log.backup',
            'domain': [('backup_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'view_id': self.env.ref("backup.log_back_up_view_tree", False).id,
            'target': 'new'
        }
