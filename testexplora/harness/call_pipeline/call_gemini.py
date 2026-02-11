import os
import time
from openai import OpenAI

def call_gemini(prompt, system_prompt="", model="o3-mini", max_retries=5, **kwargs):
    """
    Call the specified GPT model for conversation generation.

    Args:
        prompt (str | list): User input prompt or message list.
        system_prompt (str, optional): System prompt. Defaults to empty string.
        model (str, optional): Model name to use. Defaults to "o3-mini".
        max_retries (int, optional): Maximum number of retries. Defaults to 5.
        **kwargs: Other optional parameters.

    Returns:
        list[str] | None: Returns a list of model-generated replies, or None on failure.
    """
    api_key=os.getenv("GOOGLE_API_KEY")
    client = OpenAI(api_key=api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    if not isinstance(prompt, list):
        prompt = [{"role": "user", "content": prompt}] if not system_prompt else \
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
    else:
        role_0 = prompt[0].get("role", "")
        if role_0 != "system":
            prompt = [{"role": "system", "content": system_prompt}] + prompt if system_prompt else prompt
    
    def _try_call():
        response = client.chat.completions.create(model=model, messages=prompt, **kwargs)
        return response.choices[0].message.content.strip()
    
    for attempt in range(max_retries):
        try:
            result = _try_call()
            return [result]
        except Exception as e:
            print(f"Error during extraction (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                print("Retrying in 60 seconds...")
                time.sleep(60)
            
if __name__ == "__main__":
    test_prompt = [
        {"role": "user", "content": "What model are you?"}
    ]
    response = call_gemini(test_prompt, model="gemini-2.5-pro")
    print(response)

        