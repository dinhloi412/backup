import os
import logging
import requests
import odoo
import base64
from http import HTTPStatus


from . import constants as const

DATA_DIR = odoo.tools.config["data_dir"]

_logger = logging.getLogger(__name__)


class SharePoint:
    def _get_access_token(self, client_key: str, client_secret: str, tenant_id: str, scope: str):
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_key,
            "client_secret": client_secret,
            "scope": scope,
        }
        response = requests.post(token_url, data=payload)
        if response.status_code == HTTPStatus.OK or response.status_code == HTTPStatus.CREATED:
            return response.json().get("access_token")
        else:
            _logger.error(f"Failed to get access token. Status code: {response.status_code}")
            return None

    def upload_file_to_sharepoint(self, upload_path, client_key: str, client_secret: str, tenant_id: str, scope: str, behavior: str, file_content):
        try:
            self.token = self._get_access_token(
                client_key, client_secret, tenant_id, scope
            )
            conflict_behavior = self.conflict_behavior(behavior)
            res_url = f"{upload_path}:/content{conflict_behavior}"
            headers = {"Authorization": f"Bearer {self.token}"}

            # Make the request to upload the file
            data_to_send = base64.b64decode(file_content)

            response = requests.put(res_url, data=data_to_send, headers=headers, timeout=30)
            _logger.info(f"{response} : response upload")
            return response
        except Exception as e:
            _logger.error(f"error uploading file in sharepoint: {e}")
            # raise Exception(e)

    def remove_file_sharepoint(self, sharepoint_id: str, drive_url, client_key, client_secret, tenant_id, scope):
        try:
            res_url = f"{drive_url}/items/{sharepoint_id}"
            _logger.info(f"{res_url} : res_url")
            self.token = self._get_access_token(client_key, client_secret, tenant_id, scope)
            headers = {"Authorization": f"Bearer {self.token}",}

            # Make the request to delete the file
            response = requests.delete(url=res_url, headers=headers)
            return response
        except Exception as e:
            _logger.error(f"error remove file in sharepoint: {e}")

    def get_file(self, sharepoint_id: str, drive_url, client_key, client_secret, tenant_id, scope):
        try:
            res_url = f"{drive_url}/items/{sharepoint_id}"
            self.token = self._get_access_token(client_key, client_secret, tenant_id, scope)
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.get(url=res_url, headers=headers)
            return response
        except Exception as e:
            _logger.error(f"error get file in sharepoint: {e}")
        
    def conflict_behavior(self, state: str):
        behavior = {
            "fail": f"{const.MICROSOFT_CONFLICT_BEHAVIOR}fail",
            "replace": f"{const.MICROSOFT_CONFLICT_BEHAVIOR}replace",
            "rename": f"{const.MICROSOFT_CONFLICT_BEHAVIOR}rename",
        }
        return behavior.get(state, "invalid")
