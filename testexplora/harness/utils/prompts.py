GENERATE_INPUT_PROMPT = """
You are an expert software engineer. Your task is to generate a set of unit tests for the given codes to find potential problems.
You are provided with the following information:
    - The dependencies of the codes to be tested.
    - The inference of the codes to be tested.
    - The name of function to be tested.

You are required to generate unit tests that leverage all the codes in the ### The codes to be tested ### section to find potential problems.

### The dependencies of the codes to be tested ###
This section provides the dependencies of the codes to be tested. Each dependency is represented by its file path, followed by its code content.
{deps_data}

### The inference of the codes to be tested.. ###
This section provides the inference of the codes to be tested. Each code is represented by its file path, followed by its code content.
{code_data}

### The name of function to be tested ###
You should generated a test case to test the following function:
{tested_function_name}

### Requirements for the generated unit tests ###
- Here are the simplified dependencies of the codes to be tested, you can refer to them when generating unit tests:
{invoke_deps_str}
- You must leverage the following code in ### The name of function to be tested ### section as entry points to find potential problems:
{test_invokes}

### Output Format ###
- You must output the generated unit tests in the following format, wrapped in a single code block with triple backticks:
```python
{import_lines}
<generated unit tests>
```
"""

GENERATE_INPUT_PROMPT_V2 = """
You are an experienced software test engineer applying a Test-Driven Development (TDD) approach. 
Your task is to design tests that ensure only correct implementations (following the documentation) pass, while incorrect implementations would fail.

You are given the following information:
- Dependencies
- Test entry points
- Documentation

Your tasks:
1. Infer the **intended behavior** of the Test entry points' API from the documentation.
2. Design a set of **test cases** that cover:
   - Basic functionality with valid inputs and expected outputs.
   - Boundary conditions and edge cases.
   - Invalid inputs and error handling.
   - Potential issues with dependency interactions.
3. Write executable test code using Pytest.
4. Ensure tests are designed to differentiate between correct and incorrect implementations:
   - At least one test should be able to expose an incorrect implementation if it does not fully follow the documented behavior.
   - A correct implementation should pass all tests.

## Dependencies
This section provides the dependencies of the test entry points. Each dependency is represented by its file path.
{deps_data}

## Test Entry Points
This section provides the functions or methods to be tested, each represented by its file path:
{code_data}

## Documentation
You should infer the intended behavior of the test entry points from the following documentation:
{documentation}

* Additional information:
- Here are the simplified dependencies of the codes to be tested, you can refer to them when generating unit tests:
{invoke_deps_str}

## Requirements for the generated unit tests
- You must leverage the following code in ## Test Entry Points ## section as entry points to find potential problems:
{test_invokes}

### Output Format ###
- You must output the generated unit tests in the following format, wrapped in a single code block with triple backticks:
```python
{import_lines}
<generated unit tests>
```
"""

GENERATE_INPUT_PROMPT_V2_WODEP = """
You are an experienced software test engineer applying a Test-Driven Development (TDD) approach. 
Your task is to design tests that ensure only correct implementations (following the documentation) pass, while incorrect implementations would fail.

You are given the following information:
- Test entry points
- Documentation

Your tasks:
1. Infer the **intended behavior** of the Test entry points' API from the documentation.
2. Design a set of **test cases** that cover:
   - Basic functionality with valid inputs and expected outputs.
   - Boundary conditions and edge cases.
   - Invalid inputs and error handling.
3. Write executable test code using Pytest.
4. Ensure tests are designed to differentiate between correct and incorrect implementations:
   - At least one test should be able to expose an incorrect implementation if it does not fully follow the documented behavior.
   - A correct implementation should pass all tests.

## Test Entry Points
This section provides the functions or methods to be tested, each represented by its file path:
{code_data}

## Documentation
You should infer the intended behavior of the test entry points from the following documentation:
{documentation}

## Requirements for the generated unit tests
- You must leverage the following code in ## Test Entry Points ## section as entry points to find potential problems:
{test_invokes}

### Output Format ###
- You must output the generated unit tests in the following format, wrapped in a single code block with triple backticks:
```python
{import_lines}
<generated unit tests>
```
"""

