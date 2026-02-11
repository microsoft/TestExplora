import re
from typing import List

# Regular expression to match code blocks
CODE_BLOCK_RE = re.compile(
    r"```(?P<lang>\w+)?\s*\n(?P<code>.*?)```",
    re.DOTALL | re.MULTILINE
)


def extract_code(text: str) -> List[str]:
    """
    Extract triple-backticked code blocks from text.
    
    Args:
        text: Input text containing code blocks
        
    Returns:
        List[str]: List of extracted code strings
    """
    blocks = []
    for match in CODE_BLOCK_RE.finditer(text):
        code = match.group("code").strip("\n\r")
        if code:
            blocks.append(code)
    return blocks