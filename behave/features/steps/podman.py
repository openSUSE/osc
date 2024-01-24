import queue
import subprocess
import threading

from steps.common import debug


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
        debug(self.context, f"> {self.container}")


class Container:
    def __init__(self, context, name=None):
        self.context = context
        debug(self.context, "Container.__init__()")
        self.container_name = name
        self.container_id = None
        self.port = None
        self.start()

    def __del__(self):
        try:
            self.kill()
        except Exception:
            pass

    def __repr__(self):
        result = super().__repr__()
        result += f"(port:{self.port}, id:{self.container_id}, name:{self.container_name})"
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

    def start(self):
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
            "-p", "443",
            "obs-server"
        ]
        proc = self._run(args)
        lines = proc.stdout.strip().splitlines()
        self.container_id = lines[-1]
        self.wait_on_systemd()
        self.port = self.get_port()

    def exec(self, args, check=True):
        args = ["exec", self.container_id] + args
        return self._run(args, check=check)

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
        self.exec(["/usr/bin/systemctl", "is-system-running", "--wait"], check=False)

    def get_port(self):
        args = ["port", self.container_id]
        proc = self._run(args)
        lines = proc.stdout.strip().splitlines()
        for line in lines:
            if line.startswith("443/tcp"):
                # return <port> from: "443/tcp -> 0.0.0.0:<port>"
                return line.split(":")[-1]
        raise RuntimeError(f"Could not determine port of container {self.container_id}")
