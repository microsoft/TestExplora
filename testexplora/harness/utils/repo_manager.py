import subprocess
import shutil
import os
import logging

env = os.environ.copy()
env["GIT_LFS_SKIP_SMUDGE"] = "1"

logging.info(f"Setting GIT_LFS_SKIP_SMUDGE to {env['GIT_LFS_SKIP_SMUDGE']} to avoid downloading LFS files.")

def safe_ignore_function(dir, files):
    ignored = []
    # First apply the existing .git ignore rules
    git_ignored = shutil.ignore_patterns(".git")(dir, files)
    ignored.extend(git_ignored)
    
    # Check if each file is accessible
    for file in files:
        file_path = os.path.join(dir, file)
        if os.path.islink(file_path) and not os.path.exists(file_path):
            # Invalid symbolic link
            ignored.append(file)
        elif not os.access(file_path, os.R_OK):
            # File without read permission
            ignored.append(file)
    
    return ignored

class RepoManager:
    def __init__(self, repo, repo_testbed_dir):
        self.repo = repo
        self.commit = None
        self.repo_testbed_dir = repo_testbed_dir.rstrip('/') + '/' + repo.split('/')[-1]

    def clone_or_update_repo(self):
        """
        Clone the repository if it does not exist or update it to ensure it's a complete Git repository.
        
        :param repo: The name of the repository in the format 'owner/repo'.
        :param repo_testbed_dir: The directory where the repository should be cloned.
        """
        repo = self.repo
        repo_testbed_dir = self.repo_testbed_dir
        if os.path.exists(repo_testbed_dir) and os.path.isdir(repo_testbed_dir):
            # Check if it's a git repository
            try:
                result = subprocess.run(
                    ['git', 'rev-parse', '--is-inside-work-tree'],
                    cwd=repo_testbed_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                if 'true' in result.stdout.strip():
                    logging.info(f"Repository already exists at {repo_testbed_dir}, updating...")
                    
                    # Ensure the working directory is clean
                    subprocess.run(['git', 'reset', '--hard', 'HEAD'], cwd=repo_testbed_dir, check=True)
                    subprocess.run(['git', 'clean', '-fdx'], cwd=repo_testbed_dir, check=True)
                    
                    # Fetch all changes from the remote
                    subprocess.run(['git', 'fetch', '--all'], cwd=repo_testbed_dir, check=True)
                    
                    # Determine the default branch
                    default_branch = self.get_default_branch()
                    logging.info(f"Default branch detected as '{default_branch}'")
                    
                    # Switch to the default branch
                    try:
                        subprocess.run(['git', 'checkout', default_branch], cwd=repo_testbed_dir, check=True)
                    except subprocess.CalledProcessError:
                        # If the default branch doesn't exist locally, create it tracking the remote one
                        subprocess.run(['git', 'checkout', '-b', default_branch, f'origin/{default_branch}'], cwd=repo_testbed_dir, check=True)
                    
                    # Pull the latest changes from the remote default branch
                    subprocess.run(['git', 'pull', '--ff-only', 'origin', default_branch], cwd=repo_testbed_dir, check=True)
                    
                    return
            except subprocess.CalledProcessError:
                pass  # Not a valid git repository, proceed with cloning
        
        logging.info(f"Cloning repository {repo} into {repo_testbed_dir}...")

        parent_dir = os.path.dirname(repo_testbed_dir)
        os.makedirs(parent_dir, exist_ok=True)

        # Remove any existing directory with the same name to avoid conflicts
        if os.path.exists(repo_testbed_dir):
            logging.info(f"Removing existing directory: {repo_testbed_dir}")
            shutil.rmtree(repo_testbed_dir)
        
        # Clone the repository
        try:
            subprocess.run(['git', 'clone', f'https://github.com/{repo}.git', repo_testbed_dir], 
                        check=True, capture_output=True, text=True, cwd=parent_dir)
            logging.info(f"Successfully cloned {repo}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Git clone failed with return code: {e.returncode}")
            logging.error(f"Command: {e.cmd}")
            logging.error(f"Stdout: {e.stdout}")
            logging.error(f"Stderr: {e.stderr}")
            raise

    
    def checkout_commit(self, commit_sha):
        """
        Checkout a specific commit in the repository.
        
        :param repo_testbed_dir: The directory where the repository is cloned.
        :param commit_sha: The commit sha to checkout.
        """
        repo_testbed_dir = self.repo_testbed_dir
        logging.info(f"Checking out commit {commit_sha} in {repo_testbed_dir}...")
        try:
            subprocess.run(['git', 'checkout', '--quiet', commit_sha], cwd=repo_testbed_dir, check=True)
            self.commit = commit_sha
            return True
        except subprocess.CalledProcessError as e:
            return False
    
    def copy_repo(self):
        """
        Copy the repository to a new location.
        """
        repo_testbed_dir = self.repo_testbed_dir
        par_dir = os.path.abspath(os.path.join(self.repo_testbed_dir, os.pardir))
        new_repo_dir = os.path.join(par_dir, "tmp", self.repo.split("/")[-1])
        if os.path.exists(new_repo_dir):
            shutil.rmtree(new_repo_dir)
        logging.info(f"Copying repository to {new_repo_dir}...")
        shutil.copytree(repo_testbed_dir, new_repo_dir, ignore=safe_ignore_function)
        subprocess.run(["git", "init"], cwd=new_repo_dir, check=True)
        subprocess.run(["git", "add", "-A"], cwd=new_repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=new_repo_dir, check=True)
        self.copy_repo_dir = new_repo_dir
        return new_repo_dir

    def rm_copy_repo(self):
        """
        Remove the copied repository directory. 
        """
        logging.info(f"Removing copied repository directory {self.copy_repo_dir}...")
        if os.path.exists(self.copy_repo_dir):
            shutil.rmtree(self.copy_repo_dir)

    def get_default_branch(self):
        """
        Determine the default branch of the remote repository.
        
        :param repo_testbed_dir: The directory where the repository is cloned.
        :return: Name of the default branch.
        """
        repo_testbed_dir = self.repo_testbed_dir
        result = subprocess.run(
            ['git', 'remote', 'show', 'origin'],
            cwd=repo_testbed_dir,
            capture_output=True,
            text=True,
            check=True
        )
        for line in result.stdout.splitlines():
            if 'HEAD branch:' in line:
                return line.split()[-1]
        return 'main'  # Fallback to 'main' if not found
    
    def remove_repo(self):
        """
        Remove the repository directory.
        
        :param repo_testbed_dir: The directory where the repository is cloned.
        """
        repo_testbed_dir = self.repo_testbed_dir
        if os.path.exists(repo_testbed_dir):
            logging.info(f"Removing repository directory {repo_testbed_dir}...")
            shutil.rmtree(repo_testbed_dir)

    def restore_repo(self):
        """
        Restore the repository to its original state by removing all files except the .git directory.
        """
        logging.info(f"Restoring repository {self.repo_testbed_dir} to its original state...")
        subprocess.run(['git', 'reset', '--hard', 'HEAD'], cwd=self.repo_testbed_dir, check=True)
        subprocess.run(['git', 'clean', '-fd'], cwd=self.repo_testbed_dir, check=True)

    def add_changes(self, file_path):
        """
        Stage changes to a specific file in the repository.
        
        :param file_path: The path of the file to stage, relative to the repository root.
        """
        repo_path = self.repo_testbed_dir
        logging.info(f"Staging changes for {file_path} in {repo_path}...")
        subprocess.run(['git', 'add', file_path], cwd=repo_path, check=True)

    def get_diff(self, diff_saved_dir, no_index=False, cached=False):
        """
        Get the diff for changes made in the repository.
        :param diff_saved_dir: Directory to save the diff file.
        :param no_index: Whether to use --no-index option in git diff.
        :return: Path to the saved diff file.
        """
        repo_testbed_dir = self.repo_testbed_dir
        diff_file_path = os.path.join(diff_saved_dir, 'changes.diff')
        logging.info(f"Generating diff file at {diff_file_path}...")
        cmd = ['git', 'diff']
        if no_index:
            cmd.append('--no-index')
        if cached:
            cmd.append('--cached')
        cmd.append(f'--output={diff_file_path}')
        subprocess.run(cmd, cwd=repo_testbed_dir, check=True)
        return diff_file_path
    
    
    def add_patch(self, patch_string):
        # patch_info = _parse_patch_with_line_numbers(patch_string)
        repo_path = self.repo_testbed_dir
        command = ["git", "apply", "-p1", "-"]
        process = subprocess.run(
            command,
            cwd=repo_path,
            input=patch_string,
            capture_output=True,
            text=True,
            check=False
        )

        if process.returncode == 0:
            logging.info("✅ Patch successfully applied!")
            if process.stdout:
                logging.info(f"Git stdout: {process.stdout}")
            return True
        else:
            logging.info("❌ Error: Failed to apply patch.")
            logging.info("Git returned an error message, please check the patch content or repository status.")
            logging.info("--- Git Stderr ---")
            logging.info(process.stderr)
            logging.info("------------------")
            return False
