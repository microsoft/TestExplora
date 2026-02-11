from utils.prompts import prompt_dict, wo_dep_prompt_dict
import re

def remove_docstrings(code_str):
    """
    Remove docstrings by directly matching quotes.
    Matches all possible string formats: single quotes, double quotes, triple quotes.
    """
    # Define all possible string patterns
    patterns = [r'""".*?"""', r"'''.*?'''"]
    
    result = code_str
    
    # Apply patterns in order, prioritizing triple quotes
    for pattern in patterns:
        # Use DOTALL flag to let . match newline characters
        result = re.sub(pattern, '', result, flags=re.DOTALL)
    
    return result

def get_prompts(code_info, invoke_deps_data, 
                invoke_deps, invoke_full_codes, 
                test_function_name, documentation,
                omit_dep_code=False, test_type="graybox", omit_dep=False, repo_name="", hints={}, use_hint=True):
    """
    Prepare the prompts for the model based on the provided code information and dependencies.

    :param code_info: Dictionary containing code information.
    :param invoke_deps_data: Dictionary containing dependencies data.
    :param invoke_deps: List of dependencies for the invokes.
    :param invoke_full_codes: Dictionary containing full code content for the invokes.
    :param test_function_name: Name of the test function to be generated.
    :param documentation: Documentation string to infer intended behavior.
    :param omit_dep_code: Boolean indicating whether to omit dependencies in the prompt.
    :return: Formatted prompt string.
    """
    deps_data = ""
    for dep, dep_info in invoke_deps_data.items():
        if not omit_dep_code:
            dep_code = dep_info["full_code"]
        else:
            dep_code = dep_info["omit_code"]
        deps_data += f"File Path: {dep_info['file']}\n{dep_code}\n\n"
    
    code_data = ""
    for invoke, invoke_code in invoke_full_codes.items():
        file_path = invoke.split(":")[0]
        if test_type != "whitebox":
            invoke_code = remove_docstrings(invoke_code)
        code_data += f"File Path: {file_path}\n{invoke_code}\n"
    
    tested_function_name = "\n".join(invoke_deps.keys())
    test_invokes = ", ".join(invoke_deps.keys())
    invoke_deps_str = ""
    import_lines_dict = {}
    for invoke, deps in invoke_deps.items():
        invoke_deps_str += f"Code to test: {invoke}\n  - Dependencies: {', '.join(deps) if len(deps)>0 else 'No dependencies'}\n"
        import_prefix = invoke.split(":")[0].replace("/", ".").replace(".py", "")
        code_type = code_info.get(invoke, {}).get("type", "")
        if code_type == "method":
            import_suffix = code_info[invoke]["class"].split(":")[-1]
        else:
            import_suffix = invoke.split(":")[-1]
        import_line = f"from {import_prefix} import {import_suffix}"
        if import_line not in import_lines_dict:
            import_lines_dict[import_line] = []
        if code_type == "method":
            import_lines_dict[import_line].append(invoke.split(':')[-1])
    import_lines = ""
    for k, v in import_lines_dict.items():
        if len(v) > 1:
            import_lines += f"{k}" + f" # You should test the methods: {', '.join(v)} of this class\n"
        else:
            import_lines += f"{k}\n"

    doc_str = ""
    for name, doc in documentation.items():
        doc_str += f"Function/Method: {name}\n- Documentation:\n{doc}\n\n"
    
    prompt_input = {
        "code_data": code_data.strip(),
        "tested_function_name": tested_function_name,
        "invoke_deps_str": invoke_deps_str.strip(),
        "test_invokes": test_invokes,
        "test_function_name": test_function_name,
        "import_lines": import_lines.strip(),
        "deps_data": deps_data.strip(),
        "documentation": doc_str.strip(),
    }
    if test_type not in prompt_dict:
        raise ValueError(f"Unsupported test type: {test_type}")
    prompt_template = prompt_dict[test_type] if not omit_dep else wo_dep_prompt_dict[test_type]
    prompt = prompt_template.format_map(prompt_input)
    return prompt
    
