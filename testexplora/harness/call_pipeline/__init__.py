try:
    from .call_gpt import call_gpt
    from .call_gemini import call_gemini
    from .call_vllm import call_vllm_base
    from .utils import extract_code
    from .call_sweagent import call_sweagent
    from .call_traeagent import call_traeagent
except ImportError:
    from call_gpt import call_gpt
    from call_gemini import call_gemini
    from call_vllm import call_vllm_base
    from utils import extract_code
    from call_sweagent import call_sweagent
    from call_traeagent import call_traeagent


import logging

def call_4o(prompt, system_prompt="", max_attempts=5, **kwargs):
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    final_response = ""
    while it < max_attempts:
        responses = call_gpt(all_design_traj, model="gpt-4o")
        if responses is None or len(responses) == 0:
            break
        response = responses[0]
        final_response = response
        all_design_traj.append({"role": "assistant", "content": response})
        code  = extract_code(response.strip())
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break

    return fn_data + [final_response]

def call_o4_mini(prompt, system_prompt="", max_attempts=5, **kwargs):
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    final_response = ""
    while it < max_attempts:
        responses = call_gpt(all_design_traj, model="o4-mini")
        if responses is None or len(responses) == 0:
            break
        response = responses[0]
        final_response = response
        all_design_traj.append({"role": "assistant", "content": response})
        code  = extract_code(response.strip())
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break

    return fn_data + [final_response]

def call_gpt5mini(prompt, system_prompt="", max_attempts=5, **kwargs):
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    final_response = ""
    while it < max_attempts:
        responses = call_gpt(all_design_traj, model="gpt-5-mini")
        if responses is None or len(responses) == 0:
            break
        response = responses[0]
        final_response = response
        all_design_traj.append({"role": "assistant", "content": response})
        code  = extract_code(response.strip())
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break

    return fn_data + [final_response]

def call_r1(prompt, system_prompt="", max_attempts=5, **kwargs):
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    final_response = ""
    while it < max_attempts:
        responses = call_gpt(all_design_traj, model="r1")
        if responses is None or len(responses) == 0:
            break
        response = responses[0]
        final_response = response
        # logging.info(f"R1 response: {response}")
        all_design_traj.append({"role": "assistant", "content": response})
        code  = extract_code(response.strip())
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break

    return fn_data + [final_response]

def call_code_llama_34b(prompt, system_prompt="", max_attempts=5, base_url="http://localhost:9500", **kwargs):
    """
    Call CodeLlama-34B model via vLLM API for test generation.
    
    Args:
        prompt: The issue description or prompt for test generation
        system_prompt: System prompt (optional)
        max_attempts: Maximum number of attempts
        base_url: Base URL of the vLLM API server
        **kwargs: Additional arguments to pass to the vLLM call
    Returns:
        List[str]: Generated test code
    """
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    final_response = ""
    while it < max_attempts:
        # Remove potentially conflicting parameters from kwargs
        vllm_kwargs = kwargs.copy()
        vllm_kwargs.pop('max_tokens', None)  # Remove potentially conflicting max_tokens

        responses = call_vllm_base(
            all_design_traj,
            model="Codellama-34B", 
            base_url=base_url,
            **vllm_kwargs
        )
        if responses is None or len(responses) == 0:
            it += 1
            break
            
        response = responses[0]
        final_response = response
        all_design_traj.append({"role": "assistant", "content": response})
        code = extract_code(response.strip())
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break
    return fn_data + [final_response]

def call_qwen_coder_30b(prompt, system_prompt="", max_attempts=5, base_url="http://localhost:9500", **kwargs):
    """
    Call Qwen3-Coder-30B model via vLLM API for test generation.
    
    Args:
        prompt: The issue description or prompt for test generation
        system_prompt: System prompt (optional)
        max_attempts: Maximum number of attempts
        base_url: Base URL of the vLLM API server
        **kwargs: Additional arguments to pass to the vLLM call
    Returns:
        List[str]: Generated test code
    """
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    final_response = ""
    while it < max_attempts:
        # Remove potentially conflicting parameters from kwargs
        vllm_kwargs = kwargs.copy()
        vllm_kwargs.pop('max_tokens', None)  # Remove potentially conflicting max_tokens

        responses = call_vllm_base(
            all_design_traj,
            model="Qwen3-Coder-30B", 
            base_url=base_url,
            **vllm_kwargs
        )
        if responses is None or len(responses) == 0:
            it += 1
            break
            
        response = responses[0]
        final_response = response
        all_design_traj.append({"role": "assistant", "content": response})
        code = extract_code(response.strip())
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break
    return fn_data + [final_response]

