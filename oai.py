# -*- coding: utf-8 -*-

import datetime
import logging
import lxml.html
import re
import requests
import tempfile
import zipfile
from lxml import etree
from pathlib import Path
from typing import Generator


def secure_filename_from_datetime(dt: datetime.datetime) -> str:
    # Format the datetime object as a string
    formatted_datetime = dt.strftime("%Y-%m-%d_%H-%M-%S")

    # Replace any characters that are not alphanumeric, underscores, dots, or hyphens
    safe_filename = formatted_datetime.replace(" ", "_").replace(":", "-")

    return safe_filename


def secure_filename(input_str: str) -> str:
    clist = (
        " ",
        ":",
        ".",
        "/",
    )

    safe_str = input_str
    for char in clist:
        safe_str = safe_str.replace(char, "_")

    # Remove any characters that are not alphanumeric, underscores, dots, or hyphens
    safe_str = re.sub(r"[^\w.-]", "", safe_str)

    # Limit the length of the filename
    max_length = 255  # Adjust according to the file system's limitations
    safe_str = safe_str[:max_length]

    return safe_str


class OAIClient:
    def __init__(
        self,
        base_url: str,
        metadata_prefix: str = "oai_dc",
        from_date: str | None = None,
        until_date: str | None = None,
        set_spec: str | None = None,
    ):
        self.base_url = base_url
        self.metadata_prefix = metadata_prefix
        self.from_date = from_date
        self.until_date = until_date
        self.set_spec = set_spec
        self.resumption_token = None

        self.__response__ = None
        self.__numrecords__ = None

    def fetch_records(self) -> Generator[etree._Element, None, None]:
        logger = logging.getLogger(__name__)
        params = self._build_params("ListRecords")

        while True:
            response = self._make_request(params)

            try:
                root = etree.fromstring(response.content)
                for record in root.findall(
                    ".//{http://www.openarchives.org/OAI/2.0/}record"
                ):
                    yield record

                self.resumption_token = root.find(
                    ".//{http://www.openarchives.org/OAI/2.0/}resumptionToken"
                )

            except etree.XMLSyntaxError:
                logger.error("", exc_info=True)
                self.resumption_token = None

                root = lxml.html.fromstring(response.content)

                for item in root.iter():
                    if item.tag == "resumptiontoken":
                        self.resumption_token = item

            if self.resumption_token is None:
                break

            if self.resumption_token.text is None:
                break

            params = self._build_params(
                "ListRecords", resumption_token=self.resumption_token.text
            )

    def get_complete_list_size(self) -> int:
        """Gesamtzahl aller Artikel

        Returns:
            int: Gesatmzahl
        """
        if isinstance(self.__numrecords__, int):
            return self.__numrecords__

        params = self._build_params("ListRecords")

        num_found = 0

        response = self._make_request(params)

        try:
            root = etree.fromstring(response.content)
            resumptionToken = root.find(
                ".//{http://www.openarchives.org/OAI/2.0/}resumptionToken"
            )

            if resumptionToken is None:
                nodes = root.findall(".//{http://www.openarchives.org/OAI/2.0/}record")
                num_found = len(nodes)
            else:
                num_found = int(resumptionToken.attrib.get("completeListSize", "0"))
        except etree.XMLSyntaxError:
            root = lxml.html.fromstring(response.content)

            for item in root.iter():
                if item.tag == "resumptiontoken":
                    num_found = int(item.attrib.get("completelistsize", "0"))

        self.__numrecords__ = num_found
        return self.__numrecords__

    def _build_params(self, verb: str, resumption_token: str | None = None) -> dict:
        params = {"verb": verb}

        if resumption_token is not None:
            params["resumptionToken"] = resumption_token
            return params

        params["metadataPrefix"] = self.metadata_prefix

        if self.from_date:
            params["from"] = self.from_date
        if self.until_date:
            params["until"] = self.until_date
        if self.set_spec:
            params["set"] = self.set_spec

        return params

    def _make_request(self, params: dict) -> requests.Response:
        logger = logging.getLogger(__name__)

        logger.debug((self.base_url, params))

        self.__response__ = requests.get(self.base_url, params=params)

        if self.__response__.status_code != 200:
            raise TypeError(
                f"Failed to fetch records ({self.base_url}). Status Code: {
                    self.__response__.status_code
                }"
            )

        return self.__response__


