from utils.prompts import prompt_dict_hint
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
                omit_dep_code=False, test_type="graybox", hint_code=None):
    """
    Prepare the prompts for the model based on the provided code information and dependencies.

    :param code_info: Dictionary containing code information.
    :param invoke_deps_data: Dictionary containing dependencies data.
    :param invoke_deps: List of dependencies for the invokes.
    :param invoke_full_codes: Dictionary containing full code content for the invokes.
    :param test_function_name: Name of the test function to be generated.
    :param documentation: Documentation string to infer intended behavior.
    :param omit_dep_code: Boolean indicating whether to omit dependencies in the prompt.
    :param test_type: Type of tests to generate: "whitebox", "graybox", or "blackbox".
    :param omit_dep: Boolean indicating whether to omit dependencies in the prompt.
    :return: Formatted prompt string.
    """
    deps_data = ""
    for dep, dep_info in invoke_deps_data.items():
        if not omit_dep_code:
            dep_code = dep_info["full_code"]
        else:
            dep_code = dep_info["omit_code"]
        deps_data += f"File Path: {dep_info['file']}\n{dep_code}\n\n"

    hint = ""
    if hint_code:
        for code_n, code in hint_code.items():
            hint += f"File Path: {code_n.split(':')[0]}\n{code}\n\n"
    
    code_data = ""
    for invoke, invoke_code in invoke_full_codes.items():
        file_path = invoke.split(":")[0]
        if test_type == "whitebox":
            invoke_code = remove_docstrings(invoke_code)
        code_data += f"File Path: {file_path}\n{invoke_code}\n"
    
    tested_function_name = "\n".join(invoke_deps.keys())
    test_invokes = ", ".join(invoke_deps.keys())
    invoke_deps_str = ""
    import_lines_dict = {}
    for invoke, temp_deps in invoke_deps.items():
        deps = [dept for dept in temp_deps if dept in invoke_deps_data]
        if deps:
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
        "invoke_deps_str": invoke_deps_str.strip() if invoke_deps_str else "No dependencies provided.",
        "test_invokes": test_invokes,
        "test_function_name": test_function_name,
        "import_lines": import_lines.strip(),
        "deps_data": deps_data.strip() if deps_data else "No dependencies provided.",
        "documentation": doc_str.strip(),
        "hint_code": hint.strip() if hint else "No hint code provided."
    }
    if test_type not in prompt_dict_hint:
        raise ValueError(f"Unsupported test type: {test_type}")
    prompt_template = prompt_dict_hint[test_type]
    prompt = prompt_template.format_map(prompt_input)
    return prompt
    

    