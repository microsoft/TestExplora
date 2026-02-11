import subprocess
import os
import shutil
import logging
import yaml
from unidiff import PatchSet

input_template = """
<uploaded_files>
{{working_dir}}
</uploaded_files>
I've uploaded a python code repository in the directory {{working_dir}}.
""".strip()

command_template = """sweagent run \\
  --config {config_path} \\
  --agent.model.per_instance_cost_limit=240 \\
  --env.repo.path={repo_path} \\
  --output_dir={output_dir} \\
  --problem_statement.text="This is a software testing task. Generate test cases based on the provided prompts."
""".strip()

command_template_cloudgpt = """sweagent run \\
  --config {config_path} \\
  --agent.model.per_instance_cost_limit=240 \\
  --env.repo.path={repo_path} \\
  --output_dir={output_dir} \\
  --problem_statement.text="This is a software testing task. Generate test cases based on the provided prompts."
""".strip()

MODEL_ALIASES = {
    "gpt-5": "gpt-5-20250807",
}

def get_path_content(file_path):
    files = os.listdir(file_path)
    content = ""
    trajectory = ""
    for file in files:
        if file.endswith(".yaml"):
            continue
        patch_path = os.path.join(file_path, file, f"{file}.patch")
        if not os.path.exists(patch_path):
            continue
        with open(patch_path, "r") as f:
            patch_str = f.read()
        patches = PatchSet(patch_str)

        for patched_file in patches:
            path = getattr(patched_file, 'path', None) or getattr(patched_file, 'target_file', None)
            if path is None:
                # Fallback to a field that can represent the file
                path = patched_file.target_file if hasattr(patched_file, 'target_file') else str(patched_file)
            
            is_added = getattr(patched_file, 'is_added_file', None)
            if is_added is None:
                # Some versions use is_added
                is_added = getattr(patched_file, 'is_added', False)
            
            logging.info(f"Processing file: {path}, is_added: {is_added}")

            if is_added and ("generated_tests.py" in path):
                content += str(patched_file)
        trajectory_path = os.path.join(file_path, file, f"{file}.traj")
        if os.path.exists(trajectory_path):
            with open(trajectory_path, "r") as f:
                trajectory += f.read()
    return content, trajectory

def call_sweagent(prompts, repo_path, model_name, use_python=True, refine_exploration=False):
    par_dir = os.path.abspath(os.path.join(repo_path, os.pardir))

    output_dir = os.path.join(par_dir, "sweagent_output")

    if refine_exploration and (not use_python):
        raise ValueError("refine_exploration must use python tool")

    if use_python:
        base_yaml_path = "default4testexplora-fn.yaml"
        if refine_exploration:
            base_yaml_path = "default4testexplora-refineexplo.yaml"
    else:
        base_yaml_path = "default4testexplora-wopy.yaml"
    with open(base_yaml_path, "r") as f:
        config = yaml.safe_load(f)

    config["agent"]["templates"]["instance_template"] = input_template + prompts
    # logging.info(f'SWEAgent config: {config["agent"]["templates"]["refine_template"]}')

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    os.makedirs(output_dir, exist_ok=True)

    yaml_path = os.path.join(output_dir, "sweagent_config.yaml")
    with open(yaml_path, "w") as f:
        yaml.dump(config, f)

    if ("5-mini" in model_name) or ("o4-mini" in model_name):
        running_command = command_template.format(
            config_path=yaml_path,
            model_name=model_name,
            repo_path=repo_path,
            output_dir=output_dir,
        )
    else:
        running_command = command_template_cloudgpt.format(
            config_path=yaml_path,
            model_name=MODEL_ALIASES.get(model_name, model_name),
            repo_path=repo_path,
            output_dir=output_dir,
        )

    try:
        result = subprocess.run(running_command, shell=True, check=True, capture_output=True, text=True)
        logging.info(f"SWEAgent output: {result.stdout}")
        patch, trajectory = get_path_content(os.path.join(output_dir))
        return [patch, "ispatch", trajectory]
    except subprocess.CalledProcessError as e:
        logging.error(f"Error occurred while running sweagent: {e.stderr}")
        return []

