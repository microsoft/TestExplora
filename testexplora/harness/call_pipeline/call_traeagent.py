import subprocess
import os
import shutil
import logging
import yaml
from unidiff import PatchSet

command_template = """trae-cli run \\
--config-file {config_path} \\
--file {prompt_file_path} \\
--working-dir="{repo_path}" \\
--must-patch \\
--patch-path {output_dir}/test.patch \\
--trajectory-file {output_dir}/trajectory.json \\
--docker-image python:3.11 \\
--docker-keep false \\
--max-steps 60
""".strip()

def get_path_content(repo_path, output_dir):
    # git add -N .
    # git diff --diff-filter=A -p > new_files.patch
    patch_path = os.path.join(output_dir, "test.patch")
    try:
        subprocess.run(["git", "add", "-N", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "diff", "--diff-filter=A", "-p"], cwd=repo_path, check=True, stdout=open(patch_path, "w"))
    except subprocess.CalledProcessError as e:
        logging.error(f"Error occurred while getting path content: {e.stderr}")
        return ""
    
    with open(patch_path, "r") as f:
        content = f.read()
    patches = PatchSet(content)

    final_patch = ""
    for patched_file in patches:
        path = getattr(patched_file, 'path', None) or getattr(patched_file, 'target_file', None)
        if path is None:
            # Fallback to a field that can represent the file
            path = patched_file.target_file if hasattr(patched_file, 'target_file') else str(patched_file)

        # Check if this is a newly added file (boolean attribute provided by unidiff)
        is_added = getattr(patched_file, 'is_added_file', None)
        if is_added is None:
            # Some versions use is_added
            is_added = getattr(patched_file, 'is_added', False)
        
        logging.info(f"Processing file: {path}, is_added: {is_added}")

        if is_added and ("generated_tests.py" in path):
            final_patch += str(patched_file)

    trajectory = ""
    traj_path = f"{output_dir}/trajectory.json"
    if os.path.exists(traj_path):
        with open(traj_path, "r") as f:
            trajectory += f.read()
    return final_patch, trajectory

    
def call_traeagent(prompts, repo_path, model_name):
    par_dir = os.path.abspath(os.path.join(repo_path, os.pardir))
    logging.info(f"Parent directory for TRAE agent output: {par_dir}")
    logging.info(f"{repo_path}")

    # assert False, "Please make sure TRAE CLI is installed and configured properly."


    output_dir = os.path.join(par_dir, "traegent_output")
    base_yaml_path = "/home/superbench/jiaxiang/my_tddbench/my_tdd_bench/harness/call_pipeline/trae_config.yaml"

    with open(base_yaml_path, "r") as f:
        config = yaml.safe_load(f)
    config["models"]["trae_agent_model"]["model"] = model_name
    config["models"]["lakeview_model"]["model"] = model_name


    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    os.makedirs(output_dir, exist_ok=True)

    config_path = os.path.join(output_dir, "traeagent_config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    prompt_path = os.path.join(output_dir, "prompts.txt")
    with open(prompt_path, "w") as f:
        f.write(prompts)

    running_command = command_template.format(
        config_path=config_path,
        prompt_file_path=prompt_path,
        repo_path=repo_path,
        output_dir=output_dir
    )

    try:
        result = subprocess.run(running_command, shell=True, check=True, capture_output=True, text=True)
        logging.info(f"SWEAgent output: {result.stdout}")
        patch, trajectory = get_path_content(repo_path, output_dir)
        return [patch, "ispatch", trajectory]
    except subprocess.CalledProcessError as e:
        logging.error(f"Error occurred while running sweagent: {e.stderr}")
        return []
