import subprocess
import os
import shutil
from build_dependency_graph import build_json_graph
import json
from tqdm import tqdm   
from parse_repo import extract_classes_and_functions_from_repo, Repo_file_container
import re
import requests
from unidiff import PatchSet

import os
from typing import Tuple
import difflib
from copy import deepcopy
import logging
import argparse

import signal
import time

# 定义超时处理函数
def handler(signum, frame):
    raise TimeoutError("本次迭代超时")

signal.signal(signal.SIGALRM, handler)  # 注册信号

FOBIDDEN_REPO = ['MemTensor/MemOS', 'sammchardy/python-binance']

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


def clone_or_update_repo(repo, repo_testbed_dir, token):
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
                logging.info(f"Repository already exists at {repo_testbed_dir}, updating...")
                
                # Ensure the working directory is clean
                subprocess.run(['git', 'reset', '--hard', 'HEAD'], cwd=repo_testbed_dir, check=True)
                subprocess.run(['git', 'clean', '-fdx'], cwd=repo_testbed_dir, check=True)
                
                # Fetch all changes from the remote
                subprocess.run(['git', 'fetch', '--all'], cwd=repo_testbed_dir, check=True)
                
                # Determine the default branch
                default_branch = get_default_branch(repo_testbed_dir)
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
    # Remove any existing directory with the same name to avoid conflicts
    if os.path.exists(repo_testbed_dir):
        raise Exception(f"Directory {repo_testbed_dir} already exists and is not a valid git repository.")
    
    # Clone the repository
    subprocess.run(['git', 'clone', f'https://{token}@github.com/{repo}.git', repo_testbed_dir], check=True)

def checkout_commit(repo_testbed_dir, commit_hash):
    """
    Checkout a specific commit in the repository.
    
    :param repo_testbed_dir: The directory where the repository is cloned.
    :param commit_hash: The commit hash to checkout.
    """
    logging.info(f"Checking out commit {commit_hash} in {repo_testbed_dir}...")
    try:
        subprocess.run(['git', 'checkout', '--quiet', commit_hash], cwd=repo_testbed_dir, check=True)
        return True
    except subprocess.CalledProcessError as e:
        return False

def restore_repo(repo_testbed_dir):
    """
    Restore the repository to its original state by removing all files except the .git directory.
    """
    logging.info(f"Restoring repository {repo_testbed_dir} to its original state...")
    subprocess.run(['git', 'reset', '--hard', 'HEAD'], cwd=repo_testbed_dir, check=True)
    subprocess.run(['git', 'clean', '-fd'], cwd=repo_testbed_dir, check=True)

