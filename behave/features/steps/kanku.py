#!/usr/bin/python3


import os
import re
import subprocess

import behave
from ruamel.yaml import YAML


class Kanku:
    def __init__(self, context, kankufile):
        self.kankufile = kankufile
        self.kankudir = os.path.dirname(self.kankufile)
        self.domain_name = self._get_domain_name()
        self.ip = self._get_ip()

    def _get_domain_name(self):
        """
        Get domain name directly from KankuFile yaml
        """
        yaml = YAML(typ='safe')
        doc = yaml.load(open(self.kankufile, "r"))
        return doc["domain_name"]

    def _run_kanku(self, args):
        cmd = ["kanku"] + args
        env = os.environ.copy()
        env["KANKU_CONFIG"] = self.kankufile
        proc = subprocess.Popen(
            cmd,
            cwd=self.kankudir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8"
        )
        return proc

    def _get_ip(self):
        """
        Get IP from calling `kanku ip`
        """
        proc = self._run_kanku(["ip"])
        stdout, stderr = proc.communicate()
        match = re.search(r"IP Address: ([\d\.]+)", stderr)
        return match.group(1)

    def create_snapshot(self):
        # unmount /tmp/kanku so we are able to create a snapshot of the VM
        self.run_command("umount /tmp/kanku")
        proc = self._run_kanku(["snapshot", "--create", "--name", "current"])
        proc.communicate()

    def revert_to_snapshot(self):
        proc = self._run_kanku(["snapshot", "--revert", "--name", "current"])
        proc.communicate()

    def delete_snapshot(self):
        proc = self._run_kanku(["snapshot", "--remove", "--name", "current"])
        proc.communicate()

    def run_command(self, ssh_cmd, user="root"):
        proc = self._run_kanku(["ssh", "-u", user, "--execute", ssh_cmd])
        proc.wait()


@behave.step("I create VM snapshot")
def func(context, args):
    context.kanku.create_snapshot(sudo=True)


@behave.step("I revert to VM snapshot")
def func(context, args):
    context.kanku.revert_to_snapshot(sudo=True)
