import subprocess

from steps.common import debug


class Podman:
    def __init__(self, context):
        self.context = context
        debug(context, "Podman.__init__()")
        self.container_id = None
        self.start()

    def __del__(self):
        try:
            self.kill()
        except Exception:
            pass

    def _run(self, args, check=True):
        cmd = ["podman"] + args
        debug(self.context, "Running command:", cmd)
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=check,
        )
        debug(self.context, "> return code:", proc.returncode)
        debug(self.context, "> stdout:", proc.stdout)
        debug(self.context, "> stderr:", proc.stderr)
        return proc

    def start(self):
        debug(self.context, "Podman.start()")
        args = [
            "run",
            "--name", "obs-server-behave",
            "--hostname", "obs-server-behave",
            "--replace",
            "--rm",
            "--detach",
            "--interactive",
            "--tty",
            "-p", "443",
            "obs-server"
        ]
        proc = self._run(args)
        lines = proc.stdout.strip().splitlines()
        self.container_id = lines[-1]
        self.wait_on_systemd()
        self.port = self.get_port()

    def kill(self):
        if not self.container_id:
            return
        debug(self.context, "Podman.kill()")
        args = ["kill", self.container_id]
        self._run(args)
        self.container_id = None

    def restart(self):
        debug(self.context, "Podman.restart()")
        self.kill()
        self.start()

    def wait_on_systemd(self):
        args = [
            "exec",
            self.container_id,
            "/usr/bin/systemctl", "is-system-running", "--wait"
        ]
        self._run(args, check=False)

    def get_port(self):
        args = ["port", self.container_id]
        proc = self._run(args)
        lines = proc.stdout.strip().splitlines()
        for line in lines:
            if line.startswith("443/tcp"):
                # return <port> from: "443/tcp -> 0.0.0.0:<port>"
                return line.split(":")[-1]
        raise RuntimeError(f"Could not determine port of container {self.container_id}")
