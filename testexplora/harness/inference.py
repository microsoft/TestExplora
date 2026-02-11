from utils.repo_manager import RepoManager
from utils.data_manager import load_data
from utils.parse_repo import extract_classes_and_functions_from_repo, Repo_file_container
from utils.prepare_prompts import get_prompts, get_prompts_agent
# from unidiff import PatchSet
import logging
import os
import argparse
from call_pipeline import call_map
import shutil
import yaml
import json
import subprocess

NAIVE_LLM_LIST = ["o3-mini", "gpt-4o", "gemini-2.5-pro", "gemini-2.5-flash", "Codellama-34B", "glm-4-9b", "Qwen3-Coder-30B", "o4-mini", "gpt-5-mini", "gpt-5", "r1", "claude_sonnet"]

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")

def replace_code_infile(repo_file_path, pre_code, post_code):
    with open(repo_file_path, 'r') as file:
        content = file.read()
    
    if pre_code in content:
        content = content.replace(pre_code, post_code)
        with open(repo_file_path, 'w') as file:
            file.write(content)
        return True
    else:
        logging.warning(f"Pre-code snippet not found in {repo_file_path}.")
        return False

def get_dep_keys(code_key, code_info, full_code_info):
    deps = code_info.get(code_key, {}).get("deps", [])
    if not deps:
        return []
    dep_keys = []
    for dep in deps:
        dep_info = full_code_info.get(dep)
        if not dep_info:
            continue
        if dep_info["type"] == "method":
            dep_code = dep_info["class"]
        else:
            dep_code = dep
        if dep_code != code_key:
            dep_keys.append(dep_code)
    return list(set(dep_keys))


class Repo_data_processor:
    def __init__(self, repo_manager, code_info, code_origins, code_masks):
        self.repo_manager = repo_manager
        self.code_info = code_info
        self.code_origins = code_origins
        self.code_masks = code_masks
        self.repo_container = None

    def prepare_repo(self, test_invokes, test_type):

        self.repo_container = Repo_file_container(repo_saved_path=self.repo_manager.repo_testbed_dir)

        # Extract classes and functions from the repository
        repo_path = self.repo_manager.repo_testbed_dir
        
        procrssed = []
        deps_data = {}
        invoke_full_codes = {}
        fn_invokes = []
        for invoke in test_invokes:
            invoke_info = self.code_info.get(invoke)
            if not invoke_info:
                logging.warning(f"Invoke {invoke} not found in code info.")
                continue
            if invoke_info["type"] == "method":
                fn_invoke = invoke_info["class"]
            else:
                fn_invoke = invoke
            fn_invokes.append(fn_invoke)
        for invoke in test_invokes:
            invoke_info = self.code_info.get(invoke)
            if not invoke_info:
                logging.warning(f"Invoke {invoke} not found in code info.")
                continue
            if invoke_info["type"] == "method":
                fn_invoke = invoke_info["class"]
            else:
                fn_invoke = invoke
            
            if fn_invoke in procrssed:
                continue

            code_file = invoke_info["file"]
            repo_file_path = os.path.join(repo_path, code_file)

            code_origin = self.code_origins.get(fn_invoke)
            code_mask = self.code_masks.get(fn_invoke)
            if not code_origin or not code_mask:
                logging.warning(f"Origin or mask not found for invoke {fn_invoke}.")
                continue

            if not(test_type == "whitebox" or test_type == "hint"):
                replace_success = replace_code_infile(repo_file_path, code_origin, code_mask)
            # if not replace_success:
            #     logging.error(f"Failed to replace code in file {repo_file_path}.")
            #     return False
            procrssed.append(fn_invoke)
            invoke_full_codes[fn_invoke] = code_mask
            deps = get_dep_keys(fn_invoke, self.code_info, self.repo_container.code_lines)
            for dep in deps:
                if (dep not in deps_data) and (dep not in test_invokes) and (dep not in fn_invokes):
                    deps_data[dep] = self.repo_container.get_code_lines(dep)
        
        return deps_data, invoke_full_codes

