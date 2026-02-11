import os
import docker
from typing import Optional
import logging
import atexit
from docker.types import DeviceRequest
import tiktoken
import atexit
import threading
import shlex
import time

def truncate_by_token(text: str, max_head_tokens: int = 1000, max_tail_tokens: int = 4000, model: str = "gpt-4") -> str:
    """
    Truncate text by token count using tiktoken, keeping head and tail parts.
    """
    model_to_encoding = {
        "gpt-4": "cl100k_base",
        "gpt-4o": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "text-davinci-003": "p50k_base",
        "code-davinci-002": "p50k_base",
    }
    encoding_name = model_to_encoding.get(model, "cl100k_base")
    enc = tiktoken.get_encoding(encoding_name)

    tokens = enc.encode(text)
    total = len(tokens)

    if total <= max_head_tokens + max_tail_tokens:
        return text

    # Take head and tail tokens, decode into strings
    head_str = enc.decode(tokens[:max_head_tokens])
    tail_str = enc.decode(tokens[-max_tail_tokens:])

    return (
        head_str +
        f"\n\n... [stderr output truncated: {total - max_head_tokens - max_tail_tokens} tokens omitted] ...\n\n" +
        tail_str
    )

class DockerManager:
    def __init__(
        self,
        image_name: str,
        container_name: str,
        mnt_dir: Optional[str] = None,
        dockerfile_dir: Optional[str] = None,
        workspace: str = "",  # workspace should be the working directory path inside the container
        num_gpus: int = -1
    ):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO) # Add basic logging config to see log output
        self.docker_client = docker.from_env()
        self.image_name = image_name
        self.container_name = container_name # Ensure this name does not contain colons or other illegal characters
        self.num_gpus = num_gpus
        
        # Resolve mnt_dir
        _mnt_dir_resolved = mnt_dir or os.getenv("PROJECT_WORKSPACE", "")
        if not _mnt_dir_resolved:
            raise ValueError("mnt_dir (or PROJECT_WORKSPACE env var) must be set.")
        self.mnt_dir = os.path.abspath(_mnt_dir_resolved)

        self.dockerfile_dir = os.path.abspath(dockerfile_dir or self.mnt_dir)
        
        # If user didn't specify a container working directory, default to the mount directory itself
        self.workspace = workspace if workspace else self.mnt_dir # workspace is the path inside the container

        self.container = None

        self._prepare_container()
        atexit.register(self.stop_container)

    def _ensure_container_removed(self, name: str):
        try:
            container = self.docker_client.containers.get(name)
            self.logger.info(f"Found existing container '{name}'. Stopping and removing...")
            container.stop(timeout=10)
            container.remove(force=True)
            self.logger.info(f"Container '{name}' stopped and removed.")
        except docker.errors.NotFound:
            self.logger.info(f"Container '{name}' not found, no need to remove.")
        except docker.errors.APIError as e:
            self.logger.error(f"Error managing existing container '{name}': {e}")


    def _prepare_container(self):
        # Ensure no container with the same name exists; clean up if found
        self._ensure_container_removed(self.container_name)

        try:
            self.logger.info(f"Trying to load image '{self.image_name}' from local cache...")
            self.docker_client.images.get(self.image_name)
            self.logger.info(f"Found local image '{self.image_name}'.")
        except docker.errors.ImageNotFound:
            self.logger.info(f"Local image '{self.image_name}' not found.")
            try:
                self.logger.info(f"Trying to pull image '{self.image_name}' from remote...")
                self.docker_client.images.pull(self.image_name)
                self.logger.info(f"Successfully pulled image '{self.image_name}'.")
            except docker.errors.APIError: # More specific exception handling
                self.logger.warning(f"Failed to pull image '{self.image_name}' from remote. Building image locally...")
                if not os.path.exists(os.path.join(self.dockerfile_dir, "Dockerfile")):
                    self.logger.error(f"Dockerfile not found in {self.dockerfile_dir}. Cannot build image.")
                    raise FileNotFoundError(f"Dockerfile not found in {self.dockerfile_dir}")
                self._build_image(self.dockerfile_dir)
        
        self.logger.info(f"Starting container '{self.container_name}' from image '{self.image_name}'.")
        self.logger.info(f"Volume mount: '{self.mnt_dir}' (host) -> '{self.mnt_dir}' (container)")
        self.logger.info(f"Container working directory: '{self.workspace}'")
        gpu_request = [DeviceRequest(count=self.num_gpus, capabilities=[['gpu']])]
        self.container = self.docker_client.containers.run(
            image=self.image_name,
            name=self.container_name,
            device_requests=gpu_request, # Request GPU devices
            volumes={self.mnt_dir: {'bind': self.mnt_dir, 'mode': 'rw'}}, # Container path should match host path for clarity
            working_dir=self.workspace, # Set the container's default working directory
            detach=True,
            tty=True, # Keep tty=True so bash -l works (even though we use conda run below)
            # remove=True # Consider removing this during testing/debugging to inspect container state
        )
        self.logger.info(f"Container '{self.container.name}' ({self.container.short_id}) started.")

    def _build_image(self, dockerfile_path: str): # path parameter should be a directory
        self.logger.info(f"Building image '{self.image_name}' from Dockerfile in directory: {dockerfile_path}")
        try:
            image, logs = self.docker_client.images.build(
                path=dockerfile_path, # Directory containing the Dockerfile
                dockerfile='Dockerfile', # Name of the Dockerfile
                tag=self.image_name,
                rm=True,
                forcerm=True
            )
            self.logger.info(f"Image '{self.image_name}' built successfully.")
            for chunk in logs:
                if 'stream' in chunk:
                    self.logger.debug(chunk['stream'].strip())
                elif 'errorDetail' in chunk:
                    self.logger.error(f"Build Error: {chunk['errorDetail']['message']}")
                    # If there's a build error, may need to raise an exception
                    raise docker.errors.BuildError(reason=chunk['errorDetail']['message'], build_log=logs)

        except docker.errors.BuildError as e:
            self.logger.error(f"Image build failed for '{self.image_name}': {e}")
            # Try to print more detailed logs
            if hasattr(e, 'build_log'):
                for log_entry in e.build_log:
                    if 'stream' in log_entry:
                        self.logger.error(f"Build Log: {log_entry['stream'].strip()}")
                    elif 'error' in log_entry:
                        self.logger.error(f"Build Log Error: {log_entry['error'].strip()}")
            raise
        except docker.errors.APIError as e:
            self.logger.error(f"Docker API error during image build for '{self.image_name}': {e}")
            raise

    def run_cmd_with_timeout(self, cmd: str, timeout: int = 1800, log_interval: int = 20):
        """
        Run a shell command inside the Docker container with timeout and periodic logging.
        1800 seconds is the default timeout.
        """
        result = {}
        stop_logging = threading.Event()

        conda_path = f"{self.docker_client.info()['OperatingSystem'] == 'Docker Desktop' and '/opt/conda/bin/' or '/opt/conda/bin/'}conda" # Fix conda path
        conda_prefix = f"{conda_path} run --no-capture-output -n zerorepo"

        # The user-provided cmd is like "PYTHONPATH=... coverage run -m pytest ..."
        # We need to wrap the full command in bash -c '...' so PYTHONPATH and && work correctly
        # self.workspace is the directory where code should be inside the container
        shell_command_to_run = f"{cmd}"

        # Final command for exec_run
        # Wrap shell_command_to_run in single quotes to handle spaces or special characters
        full_cmd_for_exec = f"{conda_prefix} /bin/bash -c '{shell_command_to_run}'"

        def exec_target():
            try:
                result["exec"] = self.container.exec_run(
                    cmd=full_cmd_for_exec,
                    demux=True,
                    workdir=self.workspace
                )
            except Exception as e:
                result["exec"] = (-1, (b"", f"Exception: {str(e)}".encode()))

        exec_thread = threading.Thread(target=exec_target)
        exec_thread.start()

        # Logging heartbeat thread
        start_time = time.time()

        def heartbeat():
            while not stop_logging.is_set() and exec_thread.is_alive():
                elapsed = int(time.time() - start_time)
                logging.info(f"[Running] {cmd[:80]}...  (Elapsed: {elapsed}s)")
                time.sleep(log_interval)

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()

        exec_thread.join(timeout)

        if exec_thread.is_alive():
            stop_logging.set()
            logging.warning(f"============Command timed out after {timeout} seconds==============")
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": (
                    f"[TimeoutError] Execution timed out after {timeout} seconds.\n"
                    f"Command: {full_cmd_for_exec}\n"
                    f"Working directory: {self.workspace}\n"
                    "Process is likely still running in background.\n"
                    "To debug:\n"
                    "  - Use `docker exec` to inspect container state\n"
                    "  - Check for infinite loops, blocking I/O, or missing timeouts\n"
                    "  - Add `timeout` or `python -u` inside your command to improve safety"
                )
            }

        stop_logging.set()

        exit_code, output = result["exec"]
        stdout, stderr = output
        stdout_decoded = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_decoded = stderr.decode("utf-8", errors="replace") if stderr else ""

        processed_stderr = truncate_by_token(stderr_decoded, max_head_tokens=1000, max_tail_tokens=4000)
        processed_stdout = truncate_by_token(stdout_decoded, max_head_tokens=1000, max_tail_tokens=4000)

        logging.info(f"Execute Command: {cmd}")
        logging.info(f"STDOUT:\n{processed_stdout if processed_stdout else '[empty]'}")
        logging.info(f"STDERR:\n{processed_stderr if processed_stderr else '[empty]'}")

        return {
            "exit_code": exit_code,
            "stdout": stdout_decoded,
            "stderr": stderr_decoded
        }

    def run_cmd(self, cmd: str):
        """Run specified command in container (ensuring zerorepo conda environment)"""
        if not self.container:
            self.logger.error("Container is not running. Cannot execute command.")
            return {"exit_code": -1, "stdout": "", "stderr": "Container not running."}

        # /opt/conda/bin/conda is the fixed Miniconda path
        # --no-capture-output ensures stdout/stderr can be captured by exec_run
        conda_path = f"{self.docker_client.info()['OperatingSystem'] == 'Docker Desktop' and '/opt/conda/bin/' or '/opt/conda/bin/'}conda" # Fix conda path
        conda_prefix = f"{conda_path} run --no-capture-output -n zerorepo"

        # The user-provided cmd is like "PYTHONPATH=... coverage run -m pytest ..."
        # We need to wrap the full command in bash -c '...' so PYTHONPATH and && work correctly
        # self.workspace is the directory where code should be inside the container
        shell_command_to_run = f"{cmd}"

        # Final command for exec_run
        # Wrap shell_command_to_run in single quotes to handle spaces or special characters
        full_cmd_for_exec = f"{conda_prefix} /bin/bash -c '{shell_command_to_run}'"
        
        self.logger.info(f"Executing in container: {full_cmd_for_exec}")
        
        exit_code, output = self.container.exec_run(
            cmd=full_cmd_for_exec,
            demux=True
            # working_dir=self.workspace # Can also be set here, but cd inside the command is more explicit
        )
        
        stdout_bytes, stderr_bytes = output
        decoded_stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        decoded_stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        self.logger.debug(f"Command exit code: {exit_code}")
        if decoded_stdout:
            self.logger.debug(f"STDOUT:\n{decoded_stdout}")
        if decoded_stderr:
            self.logger.debug(f"STDERR:\n{decoded_stderr}") # coverage usually outputs "No data collected" to stderr

        return {
            "exit_code": exit_code,
            "stdout": decoded_stdout,
            "stderr": decoded_stderr
        }

    def stop_container(self):
        """Stop and clean up the container."""
        if self.container:
            container_name = self.container.name # Get name first, as the object may become unavailable after removal
            try:
                self.logger.info(f"Stopping container '{container_name}'...")
                self.container.stop(timeout=10) # Allow time for graceful shutdown
                self.logger.info(f"Removing container '{container_name}'...")
                self.container.remove(force=True) # Force remove
                self.logger.info(f"Container '{container_name}' stopped and removed.")
            except docker.errors.NotFound:
                self.logger.warning(f"Container '{container_name}' already removed or not found.")
            except docker.errors.APIError as e:
                self.logger.error(f"Failed to stop/remove container '{container_name}': {e}")
            finally:
                self.container = None # Clean up reference
        else:
            self.logger.info("No active container to stop.")