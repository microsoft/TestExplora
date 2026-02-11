from utils.eval_docker import DockerManager
from utils.eval_ces import CESManager
from utils.repo_manager import RepoManager
import os
import logging
import json

AZ_UPOLOAD_COMMAND = """
az storage blob upload \
  --account-name {az_account} \
  --account-key  {az_key} \
  --container-name {az_container} \
  --name "coverage/coverage.json" \
  --file {coverage_json_dir} \
  --overwrite
""".strip()

class TestRunner:
    def __init__(self, runner_type: str, repo_manager: RepoManager, args):
        self.repo_manager = repo_manager
        self.runner_type = runner_type
        self.args = args
        if runner_type == "docker":
            self.test_manager = DockerManager(image_name=args.image_name, 
                                              container_name=f"repo-{repo_manager.repo}", mnt_dir=args.repo_testbed_dir, 
                                              dockerfile_dir=args.dokerfile_dir, workspace=repo_manager.repo_testbed_dir)
        elif runner_type == "ces":
            self.test_manager = CESManager(repo_name=self.repo_manager.repo, commit=self.repo_manager.commit, args=args)
        else:
            raise ValueError(f"Unsupported runner type: {runner_type}")

    def stop_manager(self):
        if self.runner_type == "docker":
            self.test_manager.stop_container()
        elif self.runner_type == "ces":
            self.test_manager.end_run()
    
    def add_test_patch(self, patch: str):
        if self.runner_type == "docker":
           success = self.repo_manager.add_patch(patch)
        elif self.runner_type == "ces":
            success = self.test_manager.add_patch(patch)
        return success

    def run_tests(self, test_patch: str, saved_test_path_str: str, add_test_patch: bool = True):
        if add_test_patch:
            patch_success = self.add_test_patch(test_patch)
            if not patch_success:
                return False, None

        running_data = {"running_log": "", "coverage_report": {}}
        if self.runner_type == "docker":
            coverage_file = os.path.join(self.args.repo_testbed_dir, ".coverage")
            coverage_json_dir = os.path.join(self.args.repo_testbed_dir, "coverage_data.json")
            run_name = os.path.join(self.repo_manager.repo_testbed_dir, saved_test_path_str)
            test_command = ["coverage", "run", f"--data-file={coverage_file}", "-m", "pytest", run_name]
            test_command_str = f"PYTHONPATH={self.repo_manager.repo_testbed_dir} " + ' '.join(test_command)
            logging.info(f"Running command: {test_command_str}")
            result = self.test_manager.run_cmd(test_command_str)
            logging.info(f"Command output: \n{result['stdout']}")

            cover_comand = ["coverage", "json", f"--data-file={coverage_file}", "-o", coverage_json_dir]
            cover_comand_str = ' '.join(cover_comand)
            logging.info(f"Running command: {cover_comand_str}")
            result_cov = self.test_manager.run_cmd(cover_comand_str)
            logging.info(f"Command output: \n{result_cov['stdout']}")
            with open(coverage_json_dir, "r", encoding="utf-8") as f:
                coverage_data = json.load(f)
            
            running_data["running_log"] = result['stdout']
            running_data["coverage_report"] = coverage_data
        elif self.runner_type == "ces":
            coverage_file = "./.coverage"
            coverage_json_dir = "./coverage_data.json"
            run_name = saved_test_path_str
            test_command = f"coverage run --data-file={coverage_file} -m pytest {run_name}"
            logging.info(f"Running command in CES: {test_command}")
            result = self.test_manager.run_cmd(test_command)
            logging.info(f"Command output: \n{result}")
            cover_comand = f"coverage json --data-file={coverage_file} -o {coverage_json_dir}"
            logging.info(f"Running command in CES: {cover_comand}")
            result_cov = self.test_manager.run_cmd(cover_comand)
            logging.info(f"Command output: \n{result_cov}")
            uploda_command = AZ_UPOLOAD_COMMAND.format(
                az_account=self.args.az_account,
                az_key=self.args.az_key,
                az_container=self.args.az_container,
                coverage_json_dir=coverage_json_dir
            )
            logging.info(f"Uploading coverage data to Azure Blob Storage with command: {uploda_command}")
            upload_result = self.test_manager.run_cmd(uploda_command)
            logging.info(f"Upload command output: \n{upload_result}")
            with open(os.path.join(self.args.blob_dir, "coverage/coverage.json"), "r", encoding="utf-8") as f:
                coverage_data = json.load(f)
            running_data["running_log"] = result
            running_data["coverage_report"] = coverage_data

        return True, running_data