import requests
import odoo
from http import HTTPStatus


from . import constants as const

DATA_DIR = odoo.tools.config["data_dir"]


class SharePoint:
    def _get_access_token(self, client_key: str, client_secret: str, tenant_id: str, scope: str):
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload = {
            'grant_type': 'client_credentials',
            'client_id': client_key,
            'client_secret': client_secret,
            'scope': scope,
        }
        response = requests.post(token_url, data=payload)
        if response.status_code == HTTPStatus.OK or response.status_code == HTTPStatus.CREATED:
            return response.json().get('access_token')
        else:
            print(f"Failed to get access token. Status code: {response.status_code}")
            return None

    def upload_file_to_sharepoint(self, path_upload, file_path, client_key: str, client_secret: str, tenant_id: str, scope: str, behavior: str):
        self.token = self._get_access_token(client_key, client_secret, tenant_id, scope)
        access_token = self.token
        conflict_behavior = self.conflict_behavior(behavior)
        res_url = f"{path_upload}:/content{conflict_behavior}"
        print(res_url, "res_url")
        # Read the file content
        with open(file_path, 'rb') as file:
            file_content = file.read()

        # Set up the headers with the access token
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'text/plain',
        }

        # Make the request to upload the file
        response = requests.put(res_url, data=file_content, headers=headers)
        print(response, "response upload")
        return response

    def conflict_behavior(self, state: str):
        print(state, "state")
        behavior = {
            'fail': f"{const.MICROSOFT_CONFLICT_BEHAVIOR}fail",
            'replace': f"{const.MICROSOFT_CONFLICT_BEHAVIOR}replace",
            'rename': f"{const.MICROSOFT_CONFLICT_BEHAVIOR}rename",
        }
        return behavior.get(state, "invalid")

