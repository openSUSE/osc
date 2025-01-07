import hashlib
import os
import shutil
import tempfile
import time
from typing import Optional
from urllib.error import HTTPError
from urllib.parse import urlparse

from .. import oscerr
from .. import output
from ..util.xml import ET


class Serviceinfo:
    """Source service content
    """

    def __init__(self):
        """creates an empty serviceinfo instance"""
        self.services = []
        self.apiurl: Optional[str] = None
        self.project: Optional[str] = None
        self.package: Optional[str] = None

    def read(self, serviceinfo_node, append=False):
        """read in the source services ``<services>`` element passed as
        elementtree node.
        """
        def error(msg, xml):
            from ..core import ET_ENCODING
            data = f'invalid service format:\n{ET.tostring(xml, encoding=ET_ENCODING)}'
            raise ValueError(f"{data}\n\n{msg}")

        if serviceinfo_node is None:
            return
        if not append:
            self.services = []
        services = serviceinfo_node.findall('service')

        for service in services:
            name = service.get('name')
            if name is None:
                error("invalid service definition. Attribute name missing.", service)
            if len(name) < 3 or '/' in name:
                error(f"invalid service name: {name}", service)
            mode = service.get('mode', '')
            data = {'name': name, 'mode': mode}
            command = [name]
            for param in service.findall('param'):
                option = param.get('name')
                if option is None:
                    error(f"{name}: a parameter requires a name", service)
                value = ''
                if param.text:
                    value = param.text
                command.append('--' + option)
                # hmm is this reasonable or do we want to allow real
                # options (e.g., "--force" (without an argument)) as well?
                command.append(value)
            data['command'] = command
            self.services.append(data)

    def getProjectGlobalServices(self, apiurl: str, project: str, package: str):
        from ..core import http_POST
        from ..core import makeurl
        from ..util.xml import xml_parse

        self.apiurl = apiurl
        # get all project wide services in one file, we don't store it yet
        u = makeurl(apiurl, ["source", project, package], query={"cmd": "getprojectservices"})
        try:
            f = http_POST(u)
            root = xml_parse(f).getroot()
            self.read(root, True)
            self.project = project
            self.package = package
        except HTTPError as e:
            if e.code == 404 and package != '_project':
                self.getProjectGlobalServices(apiurl, project, '_project')
                self.package = package
            elif e.code != 403 and e.code != 400:
                raise e

    def addVerifyFile(self, serviceinfo_node, filename: str):
        f = open(filename, 'rb')
        digest = hashlib.sha256(f.read()).hexdigest()
        f.close()

        r = serviceinfo_node
        s = ET.Element("service", name="verify_file")
        ET.SubElement(s, "param", name="file").text = filename
        ET.SubElement(s, "param", name="verifier").text = "sha256"
        ET.SubElement(s, "param", name="checksum").text = digest

        r.append(s)
        return r

    def addDownloadUrl(self, serviceinfo_node, url_string: str):
        url = urlparse(url_string)
        protocol = url.scheme
        host = url.netloc
        path = url.path

        r = serviceinfo_node
        s = ET.Element("service", name="download_url")
        ET.SubElement(s, "param", name="protocol").text = protocol
        ET.SubElement(s, "param", name="host").text = host
        ET.SubElement(s, "param", name="path").text = path

        r.append(s)
        return r

    def addSetVersion(self, serviceinfo_node):
        r = serviceinfo_node
        s = ET.Element("service", name="set_version", mode="buildtime")
        r.append(s)
        return r

    def addGitUrl(self, serviceinfo_node, url_string: Optional[str]):
        r = serviceinfo_node
        s = ET.Element("service", name="obs_scm")
        ET.SubElement(s, "param", name="url").text = url_string
        ET.SubElement(s, "param", name="scm").text = "git"
        r.append(s)
        return r

    def addTarUp(self, serviceinfo_node):
        r = serviceinfo_node
        s = ET.Element("service", name="tar", mode="buildtime")
        r.append(s)
        return r

    def addRecompressTar(self, serviceinfo_node):
        r = serviceinfo_node
        s = ET.Element("service", name="recompress", mode="buildtime")
        ET.SubElement(s, "param", name="file").text = "*.tar"
        ET.SubElement(s, "param", name="compression").text = "xz"
        r.append(s)
        return r

    def execute(self, dir, callmode: Optional[str] = None, singleservice=None, verbose: Optional[bool] = None):
        old_dir = os.path.join(dir, '.old')

        # if 2 osc instances are executed at a time one, of them fails on .old file existence
        # sleep up to 10 seconds until we can create the directory
        for i in reversed(range(10)):
            try:
                os.mkdir(old_dir)
                break
            except FileExistsError:
                time.sleep(1)

            if i == 0:
                msg = f'"{old_dir}" exists, please remove it'
                raise oscerr.OscIOError(None, msg)

        try:
            result = self._execute(dir, old_dir, callmode, singleservice, verbose)
        finally:
            shutil.rmtree(old_dir)
        return result

    def _execute(
        self, dir, old_dir, callmode: Optional[str] = None, singleservice=None, verbose: Optional[bool] = None
    ):
        from ..core import get_osc_version
        from ..core import run_external
        from ..core import vc_export_env

        # cleanup existing generated files
        for filename in os.listdir(dir):
            if filename.startswith('_service:') or filename.startswith('_service_'):
                os.rename(os.path.join(dir, filename),
                          os.path.join(old_dir, filename))

        allservices = self.services or []
        service_names = [s['name'] for s in allservices]
        if singleservice and singleservice not in service_names:
            # set array to the manual specified singleservice, if it is not part of _service file
            data = {'name': singleservice, 'command': [singleservice], 'mode': callmode}
            allservices = [data]
        elif singleservice:
            allservices = [s for s in allservices if s['name'] == singleservice]
            # set the right called mode or the service would be skipped below
            for s in allservices:
                s['mode'] = callmode

        if not allservices:
            # short-circuit to avoid a potential http request in vc_export_env
            # (if there are no services to execute this http request is
            # useless)
            return 0

        # services can detect that they run via osc this way
        os.putenv("OSC_VERSION", get_osc_version())

        # set environment when using OBS 2.3 or later
        if self.project is not None:
            # These need to be kept in sync with bs_service
            os.putenv("OBS_SERVICE_APIURL", self.apiurl)
            os.putenv("OBS_SERVICE_PROJECT", self.project)
            os.putenv("OBS_SERVICE_PACKAGE", self.package)
            # also export vc env vars (some services (like obs_scm) use them)
            vc_export_env(self.apiurl)

        # recreate files
        ret = 0
        for service in allservices:
            if callmode != "all":
                if service['mode'] == "buildtime":
                    continue
                if service['mode'] == "serveronly" and callmode != "local":
                    continue
                if service['mode'] == "manual" and callmode != "manual":
                    continue
                if service['mode'] != "manual" and callmode == "manual":
                    continue
                if service['mode'] == "disabled" and callmode != "disabled":
                    continue
                if service['mode'] != "disabled" and callmode == "disabled":
                    continue
                if service['mode'] != "trylocal" and service['mode'] != "localonly" and callmode == "trylocal":
                    continue
            temp_dir = None
            try:
                temp_dir = tempfile.mkdtemp(dir=dir, suffix=f".{service['name']}.service")
                cmd = service['command']
                if not os.path.exists("/usr/lib/obs/service/" + cmd[0]):
                    raise oscerr.PackageNotInstalled(f"obs-service-{cmd[0]}")
                cmd[0] = "/usr/lib/obs/service/" + cmd[0]
                cmd = cmd + ["--outdir", temp_dir]
                output.print_msg(f"Running source_service '{service['name']}' ...", print_to="stdout")
                output.print_msg("Run source service:", " ".join(cmd), print_to="verbose")
                r = run_external(*cmd)

                if r != 0:
                    print("Aborting: service call failed: ", ' '.join(cmd))
                    # FIXME: addDownloadUrlService calls si.execute after
                    #        updating _services.
                    return r

                if service['mode'] == "manual" or service['mode'] == "disabled" or service['mode'] == "trylocal" or service['mode'] == "localonly" or callmode == "local" or callmode == "trylocal" or callmode == "all":
                    for filename in os.listdir(temp_dir):
                        os.rename(os.path.join(temp_dir, filename), os.path.join(dir, filename))
                else:
                    name = service['name']
                    for filename in os.listdir(temp_dir):
                        os.rename(os.path.join(temp_dir, filename), os.path.join(dir, "_service:" + name + ":" + filename))
            finally:
                if temp_dir is not None:
                    shutil.rmtree(temp_dir)

        return 0