def zipper(
    oai_url: str,
    destination: str,
    from_date: str | None = None,
    until_date: str | None = None,
    metadata_prefix: str = "oai_dc",
    spec: str | None = None,
    max_files_in_archive: int = 50_000,
    filename_prefix: str | None = None,
) -> dict:
    """Führt eine OAI Abfrage aus

    Führt eine OAI Abfrage aus und erstellt für jeden Record eine XML-Datei.
    Diese XML-Dateien, werden dann in ZIP Archive aufgeteilt, je
    {max_files_in_archive} pro Archiv.

    Args:
        oai_url (str): URL des OAI Repository
        destination (Path): Pfad zum Ablageordner
        from_date (str | None, optional): OAI Request Option: from. Defaults to None.
        until_date (str| None, optional): OAI Request Option: until. Defaults to None.
        metadata_prefix (str): OAI Request Option: Metadata Format
        spec (str | None, optional): OAI Request Option: set. Defaults to None.
        max_files_in_archive (int | None, optional): Maximal Anzahl von XML-Dateien pro Archiv. Defaults to 50.000.
        filename_prefix (str | None, optional): Präfix für den Namen des ZIP-Archivs.

    Returns:
        dict: Angaben über die Artikel
    """
    logger = logging.getLogger(__name__)

    result = {"num_found": 0, "num_received": 0, "filenames": []}

    nss = {"oai": "http://www.openarchives.org/OAI/2.0/"}

    stms = {"identifier": f"./{{{nss['oai']}}}header/{{{nss['oai']}}}identifier"}

    destpath = Path(destination)
    destpath.mkdir(exist_ok=True)

    now = datetime.datetime.now()

    oai_client = OAIClient(
        oai_url,
        set_spec=spec,
        from_date=from_date,
        until_date=until_date,
        metadata_prefix=metadata_prefix,
    )

    try:
        num_found = oai_client.get_complete_list_size()
    except Exception:
        logger.error("", exc_info=True)
        return result

    logger.info(f"{oai_url}: {num_found} Artikel")
    result["num_found"] = num_found

    if num_found == 0:
        return result

    num_articles = 0
    num_zip = 1

    if filename_prefix is None:
        filename_prefix = f"{secure_filename_from_datetime(now)}"

    zname = f"{filename_prefix}-{num_zip:03}.zip"
    zpath = destpath / zname

    result["filenames"].append(zname)

    zfh = zipfile.ZipFile(zpath, "w")
    try:
        for i, node in enumerate(oai_client.fetch_records()):
            inode = node.find(stms["identifier"])

            if inode is None:
                continue

            if num_articles > 0 and num_articles % 100 == 0:
                logger.info(f"{oai_url}: {num_articles}/{num_found} Artikel")

            if num_articles > 0 and num_articles % max_files_in_archive == 0:
                zfh.close()

                num_zip += 1
                zname = f"{filename_prefix}-{num_zip:03}.zip"
                zpath = destpath / zname

                result["filenames"].append(zname)

                zfh = zipfile.ZipFile(zpath, "w")

            identifier = inode.text

            fname = f"{secure_filename(identifier)}.xml"

            with tempfile.NamedTemporaryFile("wb") as xfh:
                xfh.write(etree.tostring(node, encoding="UTF-8", xml_declaration=True))
                xfh.seek(0)
                zfh.write(xfh.name, fname)

            num_articles += 1
            result["num_received"] += 1
        zfh.close()
    except Exception:
        logger.error("", exc_info=True)

        for fname in result["filenames"]:
            fpath = destpath / fname
            if fpath.exists():
                fpath.unlink()

        result["filenames"] = []
        return result

    return result