GENERATE_INPUT_PROMPT_V2_WODEP_AGENT = """
You are an experienced software test engineer applying a Test-Driven Development (TDD) approach. 
Your task is to design tests that ensure only correct implementations (following the documentation) pass, while incorrect implementations would fail.

You are given the following information:
- Test entry points
- Documentation

Follow these steps to generate the unit tests:
1. Infer the **intended behavior** of the Test entry points' API from the documentation.
2. Explore the repo and check whether there are any potential problems in the code related to the Test Entry Points:
   - You should check whether there are any potential problems in the Test Entry Points.
   - You should also check whether there are any potential problems in the dependencies of the Test Entry Points, that can be detected by leveraging the test of the Test Entry Points.
3. Design a set of **test cases** that cover:
   - Basic functionality with valid inputs and expected outputs.
   - Boundary conditions and edge cases.
   - Invalid inputs and error handling.
4. Write executable test code using Pytest.
5. Ensure tests are designed to differentiate between correct and incorrect implementations:
   - At least one test should be able to expose an incorrect implementation if it does not fully follow the documented behavior.
   - A correct implementation should pass all tests.
6. Make sure all generated tests are compilable and executable.

## Test Entry Points
This section provides the functions or methods to be tested, each represented by its file path:
{code_data}

## Documentation
You should infer the intended behavior of the test entry points from the following documentation:
{documentation}

## Requirements for the generated unit tests
- You must leverage the following code in ## Test Entry Points ## section as entry points to find potential problems:
{test_invokes}

### Important Note ###
Create a file named `generated_tests.py` in the proper location WITHIN the repo directory to contain all the generated unit tests.
This is important because the tests patch will be created in the repo for further processing.
""".strip()

GENERATE_INPUT_PROMPT_V2_WODEP_AGENT_REFINE_EXPLO = """
You are an experienced software test engineer applying a Test-Driven Development (TDD) approach. 
Your task is to design tests that ensure only correct implementations (following the documentation) pass, while incorrect implementations would fail.

You are given the following information:
- Test entry points
- Documentation

## Test Entry Points
This section provides the functions or methods to be tested, each represented by its file path:
{code_data}

## Documentation
You should infer the intended behavior of the test entry points from the following documentation:
{documentation}

## Requirements for the generated unit tests
- You must leverage the following code in ## Test Entry Points ## section as entry points to find potential problems:
{test_invokes}

Can you help me implement the necessary changes to the repository so that the requirements specified in the test requirements are met?
Follow these steps to resolve the issue:
1. As a first step, it might be a good idea to find and read code relevant to the test requirements.
2. Exploration in the repo to identify potential issues:
    2.1 First identify the corresponding code related to the ### Test Entry Points.
    2.1 Leverage the python in bash tool to execute the corresponding code and identify whether the behavior is as expected.
3. Write tests that ensure only correct implementations (following the documentation) pass, while incorrect implementations would fail.
4. Make sure all generated tests are compilable and executable (if there is no pytest tool in the environment, you need to install it first).
   4.1 IMPORTANT: This does not mean your generated tests must pass in the current repo state.
   4.2 Keep in mind that some of the existing code may be incorrect according to the documentation, so your tests should be able to fail in such cases.

""".strip()

### Important Note ###
#Create a file named `generated_tests.py` in the proper location WITHIN the REPO (`{repo_name}`) located directory to contain all the generated unit tests.
#This is important because the tests patch will be created in the repo for further processing.

GENERATE_INPUT_PROMPT_V2_WODEP_AGENT_HINT = """
You are an experienced software test engineer applying a Test-Driven Development (TDD) approach. 
Your task is to design tests that ensure only correct implementations (following the documentation) pass, while incorrect implementations would fail.

You are given the following information:
- Test entry points
- Documentation

Follow these steps to generate the unit tests:
1. Infer the **intended behavior** of the Test entry points' API from the documentation.
2. Explore the repo and check whether there are any potential problems in the code related to the Test Entry Points:
   - You should check whether there are any potential problems in the Test Entry Points.
   - You should also check whether there are any potential problems in the dependencies of the Test Entry Points, that can be detected by leveraging the test of the Test Entry Points.
3. Design a set of **test cases** that cover:
   - Basic functionality with valid inputs and expected outputs.
   - Boundary conditions and edge cases.
   - Invalid inputs and error handling.
4. Write executable test code using Pytest.
5. Ensure tests are designed to differentiate between correct and incorrect implementations:
   - At least one test should be able to expose an incorrect implementation if it does not fully follow the documented behavior.
   - A correct implementation should pass all tests.
6. Make sure all generated tests are compilable and executable.

## Test Entry Points
This section provides the functions or methods to be tested, each represented by its file path:
{code_data}

## Documentation
You should infer the intended behavior of the test entry points from the following documentation:
{documentation}

## Requirements for the generated unit tests
- You must leverage the following code in ## Test Entry Points ## section as entry points to find potential problems:
{test_invokes}

### Hint ###
The following code is incorrect implementations against the documentation that may cause potential problems.
You should try to use the Test Entry Points to find problems in the following code and make sure the test will pass after these problem codes is fixed:
{hint_code_str}
So you should generate the corresponding test cases to let the code fail before applying the patch and pass after applying the patch.

### Important Note ###
Create a file named `generated_tests.py` in the proper location WITHIN the repo directory to contain all the generated unit tests.
This is important because the tests patch will be created in the repo for further processing.
""".strip()

