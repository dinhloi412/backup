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

    def upload_file_to_sharepoint(self, upload_path, file_path, client_key: str, client_secret: str, tenant_id: str, scope: str, behavior: str, datas):
        try:
            self.token = self._get_access_token(client_key, client_secret, tenant_id, scope)
            conflict_behavior = self.conflict_behavior(behavior)
            print(upload_path, "path_upload")
            res_url = f"{upload_path}:/content{conflict_behavior}"
            # Read the file content
            file_content = datas
            if file_path:
                with open(file_path, 'rb') as file:
                    file_content = file.read()
            # Set up the headers with the access token
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'text/plain',
            }

            # Make the request to upload the file
            response = requests.put(res_url, data=file_content, headers=headers)
            print(response, "response upload")
            return response
        except Exception as e:
            return e

    def remove_file_sharepoint(self, sharepoint_id: str, delete_url,client_key, client_secret, tenant_id, scope):
        try:
            test_url = "https://graph.microsoft.com/v1.0/drives/b!IJWKFS9o9ESgbLk8b6sLTph4xN05W3RPuyn_G18c2-igsr8sgTbnQrBcjG-DqtVC"
            res_url = f"{test_url}/items/{sharepoint_id}"
            print(res_url, "res_url")
            self.token = self._get_access_token(client_key, client_secret, tenant_id, scope)
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'text/plain',
            }
            # Make the request to delete the file
            response = requests.delete(url = res_url, headers=headers)
            print(response, "nnnnnnnnnnnnnnnnnnnnnn")
            print(response.json(), "response")
            return response
        except Exception as e:
            return e

    def conflict_behavior(self, state: str):
        behavior = {
            'fail': f"{const.MICROSOFT_CONFLICT_BEHAVIOR}fail",
            'replace': f"{const.MICROSOFT_CONFLICT_BEHAVIOR}replace",
            'rename': f"{const.MICROSOFT_CONFLICT_BEHAVIOR}rename",
        }
        return behavior.get(state, "invalid")

     