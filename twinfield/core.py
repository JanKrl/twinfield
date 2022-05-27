import logging
import time
from xml.etree import ElementTree as Et

import requests

from twinfield.login import TwinfieldLogin


class Base(TwinfieldLogin):
    """
    Base class for Twinfield handling static settings (namespaces) and parsing of responses, which follows the same
    logic for each of the modules.
    """

    def __init__(self):

        super().__init__()
        self.namespaces = {
            "env": "http://schemas.xmlsoap.org/soap/envelope/",
            "tw": "http://www.twinfield.com/",
        }

        self.namespaces_txt = {k: "{" + v + "}" for k, v in self.namespaces.items()}

    def send_request(self, browse) -> requests.Response:
        """
        Parameters
        ----------
        browse
            Browse class for the xml request.

        Returns
        -------
        df: pd.DataFrame
            dataframe containing response records.

        """
        success = False
        retry = 1
        while not success:
            if retry > self.max_retries:
                logging.warning(f"Max retries ({self.max_retries}) exceeded, " f"stopping requests for this office.")
                break
            try:
                with requests.post(
                    url=f"{self.cluster}/webservices/processxml.asmx?wsdl",
                    headers={"Content-Type": "text/xml", "Accept-Charset": "utf-8"},
                    data=browse.body(),
                ) as response:
                    output = response
                    success = True
            except ConnectionError:
                logging.info(f"No response, retrying in {self.sec_wait} seconds. Retry number: {retry}")
                time.sleep(self.sec_wait)
                retry += 1

        return output

    def check_invalid_token(self, response: requests.Response) -> bool:
        """
        Checks if the response message is about the token being expired.

        Parameters
        ----------
        response: requests.Response
            response from twinfield server

        Returns
        -------
        True or False, depending on wether the token is expired.

        """
        fault_string = Et.fromstring(response.text).find("env:Body/env:Fault/faultstring", self.namespaces)

        if fault_string:
            # if the there is a faultcode, check if its about the token being expired.
            return fault_string.text == "Access denied. Token invalid."
        else:
            # if not, return False.
            return False
