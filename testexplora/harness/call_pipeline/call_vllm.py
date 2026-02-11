import requests
import json
import time
import logging
from typing import List, Dict, Any, Optional

class VLLMClient:
    """
    VLLM client for calling model APIs deployed via VLLM.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 300):
        """
        Initialize VLLM client.

        Args:
            base_url: Base URL of the VLLM service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
    
    def call_model(self, messages: List[Dict[str, str]], model: str, **kwargs) -> Optional[str]:
        """
        Call a VLLM-deployed model.

        Args:
            messages: List of conversation messages, format: [{"role": "user", "content": "..."}]
            model: Model name
            **kwargs: Other generation parameters

        Returns:
            str: Model-generated reply, or None on failure
        """
        # Default generation parameters
        default_params = {
            # "max_tokens": 6000,  # Set to a large value, can be overridden via kwargs
            "temperature": 0.7,
            "top_p": 0.9,
            "stop": None,
        }
        default_params.update(kwargs)
        
        # Build request data
        data = {
            "model": model,
            "messages": messages,
            **default_params
        }
        
        try:
            # Send request to VLLM service's chat/completions endpoint
            response = self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=data,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract generated content
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                return content.strip()
            else:
                logging.error(f"VLLM API response format error: {result}")
                return None
                
        except requests.exceptions.Timeout:
            logging.error(f"VLLM API call timed out (exceeded {self.timeout} seconds)")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"VLLM API call failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"VLLM API response JSON parsing failed: {e}")
            return None
        except Exception as e:
            logging.error(f"Unknown error occurred during VLLM call: {e}")
            return None


def call_vllm_base(prompt, system_prompt="", model="Qwen/Qwen2.5-Coder-32B-Instruct", 
              base_url="http://localhost:8000", max_retries=10, **kwargs):
    """
    Generic VLLM model calling function.

    Args:
        prompt (str | list): User input prompt or message list
        system_prompt (str): System prompt
        model (str): Model name
        base_url (str): VLLM service address
        max_retries (int): Maximum number of retries
        **kwargs: Other generation parameters

    Returns:
        list[str] | None: Returns a list of model-generated replies, or None on failure
    """
    # Process message format
    if not isinstance(prompt, list):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
    else:
        messages = prompt
        # If no system message in the message list and system_prompt is provided, add it
        if system_prompt and (not messages or messages[0].get("role") != "system"):
            messages = [{"role": "system", "content": system_prompt}] + messages
    
    # Create VLLM client
    client = VLLMClient(base_url=base_url)
    
    # Retry logic
    for attempt in range(max_retries):
        try:
            logging.info(f"Calling VLLM model {model} (attempt {attempt + 1}/{max_retries})")
            
            result = client.call_model(messages, model, **kwargs)
            
            if result is not None and result.strip():
                logging.info(f"VLLM model {model} call succeeded")
                return [result]
            else:
                logging.warning(f"VLLM model {model} returned empty result")
                
        except Exception as e:
            logging.error(f"VLLM model {model} call failed (attempt {attempt + 1}): {e}")
            
        # If not the last attempt, wait before retrying
        if attempt < max_retries - 1:
            wait_time = 60  # Wait time before retry
            logging.info(f"Waiting {wait_time} seconds before retrying...")
            time.sleep(wait_time)
    
    logging.error(f"VLLM model {model} still failed after {max_retries} attempts")
    return None


def call_qwen_coder_30b(prompt, system_prompt="", max_attempts=5, base_url="http://localhost:8002", **kwargs):
    """
    Call Qwen/Qwen2.5-Coder-32B-Instruct model for code generation.

    Args:
        prompt (str): User prompt
        system_prompt (str): System prompt
        max_attempts (int): Maximum number of attempts
        base_url (str): VLLM service address
        **kwargs: Other parameters

    Returns:
        list[str]: List of generated code
    """
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."

    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []

    while it < max_attempts:
        # Remove potentially conflicting parameters from kwargs
        vllm_kwargs = kwargs.copy()
        vllm_kwargs.pop('max_tokens', None)  # Remove potentially conflicting max_tokens

        responses = call_vllm_base(
            all_design_traj,
            model="Qwen/Qwen2.5-Coder-32B-Instruct",
            base_url=base_url,
            temperature=0.7,
            max_tokens=8192,
            **vllm_kwargs
        )
        
        if responses is None or len(responses) == 0:
            it += 1
            continue
            
        response = responses[0]
        all_design_traj.append({"role": "assistant", "content": response})
        
        # Import utility function to extract code
        try:
            from .utils import extract_code
        except ImportError:
            from utils import extract_code
        code = extract_code(response.strip())

        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break

    return fn_data


def call_glm_4_9b(prompt, system_prompt="", max_attempts=5, base_url="http://localhost:8001", **kwargs):
    """
    Call zai-org/glm-4-9b-chat-hf model for code generation.

    Args:
        prompt (str): User prompt
        system_prompt (str): System prompt
        max_attempts (int): Maximum number of attempts
        base_url (str): VLLM service address
        **kwargs: Other parameters

    Returns:
        list[str]: List of generated code
    """
    if system_prompt == "":
        system_prompt = "You are a helpful assistant that helps people generate test case."
    
    all_design_traj = []
    all_design_traj.append({"role": "system", "content": system_prompt})
    all_design_traj.append({"role": "user", "content": prompt})

    it = 0
    fn_data = []
    
    while it < max_attempts:
        # Remove potentially conflicting parameters from kwargs
        vllm_kwargs = kwargs.copy()
        vllm_kwargs.pop('max_tokens', None)  # Remove potentially conflicting max_tokens

        responses = call_vllm_base(
            all_design_traj,
            model="zai-org/glm-4-9b-chat-hf",
            base_url=base_url,
            temperature=0.7,
            max_tokens=8192,
            **vllm_kwargs
        )
        
        if responses is None or len(responses) == 0:
            it += 1
            continue
            
        response = responses[0]
        all_design_traj.append({"role": "assistant", "content": response})
        
        # Import utility function to extract code
        try:
            from .utils import extract_code
        except ImportError:
            from utils import extract_code
        code = extract_code(response.strip())
        
        if len(code) == 0:
            feedback = "The generated response does not contain any code snippet. Please wrap your code snippets in triple backticks (```python ... ```) to ensure they are recognized."
            all_design_traj.append({"role": "user", "content": feedback})
            it += 1
            continue
        else:
            fn_data = ["\n".join(code)]
            break

    return fn_data

if __name__ == "__main__":
    prompt = "Write a function to add two numbers"
    system_prompt = "You are a helpful assistant that helps people generate test case."
    max_attempts = 5
    base_url = "http://localhost:9500"
    kwargs = {}
    # print(call_glm_4_9b(prompt, system_prompt, max_attempts, base_url, **kwargs))
    # print(call_qwen_coder_30b(prompt, system_prompt, max_attempts, base_url, **kwargs))
    print(call_vllm_base(prompt, system_prompt, model="Codellama-34B", base_url=base_url, **kwargs))