def call_o3_mini(prompt, system_prompt="", max_attempts=5, **kwargs):
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    final_response = ""
    while it < max_attempts:
        responses = call_gpt(all_design_traj, model="o3-mini")
        if responses is None or len(responses) == 0:
            break
        response = responses[0]
        final_response = response
        all_design_traj.append({"role": "assistant", "content": response})
        code  = extract_code(response.strip())
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break

    return fn_data + [final_response]

def call_gpt_5(prompt, system_prompt="", max_attempts=5, **kwargs):
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    final_response = ""
    while it < max_attempts:
        responses = call_gpt(all_design_traj, model="gpt-5")
        if responses is None or len(responses) == 0:
            break
        response = responses[0]
        final_response = response
        all_design_traj.append({"role": "assistant", "content": response})
        code  = extract_code(response.strip())
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break

    return fn_data + [final_response]

def call_gemini_2_5_pro(prompt, system_prompt="", max_attempts=5, **kwargs):
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    final_response = ""
    while it < max_attempts:
        responses = call_gemini(all_design_traj, model="gemini-2.5-pro")
        if responses is None or len(responses) == 0:
            break
        response = responses[0]
        final_response = response
        all_design_traj.append({"role": "assistant", "content": response})
        code  = extract_code(response.strip())
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break

    return fn_data + [final_response]

def call_claude_sonnet(prompt, system_prompt="", max_attempts=5, **kwargs):
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    final_response = ""
    while it < max_attempts:
        responses = call_gpt(all_design_traj, model="claude-4-5")
        if responses is None or len(responses) == 0:
            break
        response = responses[0]
        final_response = response
        all_design_traj.append({"role": "assistant", "content": response})
        code  = extract_code(response.strip())
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break

    return fn_data + [final_response]

def call_gemini_2_5_flash(prompt, system_prompt="", max_attempts=5, **kwargs):
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    final_response = ""
    while it < max_attempts:
        responses = call_gemini(all_design_traj, model="gemini-2.5-flash")
        if responses is None or len(responses) == 0:
            break
        response = responses[0]
        final_response = response
        all_design_traj.append({"role": "assistant", "content": response})
        code  = extract_code(response.strip())
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break

    return fn_data + [final_response]

def call_sweagent_o4mini(prompts, repo_path):
    """Run SWEAgent pipeline using Azure o4-mini model."""
    max_tries = 5
    for attempt in range(1, max_tries + 1):
        result = call_sweagent(prompts, repo_path, "o4-mini")
        if len(result) > 0:
            if len(result[0].strip()) > 0:
                return result
        import time
        logging.warning(f"SWEAgent o4-mini attempt {attempt} failed, retrying...")
        time.sleep(60)
    return []

def call_sweagent_gpt5mini(prompts, repo_path):
    """Run SWEAgent pipeline using Azure gpt-5-mini model."""
    max_tries = 5
    for attempt in range(1, max_tries + 1):
        result = call_sweagent(prompts, repo_path, "gpt-5-mini")
        if len(result) > 0:
            if len(result[0].strip()) > 0:
                return result
        import time
        logging.warning(f"SWEAgent gpt-5-mini attempt {attempt} failed, retrying...")
        time.sleep(60)
    return []

def call_sweagent_o4mini_wopython(prompts, repo_path):
    """Run SWEAgent pipeline using Azure o4-mini model without Python."""
    max_tries = 5
    for attempt in range(1, max_tries + 1):
        result = call_sweagent(prompts, repo_path, "o4-mini", use_python=False)
        if len(result) > 0:
            if len(result[0].strip()) > 0:
                return result
        import time
        logging.warning(f"SWEAgent o4-mini attempt {attempt} failed, retrying...")
        time.sleep(60)
    return []

def call_sweagent_gpt5mini_wopython(prompts, repo_path):
    """Run SWEAgent pipeline using Azure gpt-5-mini model without Python."""
    max_tries = 5
    for attempt in range(1, max_tries + 1):
        result = call_sweagent(prompts, repo_path, "gpt-5-mini", use_python=False)
        if len(result) > 0:
            if len(result[0].strip()) > 0:
                return result
        import time
        logging.warning(f"SWEAgent gpt-5-mini attempt {attempt} failed, retrying...")
        time.sleep(60)
    return []

