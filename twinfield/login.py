import base64
import json
import logging
import os
import time

import requests

from twinfield.exceptions import EnvironmentVariablesError, LoginSessionError


class TwinfieldLogin:
    def __init__(self):
        self.organisation = os.environ.get("TWINFIELD_ORGANISATION")
        self.client_id = os.environ.get("TWINFIELD_CLIENT_ID")
        self.client_secret = os.environ.get("TWINFIELD_CLIENT_SECRET")
        self.refresh_token = os.environ.get("TWINFIELD_REFRESH_TOKEN")
        self.check_environment_variables()

        self.header = self.create_authorization_header()
        self.cluster = self.determine_cluster()
        self.max_retries = 5
        self.sec_wait = 10
        self.access_token = self.refresh_access_token()

    def check_environment_variables(self):
        # Test if environment variables are set for Twinfield login

        if not all([self.client_id, self.client_secret, self.organisation, self.refresh_token]):
            raise EnvironmentVariablesError(
                "One of the environment variables TWINFIELD_CLIENT_ID, TWINFIELD_CLIENT_SECRET, "
                "TWINFIELD_ORGANISATION or TWINFIELD_REFRESH_TOKEN is not set"
            )

    def create_authorization_header(self):
        # encode client_id en client_secret to be send as an authorization header in the request.
        raw = f"{self.client_id}:{self.client_secret}".encode("ascii")
        base64_credentials = base64.b64encode(raw).decode("ascii")
        header = {"Content-Type": "application/x-www-form-urlencoded ", "Authorization": f"Basic {base64_credentials}"}

        return header

    def refresh_access_token(self):
        url = "https://login.twinfield.com/auth/authentication/connect/token"
        data = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}
        response = self.do_retry_request(url=url, headers=self.header, data=data, special_error=LoginSessionError)
        json_data = json.loads(response.text)
        access_token = json_data.get("access_token")
        return access_token

    def determine_cluster(self):
        access_token = self.refresh_access_token()
        url = f"https://login.twinfield.com/auth/authentication/connect/accesstokenvalidation?token={access_token}"
        response = self.do_retry_request(url=url, headers=self.header, req_type="GET")
        json_data = json.loads(response.text)
        cluster = json_data.get("twf.clusterUrl")
        return cluster

    def do_retry_request(self, url, headers, data=None, special_error=None, req_type="POST"):
        success = False
        retry = 1
        if req_type not in ["POST", "GET"]:
            raise ValueError(f"{req_type} is not a valid requests type.")
        if req_type == "POST" and not data:
            raise ValueError("Parameter data is not given while req_type POST")
        while not success:
            if retry > self.max_retries:
                logging.warning(f"Max retries ({self.max_retries}) exceeded, stopping requests for this office.")
                break
            try:
                if req_type == "POST":
                    with requests.post(url=url, headers=headers, data=data) as response:
                        if not response and special_error:
                            raise special_error
                        output = response
                else:
                    with requests.get(url=url, headers=headers) as response:
                        if not response and special_error:
                            raise special_error
                        output = response
                success = True
            except ConnectionError:
                self.access_token = self.refresh_access_token()
                logging.info(f"No response, retrying in {self.sec_wait} seconds. Retry number: {retry}")
                time.sleep(self.sec_wait)
                retry += 1
        return output
