import contextlib
import queue
import socket
import subprocess
import threading

import behave

from steps.common import debug


@contextlib.contextmanager
def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        s.listen()
        port = s.getsockname()[1]
        yield port


class Podman:
    def __init__(self, context, container_name):
        self.context = context
        self.container_name = container_name
        self.container = None
        debug(self.context, "Podman.__init__()")

        self.new_container()

    def __del__(self):
        debug(self.context, "Podman.__del__()")
        try:
            self.kill()
        except Exception:
            pass

    def kill(self):
        debug(self.context, "Podman.kill()")
        if not self.container:
            return
        self.container.kill()
        self.container = None

    def new_container(self):
        debug(self.context, "Podman.new_container()")
        # no need to stop the running container
        # becuse the new container replaces an old container with the identical name
        self.container = Container(self.context, name=self.container_name)
        self.container.wait_on_systemd()
        debug(self.context, f"> {self.container}")


class ThreadedPodman:
    def __init__(self, context, container_name_prefix, max_containers=1):
        self.context = context
        self.container = None
        debug(self.context, "ThreadedPodman.__init__()")

        self.max_containers = max_containers
        self.container_name_prefix = container_name_prefix
        self.container_name_num = 0

        # produce new containers
        self.container_producer_queue = queue.Queue(maxsize=self.max_containers)
        self.container_producer_queue_is_stopping = threading.Event()
        self.container_producer_queue_is_stopped = threading.Event()
        self.container_producer_thread = threading.Thread(target=self.container_producer, daemon=True)
        self.container_producer_thread.start()

        # consume (kill) used containers
        self.container_consumer_queue = queue.Queue()
        self.container_consumer_thread = threading.Thread(target=self.container_consumer, daemon=True)
        self.container_consumer_thread.start()

        self.new_container()

    def __del__(self):
        debug(self.context, "ThreadedPodman.__del__()")
        try:
            self.kill()
        except Exception:
            pass

    def kill(self):
        debug(self.context, "ThreadedPodman.kill()")
        self.container_producer_queue_is_stopping.set()

        container = getattr(self, "container", None)
        if container:
            self.container_consumer_queue.put(container)
            self.container = None

        while not self.container_producer_queue_is_stopped.is_set():
            try:
                container = self.container_producer_queue.get(block=True, timeout=1)
                self.container_consumer_queue.put(container)
            except queue.Empty:
                continue

        # 'None' is a signal to finish processing the queue
        self.container_consumer_queue.put(None)

        self.container_producer_thread.join()
        self.container_consumer_thread.join()

    def container_producer(self):
        while not self.container_producer_queue_is_stopping.is_set():
            if self.container_name_prefix:
                self.container_name_num += 1
                container_name = f"{self.container_name_prefix}{self.container_name_num}"
            else:
                container_name = None
            container = Container(self.context, name=container_name)
            debug(self.context, f"ThreadedPodman.container_producer() - container created: {self.container_name_num}")
            self.container_producer_queue.put(container, block=True)
        self.container_producer_queue_is_stopped.set()

    def container_consumer(self):
        while True:
            container = self.container_consumer_queue.get(block=True)
            if container is None:
                break
            container.kill()

    def new_container(self):
        debug(self.context, "ThreadedPodman.new_container()")
        if getattr(self, "container", None):
            self.container_consumer_queue.put(self.container)
        self.container = self.container_producer_queue.get(block=True)
        self.container.wait_on_systemd()
        debug(self.context, f"> {self.container}")


class Container:
    def __init__(self, context, name=None):
        self.context = context
        debug(self.context, "Container.__init__()")
        self.container_name = name
        self.container_id = None
        self.ports = {}
        self.start()

    def __del__(self):
        try:
            self.kill()
        except Exception:
            pass

    def __repr__(self):
        result = super().__repr__()
        result += f"(id:{self.container_id}, name:{self.container_name})"
        return result

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

    def start(self, use_proxy_auth: bool = True):
        debug(self.context, "Container.start()")
        args = [
            "run",
            "--hostname", "obs-server-behave",
        ]
        if self.container_name:
            args += [
                "--name", self.container_name,
                "--replace",
                "--stop-signal", "SIGKILL",
            ]
        args += [
            "--rm",
            "--detach",
            "--interactive",
            "--tty",
        ]

        with get_free_port() as obs_https, get_free_port() as gitea_http, get_free_port() as gitea_ssh:
            # we're using all context managers to reserve all ports at once
            # and close the gap between releasing them and using again in podman
            self.ports = {
                "obs_https": obs_https,
                "gitea_http": gitea_http,
                "gitea_ssh": gitea_ssh,
            }

            if use_proxy_auth:
                args += [
                    # enable proxy auth to bypass http auth that is slow
                    "--env", "OBS_PROXY_AUTH=1",
                ]

            args += [
                # obs runs always on 443 in the container
                "-p", f"{obs_https}:443",

                # gitea runs on random free ports
                # it is configured via env variables and running gitea-configure-from-env.service inside the container
                "-p", f"{gitea_http}:{gitea_http}",
                "--env", f"GITEA_SERVER_HTTP_PORT={gitea_http}",
                "-p", f"{gitea_ssh}:{gitea_ssh}",
                "--env", f"GITEA_SERVER_SSH_PORT={gitea_ssh}",
            ]

        args += [
            "obs-server"
        ]
        proc = self._run(args)
        lines = proc.stdout.strip().splitlines()
        self.container_id = lines[-1]

    def exec(self, args, check=True, interactive=False):
        podman_args = ["exec"]
        if interactive:
            podman_args += ["-it"]
        podman_args += [self.container_id]
        podman_args += args
        return self._run(podman_args, check=check)

    def kill(self):
        if not self.container_id:
            return
        debug(self.context, "Container.kill()")
        args = ["kill", self.container_id]
        self._run(args)
        self.container_id = None

    def restart(self):
        debug(self.context, "Container.restart()")
        self.kill()
        self.start()

    def wait_on_systemd(self):
        debug(self.context, "Container.wait_on_systemd() - start")
        self.exec(["/usr/bin/systemctl", "is-system-running", "--wait"], check=False)
        debug(self.context, "Container.wait_on_systemd() - done")


@behave.step("I start a new container without proxy auth")
def step_impl(context):
    context.podman.container.kill()
    context.podman.container.container_id = None
    context.podman.container.ports = {}
    context.podman.container.start(use_proxy_auth=False)
    context.podman.container.wait_on_systemd()
    context.osc.write_config()
    context.git_obs.write_config()
    context.git_osc_precommit_hook.write_config()