def _parse_patch_with_line_numbers_for_file(patch_string: str):
    """
    Analyze a patch string and extract line numbers for added and removed lines.

    Args:
        patch_string (str): diff patch string for a single file.

    Returns:
        A dictionary with file names as keys and a dictionary of added and removed line numbers as values.
        The structure is like this:
        {
            'added': [1, 2, 3],
            'removed': [4, 5]
        }
        where 'added' contains line numbers of lines added in the new version,
        and 'removed' contains line numbers of lines removed in the old version.
        一个字典，结构为 {文件名: {'added': [行号列表], 'removed': [行号列表]}}。
        'added' 中的行号对应新文件，'removed' 中的行号对应旧文件。
    """
    changed_lines = {'added': [], 'removed': []}
    # 用于从 '@@ -1,2 +1,3 @@' 中提取起始行号
    hunk_header_regex = re.compile(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')
    
    # 行号计数器
    old_line_num = 0
    new_line_num = 0

    lines = patch_string.strip().split('\n')
    start_counting = False
    for line in lines:
        if line.startswith('diff --git'):
            start_counting = False
            continue
        if line.startswith('@@'):
            match = hunk_header_regex.match(line)
            if match:
                # 当遇到 hunk 头部时，重置行号计数器
                old_line_num = int(match.group(1)) - 1
                new_line_num = int(match.group(2)) - 1
                start_counting = True
            continue
        if not start_counting:
            continue
        if line.startswith('-'):
            changed_lines['removed'].append(old_line_num)
            old_line_num += 1
        elif line.startswith('+'):
            changed_lines['added'].append(new_line_num)
            new_line_num += 1
        elif line.startswith(' '):
            # 上下文行，在两个版本中都存在，所以两个计数器都要增加
            old_line_num += 1
            new_line_num += 1
    return changed_lines

def add_patch(repo_path, patch_string):
    # patch_info = _parse_patch_with_line_numbers(patch_string)
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

def find_code_by_patch(code_info, folders, patch_info, diff_key='added'):
    """
    Fine-tune the code information based on the patch information.
    
    :param code_info: Dictionary containing code information.
    :param folders: List of folders in the repository.
    :param patch_info: Dictionary containing patch information.
    :param diff_key: Key to determine whether to use 'added' or 'removed' lines.
    :return: Updated code_info with fine-tuned code information.
    """
    codes = []
    for file_name, changes in patch_info.items():
        if file_name not in folders:
            continue
        codes_in_folder = folders[file_name]['deps']['contains']
        fn_code_infolder = []
        for code_name in codes_in_folder:
            if code_info.get(code_name, {}).get('type') != 'class':
                fn_code_infolder.append(code_name)
            else:
                # If it's a class, we need to check its methods
                methods = code_info.get(code_name, {}).get('methods', [])
                for method in methods:
                    if method not in code_info:
                        continue
                    fn_code_infolder.append(method)
            
        changed_lines = changes.get(diff_key, [])
        for code_name in fn_code_infolder:
            code = code_info.get(code_name, {})
            code_lines = code.get('line', (0, 0))
            code_lines_range = [i for i in range(code_lines[0] + 1, code_lines[1])]
            if set(code_lines_range) & set(changed_lines):
                codes.append(code_name)            

    return codes

def find_invokes_for_codes(code_deps, code_name):
    """
    Find all invokes for a given code name in the code dependencies.
    
    :param code_deps: Dictionary containing code dependencies.
    :param code_name: Name of the code to find invokes for.
    :return: List of invokes for the given code name.
    """
    if code_deps[code_name]['type'] != 'class':
        deps = code_deps.get(code_name, {}).get('deps', {})
        invokes = deps.get('invokes', [])
    else:
        invokes = []
        for method in code_deps.get(code_name, {}).get('deps', {}).get('contains', []):
            if not method.startswith(code_name):
                continue
            method_info = code_deps.get(method, {})
            if method_info.get('type') == 'function':
                invokes += method_info.get('deps', {}).get('invokes', [])
        invokes = list(set(invokes))
    return invokes

def find_test_dict_for_codes(code_deps):
    test_dict = {}
    for name, code_deps in code_deps.items():
        if ('test' in name.lower()) and (code_deps['type'] == 'function'):
            invoks = code_deps.get('deps', {}).get('invokes', [])
        else:
            invoks = []
        for invoke in invoks:
            if invoke not in test_dict:
                test_dict[invoke] = []
            test_dict[invoke].append(name)
    return test_dict

def get_code_content(repo, code_name, code_info, mask=False):
    """
    Get the content of a specific code by its name from the repository.
    
    :param repo: The repository file container.
    :param code_name: The name of the code to retrieve.
    :return: The content of the code.
    """
    file_name = code_name.split(":")[0]
    file_info = repo.get_file_content(file_name)
    code_lines = file_info["lines"][code_info[code_name]["line"][0]-1:code_info[code_name]["line"][1]]
    code_str = "\n".join(code_lines)
    if not file_info:
        return None
    if mask:
        mask_pattern = "# -- Code to be worked on --"
        if code_info[code_name]["type"] != "class":
            impl_start = code_info[code_name]['docstring_end_line']
            impl_end = code_info[code_name]['line'][1]
            if impl_end > impl_start:
                impl_lines = file_info["lines"][impl_start: impl_end]
                impl_text = "\n".join(impl_lines)
                if impl_text:
                    num_spaces = len(impl_lines[0]) - len(impl_lines[0].lstrip())
                    tem_mask_str = " " * num_spaces + mask_pattern
                    code_str = code_str.replace(impl_text, tem_mask_str)
            
        else:
            for method in code_info.get(code_name, {}).get('methods', []):
                if method not in code_info:
                    continue
                impl_start = code_info[method]['docstring_end_line']
                impl_end = code_info[method]['line'][1]
                if impl_end > impl_start:
                    impl_lines = file_info["lines"][impl_start: impl_end]
                    impl_text = "\n".join(impl_lines)
                    if impl_text:
                        # Avoid replace empty string!!! Bug of OOM!!!
                        num_spaces = len(impl_lines[0]) - len(impl_lines[0].lstrip())
                        tem_mask_str = " " * num_spaces + mask_pattern
                        code_str = code_str.replace(impl_text, tem_mask_str) 

    return code_str

def tested_function_checker(pre_code_info, post_code_info, pre_repo, post_repo, tested_codes):
    """
    Check if the tested codes are valid functions in the pre and post code information.
    :param pre_code_info: Pre-patch code information.
    :param post_code_info: Post-patch code information.
    :param pre_repo: Pre-patch repository file container.       
    :param post_repo: Post-patch repository file container.
    :param tested_codes: List of tested codes.
    :return: List of valid tested codes.
    """
    vaild_codes = []
    for code_n in tested_codes:
        # Check if the code exists in both pre and post code information
        if (code_n not in pre_code_info) or (code_n not in post_code_info):
            continue
        pre_code = pre_code_info[code_n]
        post_code = post_code_info[code_n]
        file = pre_code['file']

        post_code_str = get_code_content(post_repo, code_n,  post_code_info)
        post_code_wo_docstring = re.sub(r'""".*?"""|\'\'\'.*?\'\'\'', '', post_code_str, flags=re.DOTALL)
        pre_docstring = pre_code.get('docstring', '')
        post_docstring = post_code.get('docstring', '')

        skip = False
        for method in post_code.get('methods', []):
            if method not in pre_code_info:
                skip = True
                continue
            pre_method = pre_code_info[method]
            pre_docstring += pre_method.get('docstring', '')
            post_method = post_code_info[method]
            post_docstring += post_method.get('docstring', '')
        if skip:
            continue
        # Check if the docstrings are the same
        if pre_docstring != post_docstring:
            continue
        # Check if the code will be changed in future commits
        if "todo" in post_code_str.lower():
            continue
        if "pass" in post_code_wo_docstring.lower():
            continue

        vaild_codes.append(code_n)
    
    return vaild_codes

def _yeld_repo_data(pr_data_path, repo_data_path):
    repo_json_list = os.listdir(pr_data_path)
    ind = 0
    for repo_jsonl in tqdm(repo_json_list, desc="Processing repositories"):
        repo_id = repo_jsonl.split(".jsonl")[0]
        repo_path = os.path.join(repo_data_path, repo_id + ".json")
        pr_path = os.path.join(pr_data_path, repo_jsonl)
        if not os.path.exists(repo_path) or not os.path.exists(pr_path):
            logging.info(f"Repository data file {repo_path} or PR data file {pr_path} does not exist, skipping...")
            continue
        with open(repo_path, 'r', encoding="utf-8") as f:
            repo_info = json.load(f)
        pr_dict = {pr["pull_number"]: pr for pr in repo_info["pulls"]}
        if repo_info["full_name"] in FOBIDDEN_REPO:
            logging.info(f"Skipping repository {repo_info['full_name']}...")
            continue
        pull_list = []
        with open(pr_path, 'r', encoding="utf-8") as f:
            for line in f:
                pr = json.loads(line.strip())
                if pr_dict[pr["pull_number"]]["state"] != "closed":
                    continue
    
                test_file = []
                base_file = []
                for patch in pr["diff_patch"]:
                    name = patch["filename"]
                    if any(test_word in name for test_word in ["test", "tests", "e2e", "testing"]):
                        test_file.append(name)
                    else:
                        base_file.append(name)
                if not test_file or not base_file:
                    continue
                pr_dict[pr["pull_number"]]["patches"] = pr["diff_patch"]
                pr_dict[pr["pull_number"]]["pr_diff"] = pr["pr_diff"]
                pull_list.append(pr_dict[pr["pull_number"]])
        if len(pull_list) == 0:
            logging.info(f"No closed pull requests found for repository {repo_info['full_name']}, skipping...")
            continue
        logging.info(f"Processing repository {ind + 1}/{len(repo_json_list)-1}: NAME_{repo_info['full_name']} ID_{repo_id} NUM_PR_{len(pull_list)}")
        ind += 1
        repo_info["pulls"] = pull_list
        logging.info(f"Processing repository {repo_info['full_name']} with {len(repo_info['pulls'])} pull requests.")
        yield repo_info

def get_full_diff(repo_name, pr_id, token):
    url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_id}"
    headers = {
        "Accept": "application/vnd.github.v3.diff",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        logging.info(f"Failed to fetch diff for {repo_name} PR {pr_id}: {response.status_code} {response.text}")
        return None

def get_diff(
    old_contents: str,
    new_contents: str,
    filepath: str = "file",
    *,
    context: int = 3,          # 建议 >= 3，给 git 更友好
    for_git_apply: bool = True # True: 生成更适合 git apply 的形式
) -> str:
    """Return a unified diff between old/new contents for a single file.

    - Adds 'a/' / 'b/' prefixes to filenames when for_git_apply=True
    - Uses context lines (default 3) to make patch robust
    - Preserves trailing spaces and line endings in hunks
    """

    # Git/patch 对末尾换行很敏感：确保文本以 '\n' 结尾
    if not old_contents.endswith("\n"):
        old_contents = old_contents + "\n"
    if not new_contents.endswith("\n"):
        new_contents = new_contents + "\n"

    # 推荐带 a/ b/ 前缀，提高兼容性/可读性
    fromfile = f"a/{filepath}" if for_git_apply else filepath
    tofile   = f"b/{filepath}" if for_git_apply else filepath

    # 用 splitlines(keepends=True) 保留原始换行；用 lineterm='\n' 明确行终止
    diff_lines = list(
        difflib.unified_diff(
            old_contents.splitlines(keepends=True),
            new_contents.splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
            n=context,
            lineterm="\n",
        )
    )

    # 重要：不要 rstrip()，否则会破坏补丁的精确性
    return "".join(diff_lines)

'''
def find_invoke_tree_paths(code_deps, code_name, visited=None, code_type=''):
    """
    Find all paths of invokes for a given code name in the code dependencies.
    
    :param code_deps: Dictionary containing code dependencies.
    :param code_name: Name of the code to find invoke paths for.
    :param visited: Set to keep track of visited codes to avoid cycles.
    :return: List of lists, where each inner list is a path of invokes.
    """
    if visited is None:
        visited = set()
    
    if code_name in visited:
        return []
    
    visited.add(code_name)
    
    paths = []
    if code_type == 'class':
        invokes = code_deps.get(code_name, {}).get('deps', {}).get('invokes', []) + code_deps.get(code_name, {}).get('deps', {}).get('contains', [])
    else:
        invokes = code_deps.get(code_name, {}).get('deps', {}).get('invokes', [])
    
    if not invokes:
        return [[code_name]]
    
    for invoke in invokes:
        sub_paths = find_invoke_tree_paths(code_deps, invoke, visited)
        for sub_path in sub_paths:
            paths.append([code_name] + sub_path)
    
    return paths
'''
def bfs_finding_target_code(code_deps, start_code, target_code, code_info):
    """
    Perform BFS to find a path from start_code to target_code in the code dependencies.
    
    :param code_deps: Dictionary containing code dependencies.
    :param start_code: The starting code name.
    :param target_code: The target code name to find.
    :param max_explore_size: Maximum number of nodes to explore.
    :return: List representing the path from start_code to target_code, or empty list if not found.
    """
    from collections import deque

    invokes = code_deps.get(start_code, {}).get('deps', {}).get('invokes', []) 
    contains = code_deps.get(start_code, {}).get('deps', {}).get('contains', [])
    
    queue = deque()
    for invoke in invokes:
        queue.append((invoke, 1))
    for contain in contains:
        queue.append((contain, 0))
    visited = set()
    
    while queue:
        current_code, depth = queue.popleft()
        
        if current_code == target_code:
            return [current_code, depth]
        if current_code in visited:
            continue
        
        visited.add(current_code)
        
        invokes = code_deps.get(current_code, {}).get('deps', {}).get('invokes', [])
        
        for invoke in invokes:
            if invoke not in visited:
                queue.append((invoke, depth + 1))
                if code_info.get(invoke, {}).get('type') == 'class':
                    init_pattern = invoke + ".__init__"
                    if (init_pattern in code_info) and (init_pattern not in visited):
                        queue.append((init_pattern, depth + 1))
    
    return []
'''
def find_all_dependencies_path(code_deps, code_name, visited=None):
    """
    Find all dependencies for a given code name in the code dependencies.
    
    :param code_deps: Dictionary containing code dependencies.
    :param code_name: Name of the code to find dependencies for.
    :param visited: Set to keep track of visited codes to avoid cycles.
    :return: List of lists, where each inner list is a path of dependencies.
    """
    if visited is None:
        visited = set()
    
    if code_name in visited:
        return []
    
    visited.add(code_name)
    
    dependencies_path = []
    invokes = code_deps.get(code_name, {}).get('deps', {}).get('invokes', []) + code_deps.get(code_name, {}).get('deps', {}).get('contains', []) + code_deps.get(code_name, {}).get('deps', {}).get('inherits', [])
    
    if not invokes:
        return [[code_name]]
    
    for invoke in invokes:
        sub_paths = find_all_dependencies_path(code_deps, invoke, visited)
        for sub_path in sub_paths:
            dependencies_path.append([code_name] + sub_path)
    
    return dependencies_path
'''

def find_all_deps(code_deps, code_name):
    """
    Find all dependencies for a given code name in the code dependencies.
    
    :param code_deps: Dictionary containing code dependencies.
    :param code_name: Name of the code to find dependencies for.
    :return: List of dependencies for the given code name.
    """
    if code_name not in code_deps:
        return []
    
    deps = code_deps[code_name].get('deps', {})
    invokes = deps.get('invokes', [])
    contains = deps.get('contains', [])
    inherits = deps.get('inherits', [])

    further_deps = []
    for contained in contains:
        con_deps = code_deps.get(contained, {}).get('deps', {})
        further_deps += con_deps.get('invokes', [])
    
    return list(set(invokes + contains + inherits + further_deps))

def process_methods2class(code_list, code_info):
    fn_codes = []
    for code_tested in code_list:
        info = code_info.get(code_tested, {})
        if info.get('type') == 'method':
            class_name = info.get('class', '')
            if class_name:
                if class_name not in fn_codes:
                    fn_codes.append(class_name)
        else:
            if code_tested not in fn_codes:
                fn_codes.append(code_tested)
    return fn_codes
                    

def prepare_data(pr_data_path, repo_data_path, repo_saved_dir, token, timeout=1800):
    """
    处理爬下来的数据，生成补丁和测试用例等信息，保存到指定目录。
    :param pr_data_path: Path to the directory containing pull request data files.
    :param repo_data_path: Path to the directory containing repository data files.
    :param repo_saved_dir: Directory to save processed data.
    :param token: GitHub token for authentication.

    :在repo_saved_dir中保存以下信息：
    - ckpt.json: 记录已经处理过的仓库和PR，避免重复处理， 程序报错可以自动加载检查点并继续
    - iteration_data_info.json: 记录处理的总测试用例数、修复的代码未被测试直接调用的次数、处理的PR数量等统计信息
    - processed_data: 目录，保存每个仓库处理后的数据，每个仓库一个子目录，子目录名为仓库名，如果没有符合规则的repo，则不创建子目录
    """
    data_keys = ['repo_name', 'base_commit', 'pr_id', 'pr_patch', 'code_patch', 'test_patch', 'head_full_code', 'head_mask_code', 'base_full_code', 'base_mask_code', 'tested_code', 'pre_code_info', 'post_code_info', 'test_cases', 'test_invoke_path', 'FAIL_TO_PASS', 'FASS_TO_PASS', 'time']
    ind = 0
    ckpt_path = os.path.join(repo_saved_dir, "ckpt.json")
    if os.path.exists(ckpt_path):
        with open(ckpt_path, "r", encoding="utf-8") as f:
            ckpt_data = json.load(f)
    else:
        ckpt_data = {}
    
    it_data_path = os.path.join(repo_saved_dir, "iteration_data_info.json")
    if os.path.exists(it_data_path):
        with open(it_data_path, "r", encoding="utf-8") as f:
            iteration_data_info = json.load(f)
    else:
        iteration_data_info = {"total_tests": 0, "fixed_code_not_invoke": 0, "num_prs": 0}

    all_test_num = iteration_data_info.get("total_tests", 0)
    fixed_code_not_invoke = iteration_data_info.get("fixed_code_not_invoke", 0)
    num_prs = iteration_data_info.get("num_prs", 0)
    for repo_info in _yeld_repo_data(pr_data_path, repo_data_path):
        benchmark_data = []
        repo_name = repo_info['full_name']
        if repo_name in ckpt_data:
            if len(ckpt_data[repo_name]) == len(repo_info['pulls']):
                logging.info(f"Repository {repo_name} already processed, skipping...")
                continue
        else:
            ckpt_data[repo_name] = []
        tem_repo_saved_dir = str(os.path.join(repo_saved_dir, repo_name.split("/")[-1]))
        clone_or_update_repo(repo_name, tem_repo_saved_dir, token)
        default_branch = get_default_branch(tem_repo_saved_dir)
        for pr in repo_info["pulls"]:
            try:
                signal.alarm(timeout)
                if pr["pull_number"] in ckpt_data[repo_name]:
                    logging.info(f"Pull request {pr['pull_number']} already processed, skipping...")
                    continue
                else:
                    ckpt_data[repo_name].append(pr["pull_number"])
                pr_data = {key: None for key in data_keys}
                pr_data['repo_name'] = repo_name
                # pr_data['repo_version'] = "" # TODO: Add repo version if available

                if pr["state"] != "closed":
                    logging.info(f"Pull request {pr['pull_number']} is not closed, skipping...")
                    continue
                base_commit = pr["base"]["sha"]
                pr_data['base_commit'] = base_commit
                pr_data['pr_id'] = pr["pull_number"]

                checkout_success = checkout_commit(tem_repo_saved_dir, base_commit)
                if not checkout_success:
                    logging.info(f"Failed to checkout commit {base_commit} for PR {pr['pull_number']} in {repo_name}, skipping...")
                    continue
                logging.info("Parsing code dependencies and functions/classes...")

                # TODO: Add patch and analyze the code
                # patch_dict : list = pr["patches"]
                test_patch = ""
                code_patch = ""
                test_files = []
                all_files = []
                # patch_string = get_full_diff(repo_name, pr["pull_number"], token)
                patch_string = pr["pr_diff"]
                
                # patch first for efficiency
                patch_result = add_patch(tem_repo_saved_dir, patch_string)
                if not patch_result:
                    logging.info(f"Failed to apply patch for PR {pr['pull_number']} in {repo_name}, skipping...")
                    restore_repo(tem_repo_saved_dir)
                    checkout_success = checkout_commit(tem_repo_saved_dir, default_branch)
                    if not checkout_success:
                        shutil.rmtree(tem_repo_saved_dir)
                        clone_or_update_repo(repo_name, tem_repo_saved_dir, token)
                    continue
                else:
                    restore_repo(tem_repo_saved_dir)

                pre_code_deps, pre_folders = build_json_graph(repo_path=tem_repo_saved_dir, global_import=False)
                pre_code_info = extract_classes_and_functions_from_repo(tem_repo_saved_dir)
                pre_repo = Repo_file_container(tem_repo_saved_dir)
                patch_info = {}
                code_patch_info = {}
                test_patch_info = {}
                for hunk in PatchSet(patch_string):
                    changed_lines = _parse_patch_with_line_numbers_for_file(str(hunk))
                    if hunk.path not in patch_info:
                        patch_info[hunk.path] = {'added': [], 'removed': []}
                    patch_info[hunk.path]['added'] += changed_lines['added']
                    patch_info[hunk.path]['removed'] += changed_lines['removed']
                    if any(
                        test_word in hunk.path for test_word in ["test", "tests", "e2e", "testing"]
                    ):
                        test_patch += str(hunk)
                        test_files.append(hunk.path)
                        if hunk.path not in test_patch_info:
                            test_patch_info[hunk.path] = {'added': [], 'removed': []}
                        test_patch_info[hunk.path]['added'] += changed_lines['added']
                        test_patch_info[hunk.path]['removed'] += changed_lines['removed']
                    else:
                        code_patch += str(hunk)
                        if hunk.path not in code_patch_info:
                            code_patch_info[hunk.path] = {'added': [], 'removed': []}
                        code_patch_info[hunk.path]['added'] += changed_lines['added']
                        code_patch_info[hunk.path]['removed'] += changed_lines['removed']
                    if hunk.path not in all_files:
                        all_files.append(hunk.path)
                pr_data['pr_patch'] = patch_string
                pr_data['code_patch'] = code_patch
                pr_data['test_patch'] = test_patch
                logging.info(f"Adding pr patch for PR {pr['pull_number']} in {repo_name}...")
                patch_result = add_patch(tem_repo_saved_dir, patch_string)
                if not patch_result:
                    logging.info(f"Failed to apply patch for PR {pr['pull_number']} in {repo_name}, skipping...")
                    restore_repo(tem_repo_saved_dir)
                    checkout_success = checkout_commit(tem_repo_saved_dir, default_branch)
                    if not checkout_success:
                        shutil.rmtree(tem_repo_saved_dir)
                        clone_or_update_repo(repo_name, tem_repo_saved_dir, token)
                    continue
                logging.info(f"Parsing code dependencies and functions/classes after patch...")
                if set(patch_info.keys()) != set(all_files):
                    logging.info("Patch keys do not match the expected keys.")
                post_code_deps, post_folders = build_json_graph(repo_path=tem_repo_saved_dir, global_import=False)
                post_code_info = extract_classes_and_functions_from_repo(tem_repo_saved_dir)
                post_repo = Repo_file_container(tem_repo_saved_dir)

                add_base_codes = find_code_by_patch(post_code_info, post_folders, code_patch_info, diff_key='added')
                remove_base_codes = find_code_by_patch(pre_code_info, pre_folders, code_patch_info, diff_key='removed')
                # Double check if the code is really added or removed
                changed_base_codes = add_base_codes + remove_base_codes
                # changed_base_codes = changed_base_codes + process_methods2class(changed_base_codes, post_code_info)
                changed_base_codes = list(set(changed_base_codes))
                changed_base_codes_ = tested_function_checker(pre_code_info, post_code_info, pre_repo, post_repo, changed_base_codes)
                if changed_base_codes_ != changed_base_codes:
                    logging.info(f"Some changed base codes are not satisfied skipping PR {pr['pull_number']} in {repo_name}: \n{set(changed_base_codes) - set(changed_base_codes_)}")
                    restore_repo(tem_repo_saved_dir)
                    checkout_success = checkout_commit(tem_repo_saved_dir, default_branch)
                    if not checkout_success:
                        shutil.rmtree(tem_repo_saved_dir)
                        clone_or_update_repo(repo_name, tem_repo_saved_dir, token)
                    continue
                add_base_tests = process_methods2class(find_code_by_patch(post_code_info, post_folders, test_patch_info, diff_key='added'), post_code_info)
                remove_base_tests = process_methods2class(find_code_by_patch(pre_code_info, pre_folders, test_patch_info, diff_key='removed'), pre_code_info)
                tem_changed_base_tests = add_base_tests + remove_base_tests
                tem_changed_base_tests = list(set(tem_changed_base_tests))
                changed_base_tests = []
                for test_file in tem_changed_base_tests:
                    if test_file in post_code_info:
                        changed_base_tests.append(test_file)
                if len(changed_base_tests) == 0:
                    logging.info(f"No changed base tests found for PR {pr['pull_number']} in {repo_name}, skipping...")
                    restore_repo(tem_repo_saved_dir)
                    checkout_success = checkout_commit(tem_repo_saved_dir, default_branch)
                    if not checkout_success:
                        shutil.rmtree(tem_repo_saved_dir)
                        clone_or_update_repo(repo_name, tem_repo_saved_dir, token)
                    continue
                # test_dic = find_test_dict_for_codes(post_code_deps)

                test_invokes_dict = {}
                # invokes_path_dict = {}
                logging.info(f"Finding test invokes and paths for PR {pr['pull_number']} in {repo_name}...")
                for test_file in changed_base_tests:
                    temp_invokes = find_invokes_for_codes(post_code_deps, test_file)
                    fn_invoks = []
                    for code_name in temp_invokes:
                        if post_code_info.get(code_name, {}).get('type', '') != 'class':
                            fn_invoks.append(code_name)
                        else:
                            fn_invoks.append(code_name)
                            init_class = code_name + ".__init__"
                            if (init_class in post_code_info) and (init_class not in temp_invokes):
                                fn_invoks.append(init_class)
                    test_invokes_dict[test_file] = tested_function_checker(pre_code_info, post_code_info, pre_repo, post_repo, fn_invoks)
                
                # all_tested_codes = list(set(test_invokes) & set(changed_base_codes))
                # all_tested_codes = changed_base_codes.copy()
                # all_tested_codes = tested_function_checker(pre_code_info, post_code_info, pre_repo, post_repo, all_tested_codes)

                
                # error_code4test = {}
                all_error_codes = []
                invokes_path_dict = {}
                for test_file in changed_base_tests:
                    # error_code4test[test_file] = []
                    invokes_path_dict[test_file] = {}
                    for changed_code in changed_base_codes:
                        code_path = bfs_finding_target_code(post_code_deps, test_file, changed_code, post_code_info)
                        if code_path != []:
                            # error_code4test[test_file].append(changed_code)
                            invokes_path_dict[test_file][changed_code] = code_path[1]
                            if changed_code not in all_error_codes:
                                all_error_codes.append(changed_code)

                
                test_invokes_dict_fn = test_invokes_dict
                # for test_n, codes in test_invokes_dict.items():
                #     test_invokes_dict_fn[test_n] = process_methods2class(codes, post_code_info)
                    
                all_tested_codes= []
                for val in test_invokes_dict_fn.values():
                    all_tested_codes += val
                all_tested_codes = list(set(all_tested_codes))
                if len(all_tested_codes) == 0:
                    logging.info(f"No valid tested codes found for PR {pr['pull_number']} in {repo_name}, skipping...")
                    restore_repo(tem_repo_saved_dir)
                    checkout_success = checkout_commit(tem_repo_saved_dir, default_branch)
                    if not checkout_success:
                        shutil.rmtree(tem_repo_saved_dir)
                        clone_or_update_repo(repo_name, tem_repo_saved_dir, token)
                    continue
                if len(all_error_codes) == 0:
                    logging.info(f"No valid error codes found for PR {pr['pull_number']} in {repo_name}, skipping...")
                    restore_repo(tem_repo_saved_dir)
                    checkout_success = checkout_commit(tem_repo_saved_dir, default_branch)
                    if not checkout_success:
                        shutil.rmtree(tem_repo_saved_dir)
                        clone_or_update_repo(repo_name, tem_repo_saved_dir, token)
                    continue
                
                all_code_to_process = list(set(all_tested_codes + all_error_codes))
                all_code_to_process = all_code_to_process + process_methods2class(all_code_to_process, post_code_info)
                all_code_to_process = list(set(all_code_to_process))
                temp_data = set(all_tested_codes) & set(all_error_codes)
                if len(temp_data) < len(set(all_error_codes)):
                    logging.info(f"Some fixed codes are not directly invoked in tests {set(all_error_codes) - temp_data}...")
                    fixed_code_not_invoke += 1

                pre_code_full = {}
                post_code_full = {}
                pre_code_mask = {}
                post_code_mask = {}
                no_exit_count = 0
                for code in all_code_to_process:
                    if code not in pre_code_info or code not in post_code_info:
                        logging.info(f"Code {code} not found in pre or post code info, skipping...")
                        no_exit_count += 1
                        continue
                    pre_code_full[code] = get_code_content(pre_repo, code, pre_code_info)
                    post_code_full[code] = get_code_content(post_repo, code, post_code_info)
                    pre_code_mask[code] = get_code_content(pre_repo, code, pre_code_info, mask=True)
                    post_code_mask[code] = get_code_content(post_repo, code, post_code_info, mask=True)
                if no_exit_count > 0:
                    logging.info(f"Skipped {no_exit_count} codes that do not exist in pre or post code info.")
                    restore_repo(tem_repo_saved_dir)
                    checkout_success = checkout_commit(tem_repo_saved_dir, default_branch)
                    if not checkout_success:
                        shutil.rmtree(tem_repo_saved_dir)
                        clone_or_update_repo(repo_name, tem_repo_saved_dir, token)
                    continue

                pr_data['base_full_code'] = pre_code_full
                pr_data['base_mask_code'] = pre_code_mask
                pr_data['head_full_code'] = post_code_full
                pr_data['head_mask_code'] = post_code_mask
                pre_code_info_flitered = {}
                post_code_info_flitered = {}
                for code in all_code_to_process:
                    if code not in pre_code_info or code not in post_code_info:
                        logging.info(f"Code {code} not found in pre or post code info, skipping...")
                        continue
                    post_in = post_code_info[code]
                    pre_in = pre_code_info[code]

                    post_in['deps'] = find_all_deps(post_code_deps, code)
                    pre_in['deps'] = find_all_deps(pre_code_deps, code)

                    pre_code_info_flitered[code] = pre_in
                    post_code_info_flitered[code] = post_in
                    if pre_code_info[code].get('type') == 'class':
                        for method in pre_code_info[code].get('methods', []):
                            if method not in pre_code_info:
                                continue
                            m_pre_in = pre_code_info[method]
                            m_pre_in['deps'] = find_all_deps(pre_code_deps, method)
                            pre_code_info_flitered[method] = m_pre_in
                    if post_code_info[code].get('type') == 'class':
                        for method in post_code_info[code].get('methods', []):
                            if method not in post_code_info:
                                continue
                            m_post_in = post_code_info[method]
                            m_post_in['deps'] = find_all_deps(post_code_deps, method)
                            post_code_info_flitered[method] = m_post_in
                pr_data['FAIL_TO_PASS'] = []
                pr_data['FASS_TO_PASS'] = []
                pr_data['time'] = pr["updated_at"]

                # checkout_success = checkout_commit(tem_repo_saved_dir, default_branch)
                # if not checkout_success:
                #     shutil.rmtree(tem_repo_saved_dir)
                #     clone_or_update_repo(repo_name, tem_repo_saved_dir)
                pr_data['invokes_code'] = test_invokes_dict_fn
                pr_data['fixed_code'] = all_error_codes
                pr_data['changed_code'] = changed_base_codes
                
                pr_data['tested_code'] = all_tested_codes
                pr_data['pre_code_info'] = pre_code_info_flitered
                pr_data['post_code_info'] = post_code_info_flitered

                pr_data['test_cases'] = list(test_invokes_dict_fn.keys())
                pr_data['test_invoke_path'] = invokes_path_dict
                all_test_num += len(pr_data['test_cases'])
                num_prs += 1

                    
                # Restore the repository to its original state
                patch_success = {}
                restore_repo(tem_repo_saved_dir)
                for patch_key in ["code_patch", "test_patch"]:
                    if pr_data[patch_key]:
                        logging.info(f"Adding {patch_key} for PR {pr['pull_number']} in {repo_name}...")
                        patch_result = add_patch(tem_repo_saved_dir, pr_data[patch_key])
                        patch_success[patch_key] = patch_result
                        restore_repo(tem_repo_saved_dir)
                pr_data['patch_success'] = patch_success
                benchmark_data.append(pr_data)
                checkout_success = checkout_commit(tem_repo_saved_dir, default_branch)
                if not checkout_success:
                    shutil.rmtree(tem_repo_saved_dir)
                    clone_or_update_repo(repo_name, tem_repo_saved_dir, token)
                logging.info(f"Successfully processed {len(benchmark_data)} benchmark data entries with {all_test_num} tests.")
            except TimeoutError:
                logging.info(f"TimeoutError occurred while processing PR {pr['pull_number']} in {repo_name}, skipping to next PR...")
                restore_repo(tem_repo_saved_dir)
                checkout_success = checkout_commit(tem_repo_saved_dir, default_branch)
                if not checkout_success:
                    shutil.rmtree(tem_repo_saved_dir)
                    clone_or_update_repo(repo_name, tem_repo_saved_dir, token)
                continue
            
        logging.info(f"Processed {ind} repositories.")
        if len(benchmark_data) != 0:
            data_saved_dir = os.path.join(repo_saved_dir, "processed_data", repo_name.replace("/", "_"))
            if not os.path.exists(data_saved_dir):
                os.makedirs(data_saved_dir)
            with open(os.path.join(data_saved_dir, "benchmark_data.json"), 'w', encoding='utf-8') as f:
                json.dump(benchmark_data, f, indent=4, ensure_ascii=False)
            iteration_data_info["total_tests"] = all_test_num
            iteration_data_info["fixed_code_not_invoke"] = fixed_code_not_invoke
            iteration_data_info["num_prs"] = num_prs
            with open(it_data_path, 'w', encoding='utf-8') as f:
                json.dump(iteration_data_info, f, indent=4, ensure_ascii=False)
        with open(ckpt_path, "w", encoding="utf-8") as f:
            json.dump(ckpt_data, f, indent=4, ensure_ascii=False)
        ind += 1
        
        shutil.rmtree(tem_repo_saved_dir)
    return benchmark_data
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process benchmark data.")
    parser.add_argument("--pr_data_path", type=str, required=False, default="/home/superbench/jiaxiang/blob/github_storage/report/python_test_diffs_20250821", help="Path to the PR diff data.")
    # 之前爬的和pr有关的数据
    parser.add_argument("--repo_data_path", type=str, required=False, default="/home/superbench/jiaxiang/blob/github_storage/report/python_repo_data_json", help="Path to the repository data.")
    # 之前爬的包含repo信息的数据
    parser.add_argument("--repo_saved_dir", type=str, required=False, default="/home/superbench/jiaxiang/Dev-TestCaseGen/build_benchmark/temp_repos", help="Directory to save temporary repositories and datasets.")
    # 数据保存地址
    parser.add_argument("--token", type=str, required=False, default="", help="GitHub token for authentication.")
    parser.add_argument("--timeout", type=int, required=False, default=1800, help="Timeout for processing each PR in seconds.")

    args = parser.parse_args()
    pr_data_path = args.pr_data_path
    repo_data_path = args.repo_data_path
    repo_saved_dir = args.repo_saved_dir
    token = args.token
    timeout = args.timeout
    if not os.path.exists(repo_saved_dir):
        os.makedirs(repo_saved_dir)
    log_file = os.path.join(repo_saved_dir, "process_data.log")
    logging.basicConfig(
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),
            logging.StreamHandler()],
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            force=True
    )
    
    prepare_data(pr_data_path, repo_data_path, repo_saved_dir, token)



    
