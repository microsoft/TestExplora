import subprocess
import os
import shutil
from build_dependency_graph import build_json_graph
import json
from tqdm import tqdm   
from parse_repo import extract_classes_and_functions_from_repo
import re

def get_default_branch(repo_testbed_dir):
    """
    Determine the default branch of the remote repository.
    
    :param repo_testbed_dir: The directory where the repository is cloned.
    :return: Name of the default branch.
    """
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


def clone_or_update_repo(repo, repo_testbed_dir):
    """
    Clone the repository if it does not exist or update it to ensure it's a complete Git repository.
    
    :param repo: The name of the repository in the format 'owner/repo'.
    :param repo_testbed_dir: The directory where the repository should be cloned.
    """
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
                print(f"Repository already exists at {repo_testbed_dir}, updating...")
                
                # Ensure the working directory is clean
                subprocess.run(['git', 'reset', '--hard', 'HEAD'], cwd=repo_testbed_dir, check=True)
                subprocess.run(['git', 'clean', '-fdx'], cwd=repo_testbed_dir, check=True)
                
                # Fetch all changes from the remote
                subprocess.run(['git', 'fetch', '--all'], cwd=repo_testbed_dir, check=True)
                
                # Determine the default branch
                default_branch = get_default_branch(repo_testbed_dir)
                print(f"Default branch detected as '{default_branch}'")
                
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
    
    print(f"Cloning repository {repo} into {repo_testbed_dir}...")
    # Remove any existing directory with the same name to avoid conflicts
    if os.path.exists(repo_testbed_dir):
        raise Exception(f"Directory {repo_testbed_dir} already exists and is not a valid git repository.")
    
    # Clone the repository
    subprocess.run(['git', 'clone', f'https://github.com/{repo}.git', repo_testbed_dir], check=True)

def checkout_commit(repo_testbed_dir, commit_hash):
    """
    Checkout a specific commit in the repository.
    
    :param repo_testbed_dir: The directory where the repository is cloned.
    :param commit_hash: The commit hash to checkout.
    """
    print(f"Checking out commit {commit_hash} in {repo_testbed_dir}...")
    subprocess.run(['git', 'checkout', '--quiet', commit_hash], cwd=repo_testbed_dir, check=True)

