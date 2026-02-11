import os
import time
import signal
from openai import AzureOpenAI


class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("GPT call timed out")

signal.signal(signal.SIGALRM, timeout_handler)


def call_gpt(prompt, system_prompt="", model="o3-mini", max_retries=5, **kwargs):
    """
    Call a GPT model via Azure OpenAI.

    All credentials and endpoints are read from environment variables:
        AZURE_OPENAI_ENDPOINT    - Azure OpenAI endpoint URL
        AZURE_OPENAI_API_KEY     - API key for authentication
        AZURE_OPENAI_API_VERSION - API version (default: 2024-12-01-preview)

    Args:
        prompt (str | list): User prompt string or message list.
        system_prompt (str): Optional system prompt.
        model (str): Model / deployment name.
        max_retries (int): Maximum retry attempts.

    Returns:
        list[str] | None: Model response as a single-element list, or None on failure.
    """
    # Format prompt into message list
    if not isinstance(prompt, list):
        if system_prompt:
            prompt = [{"role": "system", "content": system_prompt},
                      {"role": "user", "content": prompt}]
        else:
            prompt = [{"role": "user", "content": prompt}]
    else:
        if system_prompt and (not prompt or prompt[0].get("role") != "system"):
            prompt = [{"role": "system", "content": system_prompt}] + prompt

    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    )

    def _try_call():
        signal.alarm(300)
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=prompt,
                stream=False,
            )
            return completion.choices[0].message.content
        finally:
            signal.alarm(0)

    for attempt in range(max_retries):
        try:
            result = _try_call()
            if result:
                return [result]
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {e}")
        if attempt < max_retries - 1:
            print("Retrying in 60 seconds...")
            time.sleep(60)

    return None


if __name__ == "__main__":
    response = call_gpt("Talk about yourself.", model="gpt-4o")
    print(response)