def infer_repos(args):
    # Load data from the specified JSON file

    data_path = args.data_path
    repo_testbed_dir = args.repo_testbed_dir
    data, allpr_len = load_data(data_path, lite=args.lite, subset=args.subset)

    test_patch_dir = os.path.join(repo_testbed_dir, "test_patches.json")
    if os.path.exists(test_patch_dir):
        with open(test_patch_dir, "r", encoding="utf-8") as f:
            all_test_patch = json.load(f)
    else:
        all_test_patch = {}

    ind = 0
    repo_count_step = 1
    pr_count_step = 1
    for repo_name, prs in data.items():
        logging.info(f"Processing repository {repo_name} ({repo_count_step}/{len(data)})")
        repo_count_step += 1
        test_case_dict = {}
        all_has_doc_dict = {}
        for pr in prs:
            if pr["pr_id"] not in test_case_dict:
                test_case_dict[pr["pr_id"]] = []
            all_invokes = []
            for test_case, test_invokes in pr["invokes_code"].items():
                if len(test_invokes) == 0:
                    continue
                test_case_dict[pr["pr_id"]].append(test_case)
                all_invokes.extend(test_invokes)
            has_doc = []
            for invoke in all_invokes:
                if pr["post_code_info"][invoke]["docstring"].strip() != "":
                    has_doc.append(True)
                else:
                    has_doc.append(False)
            all_has_doc_dict[pr["pr_id"]] = all(has_doc)

        if repo_name not in all_test_patch:
            if args.use_generated_doc:
                missing_prs = [pr["pr_id"] for pr in prs]
                all_test_patch[repo_name] = {}
            else:
                missing_prs = []
                for prk, prv in all_has_doc_dict.items():
                    if prv:
                        missing_prs.append(prk)
                        if repo_name not in all_test_patch:
                            all_test_patch[repo_name] = {}
        else:
            missing_prs = []
            for prk, prv in test_case_dict.items():
                if len(all_test_patch[repo_name].get(prk, {})) < len(prv):
                    if args.use_generated_doc:
                        missing_prs.append(prk)
                    else:
                        if all_has_doc_dict[prk]:
                            missing_prs.append(prk)
                         
        if len(missing_prs) == 0:
            logging.info(f"All PRs for repository {repo_name} have been processed. Skipping...")
            continue
        pr_count_step += len(test_case_dict) - len(missing_prs)
        repo_manager = RepoManager(repo_name, repo_testbed_dir)
        repo_manager.clone_or_update_repo()
        for pr in prs:
            logging.info(f"Processing PR {pr['pr_id']} ({pr_count_step}/{allpr_len})")
            pr_count_step += 1
            if pr["pr_id"] not in missing_prs:
                logging.info(f"PR {pr['pr_id']} for repository {repo_name} has been processed. Skipping...")
                continue

            if pr["pr_id"] not in all_test_patch[repo_name]:
                all_test_patch[repo_name][pr["pr_id"]] = {}
            base_commit = pr["base_commit"]
            checkout_success = repo_manager.checkout_commit(base_commit)
            if not checkout_success:
                logging.info(f"Failed to checkout commit {base_commit} for repository {repo_name}. Skipping this PR.")
                repo_manager.restore_repo()
                continue
            
            if not (args.test_type == "whitebox" or args.test_type == "hint"):
                logging.warning("The Repo content is masked.")
                repo_processor = Repo_data_processor(repo_manager, pr["pre_code_info"], pr["base_full_code"], pr["base_mask_code"])
            else:
                # For whitebox testing, do not use masked code for the buggy version
                logging.warning("The Repo content is NOT masked.")
                repo_processor = Repo_data_processor(repo_manager, pr["pre_code_info"], pr["base_full_code"], pr["base_full_code"])
            for test_case, test_invokes in pr["invokes_code"].items():
                temp = test_case.split(":")
                if len(temp) != 2:
                    logging.warning(f"Unexpected test case format: {test_case}. Skipping.")
                    file_path_str = ""
                    for te in temp:
                        file_path_str += te + ":"
                        if te.endswith(".py"):
                            break
                else:
                    file_path_str = temp[0]
                saved_test_path_str = file_path_str.replace(".py", "_generated.py")
                logging.info(f"Repository: {repo_name}, PR ID: {pr['pr_id']}, Test Case: {test_case}, Invokes: {test_invokes}")
                if len(test_invokes) == 0:
                    repo_manager.restore_repo()
                    continue
                invoke_deps_data, invoke_full_codes = repo_processor.prepare_repo(test_invokes, args.test_type)
                invoke_deps = {k: pr["pre_code_info"][k]["deps"] for k in test_invokes}
                # invoke_full_codes = {k: pr["base_mask_code"].get(k, "") for k in test_invokes}
                documentation = {}
                if args.use_generated_doc:
                    documentation = pr["documentation"]
                else:
                    for k in test_invokes:
                        doc = pr["post_code_info"][k]["docstring"]
                        if doc:
                            documentation[k] = doc

                hint_code = {}
                for code_n in pr["changed_code"]:
                    hint_code[code_n] = repo_processor.repo_container.get_code_lines(code_n)['full_code']
                
                hints = {"patch": pr["code_patch"], "code": hint_code}

                prompts = get_prompts(pr["pre_code_info"], invoke_deps_data, invoke_deps, invoke_full_codes, test_case.split(":")[-1], 
                                      documentation, omit_dep_code=args.omit_dep_code, test_type=args.test_type, omit_dep=args.omit_dep, repo_name=repo_name, hints=hints,
                                      use_hint=args.use_hint)

                if args.model in NAIVE_LLM_LIST:
                    logging.info(f"Generated prompt for {test_case}:\n{prompts}\n")
                    call_result = call_map[args.model](prompts, repo_path=repo_manager.repo_testbed_dir)
                else:
                    prompts = get_prompts_agent(pr["pre_code_info"], invoke_deps_data, invoke_deps, invoke_full_codes, test_case.split(":")[-1], documentation, omit_dep_code=args.omit_dep_code, 
                                                test_type=args.test_type, omit_dep=args.omit_dep, repo_name=repo_name, hints=hints,
                                                use_hint=args.use_hint, fobbidden_commands="wopython" in args.model, refine_explo="refineexplo" in args.model)
                    logging.info(f"Generated prompt for {test_case}:\n{prompts}\n") 
                    try:
                        copy_repo_path = repo_manager.copy_repo()
                    except Exception as e:
                        logging.error(f"Failed to copy repository for safe inference: {e}")
                        all_test_patch[repo_name][pr["pr_id"]][test_case] = {"patch_string": "", "saved_test_path_str": saved_test_path_str, "test_code": "", "raw_output": ""}
                        repo_manager.rm_copy_repo()
                        repo_manager.restore_repo()
                        continue
                    call_result = call_map[args.model](prompts, repo_path=copy_repo_path)
                    repo_manager.rm_copy_repo()

                if (call_result is None) or (len(call_result) == 0):
                    logging.info(f"call result {call_result} is invalid")
                    logging.error(f"Model call failed for {test_case}.")
                    all_test_patch[repo_name][pr["pr_id"]][test_case] = {"patch_string": "", "saved_test_path_str": saved_test_path_str, "test_code": "", "raw_output": ""}
                    repo_manager.restore_repo()
                    continue
                generated_code = call_result[0]
                logging.info(f"Generated code for {test_case}:\n{generated_code}\n")
                repo_manager.restore_repo()
                if "ispatch" not in call_result:
                    test_save_path = os.path.join(repo_manager.repo_testbed_dir, saved_test_path_str)
                    os.makedirs(os.path.dirname(test_save_path), exist_ok=True)
                    with open(test_save_path, "w") as f:
                        f.write(generated_code)
                    logging.info(f"Generated test case saved to {saved_test_path_str}.")
                    try:
                        repo_manager.add_changes(saved_test_path_str)
                    except Exception as e:
                        logging.error(f"Failed to add changes for {saved_test_path_str}: {e}")
                        # all_test_patch[repo_name][pr["pr_id"]][test_case] = {"patch_string": "", "saved_test_path_str": saved_test_path_str, "test_code": generated_code}
                        repo_manager.restore_repo()
                        continue
                    diff_file_path = repo_manager.get_diff(repo_testbed_dir, cached=True)
                    with open(diff_file_path, 'r') as diff_file:
                        patch_string = diff_file.read()
                    all_test_patch[repo_name][pr["pr_id"]][test_case] = {"patch_string": patch_string, "saved_test_path_str": saved_test_path_str, "test_code": generated_code, "raw_output": call_result[-1] if args.model in NAIVE_LLM_LIST else ""}
                else:
                    all_test_patch[repo_name][pr["pr_id"]][test_case] = {"patch_string": generated_code, "saved_test_path_str": saved_test_path_str, "test_code": "", "raw_output": call_result[-1] if args.model in NAIVE_LLM_LIST else ""}

                if len(call_result) >=3:
                    traj_content = call_result[2]
                    traj_save_path = os.path.join(repo_testbed_dir, "trajectory", repo_name, f"pr_{pr['pr_id']}", f"{test_case.replace(':', '_').replace('/', '_')}_trajectory.json")
                    if not os.path.exists(os.path.dirname(traj_save_path)):
                        os.makedirs(os.path.dirname(traj_save_path), exist_ok=True)
                    with open(traj_save_path, "w") as f:
                        f.write(traj_content)
                    logging.info(f"Generated trajectory saved to {traj_save_path}.")
                    # assert False, "Just to check trajectory saving."

                repo_manager.restore_repo()

                if ind % args.ckpt_step == 0:
                    with open(test_patch_dir, "w", encoding="utf-8") as f:
                        json.dump(all_test_patch, f, indent=4)
                    logging.info(f"Checkpoint saved at iteration {ind}.")
                ind += 1
        logging.info(f"Completed processing repository {repo_name}.")
        
        # Clean up Docker containers after processing each repository
        try:
            logging.info("Cleaning up Docker containers...")
            subprocess.run(
                "docker rm -f $(docker ps -aq --filter name=openhands) 2>/dev/null || true",
                shell=True,
                check=False
            )
            logging.info("Docker cleanup completed.")
        except Exception as e:
            logging.warning(f"Docker cleanup failed: {e}")
        
        shutil.rmtree(repo_manager.repo_testbed_dir)
    return all_test_patch

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Inference on repositories to generate test cases.")
    arg_parser.add_argument("--lite", type=str2bool, default=True, help="Whether to use the lite version of the benchmark.")
    arg_parser.add_argument("--subset", type=str2bool, default=True, help="Whether to use a subset of the benchmark for quick testing.")
    arg_parser.add_argument("--data_path", type=str, default="", help="Path to the JSON data file.")
    arg_parser.add_argument("--repo_testbed_dir", type=str, default="", help="Directory to clone repositories into.")
    arg_parser.add_argument("--ckpt_step", type=int, default=50, help="Pre step to save a checkpoint.")
    arg_parser.add_argument("--test_type", type=str, default="whitebox", choices=["whitebox", "graybox", "blackbox"], help="Type of tests to generate.")
    arg_parser.add_argument("--use_generated_doc", type=str2bool, default=False, help="Whether to use generated documentation.")
    arg_parser.add_argument("--omit_dep_code", type=str2bool, default=True, help="Whether to omit dependencies in the prompt.")
    arg_parser.add_argument("--model", type=str, default="sweagent-gpt5mini", help="Model to use for inference.")
    arg_parser.add_argument("--omit_dep", type=str2bool, default=False, help="Whether to omit dependencies in the prompt.")
    arg_parser.add_argument("--use_hint", type=str2bool, default=False, help="Whether to use hint code in the prompt.")
    args = arg_parser.parse_args()

    if args.model not in NAIVE_LLM_LIST:
        if args.test_type != "whitebox":
            raise ValueError("only whitebox testing supports advanced Agents")
    
    if args.subset:
        if not args.lite:
            raise ValueError("Only lite version supports subset=True")

    args.repo_testbed_dir = os.path.join(args.repo_testbed_dir, args.model, "exp_0")
    path_id = 0
    if args.omit_dep:
        if args.test_type != "whitebox":
            raise ValueError("only whitebox testing supports omit_dep=True")
    while os.path.exists(args.repo_testbed_dir):
        if not os.path.exists(os.path.join(args.repo_testbed_dir, "config.yaml")):
            break
        with open(os.path.join(args.repo_testbed_dir, "config.yaml"), "r") as f:
            yaml_dict = yaml.safe_load(f)
        if all(yaml_dict.get(k) == v for k, v in [("model", args.model), ("omit_dep_code", args.omit_dep_code), ("test_type", args.test_type), 
                                                  ("use_generated_doc", args.use_generated_doc), ("omit_dep", args.omit_dep), 
                                                  ("lite", args.lite), ("use_hint", args.use_hint), ("subset", args.subset)]):
            break
        args.repo_testbed_dir = args.repo_testbed_dir.replace(f"exp_{path_id}", f"exp_{path_id+1}")
        path_id += 1
    os.makedirs(args.repo_testbed_dir, exist_ok=True)
    yaml_dict = {
        "model": args.model,
        "test_type": args.test_type,
        "use_generated_doc": args.use_generated_doc,
        "omit_dep_code": args.omit_dep_code,
        "omit_dep": args.omit_dep,
        "lite": args.lite,
        "use_hint": args.use_hint,
        "subset": args.subset
    }
    with open(os.path.join(args.repo_testbed_dir, "config.yaml"), "w") as f:
        yaml.dump(yaml_dict, f)
        
    log_file = os.path.join(args.repo_testbed_dir, "generation.log")
    logging.basicConfig(
                    handlers=[
                        logging.FileHandler(log_file, mode='w', encoding='utf-8'),
                        logging.StreamHandler()],
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    force=True
    )
    all_test_patch = infer_repos(args)

    with open(os.path.join(args.repo_testbed_dir, "test_patches.json"), "w", encoding="utf-8") as f:
        json.dump(all_test_patch, f, indent=4)