GENERATE_INPUT_PROMPT_V2_HINT = """
You are an experienced software test engineer applying a Test-Driven Development (TDD) approach. 
Your task is to design tests that ensure only correct implementations (following the documentation) pass, while incorrect implementations would fail.

You are given the following information:
- Test entry points
- Documentation
- Hint code

Your tasks:
1. Infer the **intended behavior** of the Test entry points' API from the documentation.
2. Design a set of **test cases** that cover:
   - Basic functionality with valid inputs and expected outputs.
   - Boundary conditions and edge cases.
   - Invalid inputs and error handling.
3. Write executable test code using Pytest.
4. Ensure tests are designed to differentiate between correct and incorrect implementations:
   - At least one test should be able to expose an incorrect implementation if it does not fully follow the documented behavior.
   - A correct implementation should pass all tests.

## Test Entry Points
This section provides the functions or methods to be tested, each represented by its file path:
{code_data}

## Documentation
You should infer the intended behavior of the test entry points from the following documentation:
{documentation}

## Hint
This section provides where potential problems is located. You should try to use the Test Entry Points to find potential problems in the following code.
The error is originally from the following dependencies of the Test Entry Points. You can generate the corresponding test cases to find potential problems:
{hint_code}

## Requirements for the generated unit tests
- You must leverage the following code in ## Test Entry Points ## section as entry points to find potential problems in the ## Hint:
{test_invokes}

### Output Format ###
- You must output the generated unit tests in the following format, wrapped in a single code block with triple backticks:
```python
{import_lines}
<generated unit tests>
```
"""


GENERATE_INPUT_PROMPT_V2_BLACK = """
You are an experienced software test engineer applying a Test-Driven Development (TDD) approach. 
Your task is to design tests that ensure only correct implementations (following the documentation) pass, while incorrect implementations would fail.

You are given the following information:
- Test entry points
- Documentation

Your tasks:
1. Infer the **intended behavior** of the Test entry points' API from the documentation.
2. Design a set of **test cases** that cover:
   - Basic functionality with valid inputs and expected outputs.
   - Boundary conditions and edge cases.
   - Invalid inputs and error handling.
   - Potential issues with dependency interactions.
3. Write executable test code using Pytest.
4. Ensure tests are designed to differentiate between correct and incorrect implementations:
   - At least one test should be able to expose an incorrect implementation if it does not fully follow the documented behavior.
   - A correct implementation should pass all tests.

## Test Entry Points
This section provides the functions or methods to be tested, each represented by its file path:
{code_data}

## Documentation
You should infer the intended behavior of the test entry points from the following documentation:
{documentation}

## Requirements for the generated unit tests
- You must leverage the following code in ## Test Entry Points section as entry points to find potential problems:
{test_invokes}
   
### Output Format ###
- You must output the generated unit tests in the following format, wrapped in a single code block with triple backticks:
```python
{import_lines}
<generated unit tests>
```
"""

prompt_dict = {
    "debug": GENERATE_INPUT_PROMPT,
    "graybox": GENERATE_INPUT_PROMPT_V2,
    "whitebox": GENERATE_INPUT_PROMPT_V2,
    "blackbox": GENERATE_INPUT_PROMPT_V2_BLACK
}

wo_dep_prompt_dict = {
    "debug": GENERATE_INPUT_PROMPT,
    "graybox": GENERATE_INPUT_PROMPT_V2_WODEP,
    "whitebox": GENERATE_INPUT_PROMPT_V2_WODEP,
    "blackbox": GENERATE_INPUT_PROMPT_V2_WODEP,
    "agent": GENERATE_INPUT_PROMPT_V2_WODEP_AGENT, 
    "agent_refine_explo": GENERATE_INPUT_PROMPT_V2_WODEP_AGENT_REFINE_EXPLO,
    "hint": GENERATE_INPUT_PROMPT_V2_WODEP_AGENT_HINT
}

prompt_dict_hint = {
    "debug": GENERATE_INPUT_PROMPT,
    "graybox": GENERATE_INPUT_PROMPT_V2_HINT,
    "whitebox": GENERATE_INPUT_PROMPT_V2_HINT,
    "blackbox": GENERATE_INPUT_PROMPT_V2_HINT
}