def call_sweagent_gpt5mini_refineexplo(prompts, repo_path):
    """Run SWEAgent pipeline using Azure gpt-5-mini model without Python."""
    max_tries = 5
    for attempt in range(1, max_tries + 1):
        result = call_sweagent(prompts, repo_path, "gpt-5-mini", use_python=True, refine_exploration=True)
        if len(result) > 0:
            if len(result[0].strip()) > 0:
                return result
        import time
        logging.warning(f"SWEAgent gpt-5-mini attempt {attempt} failed, retrying...")
        time.sleep(60)
    return []

def call_sweagent_o4mini_refineexplo(prompts, repo_path):
    """Run SWEAgent pipeline using Azure o4-mini model without Python."""
    max_tries = 5
    for attempt in range(1, max_tries + 1):
        result = call_sweagent(prompts, repo_path, "o4-mini", use_python=True, refine_exploration=True)
        if len(result) > 0:
            if len(result[0].strip()) > 0:
                return result
        import time
        logging.warning(f"SWEAgent o4-mini attempt {attempt} failed, retrying...")
        time.sleep(60)
    return []

def call_sweagent_gpt5(prompts, repo_path):
    """Run SWEAgent pipeline using Azure gpt-5 model."""
    max_tries = 5
    for attempt in range(1, max_tries + 1):
        result = call_sweagent(prompts, repo_path, "gpt-5")
        if len(result) > 0:
            if len(result[0].strip()) > 0:
                return result
        import time
        logging.warning(f"SWEAgent gpt-5 attempt {attempt} failed, retrying...")
        time.sleep(60)
    return []

def call_traeagent_o4mini(prompts, repo_path):
    """Run TRAEAgent pipeline using Azure o4-mini model."""
    max_tries = 5
    for attempt in range(1, max_tries + 1):
        result = call_traeagent(prompts, repo_path, "o4-mini")
        if len(result) > 0:
            if len(result[0].strip()) > 0:
                return result
        import time
        logging.warning(f"TRAEAgent o4-mini attempt {attempt} failed, retrying...")
        time.sleep(60)
    return []

def call_traeagent_gpt5mini(prompts, repo_path):
    """Run TRAEAgent pipeline using Azure gpt-5-mini model."""
    max_tries = 5
    for attempt in range(1, max_tries + 1):
        result = call_traeagent(prompts, repo_path, "gpt-5-mini")
        if len(result) > 0:
            if len(result[0].strip()) > 0:
                return result
        import time
        logging.warning(f"TRAEAgent gpt-5-mini attempt {attempt} failed, retrying...")
        time.sleep(60)
    return []

def call_traeagent_gpt5(prompts, repo_path):
    """Run TRAEAgent pipeline using Azure gpt-5-mini model."""
    max_tries = 5
    for attempt in range(1, max_tries + 1):
        result = call_traeagent(prompts, repo_path, "gpt-5")
        if len(result) > 0:
            if len(result[0].strip()) > 0:
                return result
        import time
        logging.warning(f"TRAEAgent gpt-5 attempt {attempt} failed, retrying...")
        time.sleep(60)
    return []


call_map = {
    "gpt-4o": call_4o,
    "o3-mini": call_o3_mini,
    "gpt-5": call_gpt_5,
    "r1": call_r1,
    "gemini-2.5-pro": call_gemini_2_5_pro,
    "gemini-2.5-flash": call_gemini_2_5_flash,
    "Codellama-34B": call_code_llama_34b,
    "Qwen3-Coder-30B": call_qwen_coder_30b,
    "o4-mini": call_o4_mini,
    "gpt-5-mini": call_gpt5mini,
    "sweagent-o4mini": call_sweagent_o4mini,
    "sweagent-gpt5mini": call_sweagent_gpt5mini,
    "sweagent-gpt5": call_sweagent_gpt5,
    "traeagent-o4mini": call_traeagent_o4mini,
    "traeagent-gpt5mini": call_traeagent_gpt5mini,
    "traeagent-gpt5": call_traeagent_gpt5,
    "claude_sonnet": call_claude_sonnet,
    "sweagent-o4mini-wopython": call_sweagent_o4mini_wopython,
    "sweagent-gpt5mini-wopython": call_sweagent_gpt5mini_wopython,
    "sweagent-gpt5mini-refineexplo": call_sweagent_gpt5mini_refineexplo,
    "sweagent-o4mini-refineexplo": call_sweagent_o4mini_refineexplo,
}