def _parse_patch_with_line_numbers(patch_string: str):
    """
    Analyze a patch string and extract line numbers for added and removed lines.

    Args:
        patch_string (str): diff patch string.

    Returns:
        A dictionary with file names as keys and a dictionary of added and removed line numbers as values.
        The structure is like this:
        {
            'file1.py': {
                'added': [1, 2, 3],
                'removed': [4, 5]
            },
            'file2.py': {
                'added': [10],
                'removed': []
            }
        }
        where 'added' contains line numbers of lines added in the new version,
        and 'removed' contains line numbers of lines removed in the old version.
    """
    changed_files = {}
    current_file = None
    # Used to extract starting line numbers from '@@ -1,2 +1,3 @@'
    hunk_header_regex = re.compile(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')
    
    # Line number counters
    old_line_num = 0
    new_line_num = 0

    lines = patch_string.strip().split('\n')
    for line in lines:
        if line.startswith('diff --git'):
            try:
                current_file = line.split(' b/')[1].strip()
                changed_files[current_file] = {'added': [], 'removed': []}
            except IndexError:
                current_file = None
            continue

        if not current_file:
            continue

        match = hunk_header_regex.match(line)
        if match:
            # Reset line number counters when encountering a hunk header
            old_line_num = int(match.group(1)) - 1
            new_line_num = int(match.group(2)) - 1
            continue
        
        if line.startswith('-') and not line.startswith('---'):
            changed_files[current_file]['removed'].append(old_line_num)
            old_line_num += 1
        elif line.startswith('+') and not line.startswith('+++'):
            changed_files[current_file]['added'].append(new_line_num)
            new_line_num += 1
        elif line.startswith(' '):
            # Context line, exists in both versions, so both counters need to increment
            old_line_num += 1
            new_line_num += 1
            
    return changed_files

def add_patch(repo_path, patch_string):
    patch_info = _parse_patch_with_line_numbers(patch_string)
    command = ["git", "apply", "-"]
    process = subprocess.run(
        command,
        cwd=repo_path,
        input=patch_string,
        capture_output=True,
        text=True,
        check=False
    )

    if process.returncode == 0:
        print("✅ Patch successfully applied!")
        if process.stdout:
            print("Git stdout:", process.stdout)
        return patch_info
    else:
        print("❌ Error: Failed to apply patch.")
        print("Git returned an error message, please check the patch content or repository status.")
        print("--- Git Stderr ---")
        print(process.stderr)
        print("------------------")
        return None

def fine_function_by_patch(code_info, folders, patch_info, diff_key='added'):
    """
    Fine-tune the function information based on the patch information.
    
    :param code_info: Dictionary containing code information.
    :param folders: List of folders in the repository.
    :param patch_info: Dictionary containing patch information.
    :param diff_key: Key to determine whether to use 'added' or 'removed' lines.
    :return: Updated code_info with fine-tuned function information.
    """
    codes = []
    for file_name, changes in patch_info.items():
        if file_name not in folders:
            continue
        codes_in_folder = folders[file_name]['deps']['contains']
        changed_lines = changes.get(diff_key, [])
        for code_name in codes_in_folder:
            code = code_info.get(code_name, {})
            code_lines = code.get('line', (0, 0))
            code_lines_range = [i for i in range(code_lines[0] + 1, code_lines[1])]
            if set(code_lines_range) & set(changed_lines):
                codes.append(code_name)            

    return codes

def prepare_data(repo_data_path, repo_saved_dir):
    data_keys = ['repo_name', 'repo_version', 'base_commit', 'pr_id', 'patch', 'test_patch', 'tested_code', 'mask_path', 'recover_patch', 'test_cases', 'FAIL_TO_PASS', 'FASS_TO_PASS', 'time']
    benchmark_data = []
    repo_json_list = os.listdir(repo_data_path)
    for repo_json in tqdm(repo_json_list, desc="Processing repositories"):
        repo_path = os.path.join(repo_data_path, repo_json)
        if not os.path.exists(repo_path):
            print(f"Repository data file {repo_path} does not exist, skipping...")
            continue
        
        with open(repo_path, 'r', encoding="utf-8") as f:
            repo_info = json.load(f)

        repo_name = repo_info['full_name']
        tem_repo_saved_dir = str(os.path.join(repo_saved_dir, repo_name))
        clone_or_update_repo(repo_name, tem_repo_saved_dir)
        default_branch = get_default_branch(tem_repo_saved_dir)
        for pr in repo_info["pulls"]:
            pr_data = {key: None for key in data_keys}
            pr_data['repo_name'] = repo_name
            pr_data['repo_version'] = "" # TODO: Add repo version if available

            if pr["state"] != "closed":
                print(f"Pull request {pr['number']} is not closed, skipping...")
                continue
            base_commit = pr["base"]["sha"]
            pr_data['base_commit'] = base_commit
            pr_data['pr_id'] = pr["pull_number"]
            checkout_commit(tem_repo_saved_dir, base_commit)
            pre_code_deps, pre_folders = build_json_graph(repo_path=tem_repo_saved_dir, global_import=True)
            pre_code_info = extract_classes_and_functions_from_repo(tem_repo_saved_dir)

            # TODO: Add patch and analyze the code
            patch_dict : dict = pr["patches"]
            patch_string = ""
            test_patch = ""
            code_patch = ""
            test_files = []

            for name, patch in patch_dict.items():
                patch_string += patch + "\n"
                if "test" in name:
                    test_patch += patch + "\n"
                    test_files.append(name)
                else:
                    code_patch += patch + "\n"
            pr_data['patch'] = patch_string
            pr_data['test_patch'] = test_patch
            patch_info = add_patch(tem_repo_saved_dir, patch_string)

            assert set(patch_info.keys()) == set(patch_dict.keys()), "Patch keys do not match the expected keys."
            post_code_deps, post_folders = build_json_graph(repo_path=tem_repo_saved_dir, global_import=True)
            post_code_info = extract_classes_and_functions_from_repo(tem_repo_saved_dir)

            changed_base_codes = fine_function_by_patch(post_code_info, post_folders, patch_info, diff_key='added')
            changed_base_tests = fine_function_by_patch(post_code_info, post_folders, patch_info, diff_key='added')
            

    
if __name__ == "__main__":
    repo_data_path = "/home/superbench/jiaxiang/blob/github_storage/report/python_repo_data_json"
    repo_saved_dir = "/home/superbench/jiaxiang/Dev-TestCaseGen/build_benchmark/temp_repos"
    
    prepare_data(repo_data_path, repo_saved_dir)
    