def get_prompts_agent(code_info, invoke_deps_data, invoke_deps, invoke_full_codes, test_function_name, 
                      documentation, omit_dep_code=False, test_type="graybox", omit_dep=False, 
                      repo_name="", hints={}, use_hint=True, fobbidden_commands=False, refine_explo=False):
    code_data = ""
    for invoke, invoke_code in invoke_full_codes.items():
        file_path = invoke.split(":")[0]
        code_name = invoke.split(":")[-1]
        code_data += f"File Path: {file_path} -Code Name: {code_name}\n"

    tested_function_name = "\n".join(invoke_deps.keys())

    hint_code_str = ""
    for code_n, code_c in hints["code"].items():
        hint_file_path = code_n.split(":")[0]
        code_name = code_n.split(":")[-1]
        hint_code_str += f"File Path: {hint_file_path} -Code Name: {code_name}\n"

    invoke_deps_str = ""
    for invoke, deps in invoke_deps.items():
        invoke_deps_str += f"Code to test: {invoke}\n  - Dependencies: {', '.join(deps) if len(deps)>0 else 'No dependencies'}\n"
    
    hint_code_str += "The following is the code patch that fix the bug:\n" + hints["patch"] + "\n"

    doc_str = ""
    for name, doc in documentation.items():
        doc_str += f"Function/Method: {name}\n- Documentation:\n{doc}\n\n"

    test_invokes = ", ".join(invoke_deps.keys())

    import_lines_dict = {}
    for invoke, deps in invoke_deps.items():
        import_prefix = invoke.split(":")[0].replace("/", ".").replace(".py", "")
        code_type = code_info.get(invoke, {}).get("type", "")
        if code_type == "method":
            import_suffix = code_info[invoke]["class"].split(":")[-1]
        else:
            import_suffix = invoke.split(":")[-1]
        import_line = f"from {import_prefix} import {import_suffix}"
        if import_line not in import_lines_dict:
            import_lines_dict[import_line] = []
        if code_type == "method":
            import_lines_dict[import_line].append(invoke.split(':')[-1])

    import_lines = ""
    for k, v in import_lines_dict.items():
        if len(v) > 1:
            import_lines += f"{k}" + f" # You should test the methods: {', '.join(v)} of this class\n"
        else:
            import_lines += f"{k}\n"

    prompt_input = {
        "code_data": code_data.strip(),
        "test_invokes": test_invokes,
        "import_lines": import_lines.strip(),
        "documentation": doc_str.strip(),
        "repo_name": repo_name.split("/")[-1],
        "hint_code_str": hint_code_str
    }

    if not use_hint:
        prompt_template = wo_dep_prompt_dict["agent"]
        if refine_explo:
            prompt_template = wo_dep_prompt_dict["agent_refine_explo"]
    else:
        prompt_template = wo_dep_prompt_dict["hint"]

    prompt = prompt_template.format_map(prompt_input).strip() + "\n"
    if fobbidden_commands:
        forbidden_cmds = '''## Forbidden Commands
The following commands are forbidden in this environment:
"vim", "vi", "emacs", "nano", "nohup", "gdb", "less", "tail -f", "python -m venv", "make", "python", "python3", "pip", "pip3", "pytest"'''
        prompt = prompt + forbidden_cmds + "\n"
    
    if refine_explo:
        prompt = prompt + "\nPS: A good starting point is to explore along the invocation paths of the test entry points and examine each invoked function or class for potential issues.\n" + \
                    "Hint: the code directly invoked by the test entry points are: \n" + invoke_deps_str.strip() + "\n" + \
                        "The exploration should start from the test entry points and their direct invocations and continues until all nodes along the invocation path are verified to conform to the intention specified in the documentation of the test entry points or not."
        prompt += """\n\n### Important Note ###
Create a file named `generated_tests.py` in the proper location WITHIN the repo directory to contain all the generated unit tests.
This is important because the tests patch will be created in the repo for further processing."""
    return prompt

    

    

    