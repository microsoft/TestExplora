from utils.ces_api import call_api
import logging

class CESManager:
    def __init__(self, repo_name, commit, args):
        self.repo_name = repo_name
        self.commit = commit
        self.args = args

        run_id, init_result = call_api(stage="initRun", repo=repo_name, commit=commit)
        self.run_id = run_id
        self.init_success = init_result.get('InitSucceeded', False)

        if not self.init_success:
            logging.error(f"Failed to initialize CES run for repo {repo_name} at commit {commit}.")
    
    def end_run(self):
        if not self.init_success:
            return
        _, end_result = call_api(stage="endRun", repo=self.repo_name, commit=self.commit, run_id=self.run_id)
        logging.info(f"Ended CES run for repo {self.repo_name} at commit {self.commit}. Result: {end_result.get('Message', 'End run failed')}")

    def add_patch(self, patch_content):
        if not self.init_success:
            return False
        stage = "addPatch"
        _, patch_result = call_api(stage=stage, repo=self.repo_name, run_id=self.run_id, patch_content=patch_content)
        success = patch_result.get('RunComplete', False)
        if success:
            logging.info("✅ Patch successfully applied in CES!")
        else:
            logging.error(f"❌ Failed to apply patch in CES. Message: {patch_result.get('Message', 'No message')}")
        return success
    
    def run_cmd(self, command):
        if not self.init_success:
            return {"stdout": "", "stderr": "CES run not initialized."}
        stage = "runCommand"
        _, cmd_result = call_api(stage=stage, repo=self.repo_name, run_id=self.run_id, command=command)
        if not cmd_result.get('RunComplete', False):
            logging.error(f"❌ Command execution failed in CES. Message: {cmd_result.get('Message', 'No message')}")
        return cmd_result.get('Log', "")