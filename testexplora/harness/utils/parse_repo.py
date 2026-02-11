import ast
import asttokens
import os
import json
import re
import logging

def extract_classes_and_functions(filepath, repo_saved_path):
    file_text = ""
    with open(filepath, 'r', encoding='utf-8') as file:
        file_text = file.read()
    prefix = filepath.replace(repo_saved_path, "").strip("/")

    try:
        atok = asttokens.ASTTokens(file_text, parse=True)
        atok.mark_tokens(atok.tree)
    except SyntaxError as e:
        print(f"SyntaxError while parsing the file: {e}")
        return [], []

    # classes = []
    # functions = []
    all_lines = {}

    def get_docstring_end_line(node):
        if not node.body:
            return None

        if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
            end = getattr(node.body[0], "end_lineno", None)
            if end:
                return end
            for stmt in node.body[1:]:
                if hasattr(stmt, "lineno"):
                    return stmt.lineno - 1
            return node.end_lineno

        for stmt in node.body:
            if hasattr(stmt, "lineno"):
                return stmt.lineno - 1
        return node.end_lineno

    class ClassVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            try:
                class_docstring = ast.get_docstring(node)
                if class_docstring is None:
                    class_docstring = ""
                class_docstring_end = get_docstring_end_line(node)
                clazz = {
                    "name": node.name,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                    "docstring_end_line": class_docstring_end,
                    "bases": [ast.unparse(base) for base in node.bases],
                    "docstring": class_docstring if class_docstring is not None else "",
                    "methods": []
                }
                all_lines[prefix + ":" + node.name] = {"line": (clazz["start_line"], clazz["end_line"]), "docstring": class_docstring, "docstring_end_line": clazz["docstring_end_line"], "file": prefix, "class": "", "type": "class", "methods": [], "parameters": {}, "returns": {}}
                all_methods = []
                all_parameters = {}
                all_returns = {}    
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                        returns = [
                            ast.unparse(stmt.value) if stmt.value else None
                            for stmt in item.body if isinstance(stmt, ast.Return)
                        ]
                        docstring = ast.get_docstring(item)
                        docstring_end_line = get_docstring_end_line(item)
                        decorators = [ast.unparse(d) for d in item.decorator_list]
                        body_text = atok.get_text(item)[item.body[0].col_offset:] if item.body else ""
                        parmeters = {}
                        for arg in item.args.args:
                            annotation = ast.unparse(arg.annotation) if arg.annotation else None
                            parmeters[arg.arg] = annotation

                        method = {
                            "name": item.name,
                            "start_line": item.decorator_list[0].lineno if item.decorator_list else item.lineno,
                            "end_line": item.end_lineno,
                            "docstring_end_line": docstring_end_line,
                            "parameters": parmeters,
                            "returns": returns if returns else None,
                            "docstring": docstring if docstring is not None else "",
                            "decorators": decorators if decorators else None,
                            "body": body_text.strip()
                        }
                        all_lines[prefix + ":" + node.name + "." + item.name] = {"line": (method["start_line"], method["end_line"]), "docstring": method["docstring"], "docstring_end_line": method["docstring_end_line"], "file": prefix, "class": prefix + ":" + node.name, "type": "method", "methods": [], "parameters": method["parameters"], "returns": method["returns"]}
                        all_methods.append(prefix + ":" + node.name + "." + item.name)
                        all_parameters[prefix + ":" + node.name + "." + item.name] = method["parameters"]
                        all_returns[prefix + ":" + node.name + "." + item.name] = method["returns"]
                all_lines[prefix + ":" + node.name]["methods"] = all_methods
                all_lines[prefix + ":" + node.name]["parameters"] = all_parameters
                all_lines[prefix + ":" + node.name]["returns"] = all_returns

                #  classes.append(clazz)
            except Exception as e:
                print(f"Error while processing class {node.name}: {e}")
            finally:
                self.generic_visit(node)

    class FunctionVisitor(ast.NodeVisitor):
        def __init__(self):
            self.in_class = False
            self.in_function = False

        def visit_ClassDef(self, node):
            self.in_class = True
            self.generic_visit(node)
            self.in_class = False

        def visit_FunctionDef(self, node):
            if not self.in_class and not self.in_function:
                self.in_function = True
                try:
                    returns = [
                        ast.unparse(stmt.value) if stmt.value else None
                        for stmt in node.body if isinstance(stmt, ast.Return)
                    ]
                    decorators = [ast.unparse(d) for d in node.decorator_list]
                    docstring = ast.get_docstring(node)
                    docstring_end_line = get_docstring_end_line(node)
                    body_text = atok.get_text(node)[node.body[0].col_offset:] if node.body else ""
                    parmeters = {}
                    for arg in node.args.args:
                        annotation = ast.unparse(arg.annotation) if arg.annotation else None
                        parmeters[arg.arg] = annotation
                    function = {
                        "name": node.name,
                        "start_line": node.decorator_list[0].lineno if node.decorator_list else node.lineno,
                        "end_line": node.end_lineno,
                        "docstring_end_line": docstring_end_line,
                        "parameters": parmeters,
                        "returns": returns if returns else None,
                        "docstring": docstring if docstring is not None else "",
                        "decorators": decorators if decorators else None,
                        "body": body_text.strip()
                    }
                    all_lines[prefix + ":" + node.name] = {"line": (function["start_line"], function["end_line"]), "docstring": function["docstring"], "docstring_end_line": function["docstring_end_line"], "file": prefix, "class": "", "type": "function", "methods": [], "parameters": {prefix + ":" + node.name: function["parameters"]}, "returns": {prefix + ":" + node.name: function["returns"]}}
                except Exception as e:
                    print(f"Error while processing function {node.name}: {e}")
                finally:
                    self.generic_visit(node)
                self.in_function = False

    ClassVisitor().visit(atok.tree)
    FunctionVisitor().visit(atok.tree)

    return all_lines

def extract_classes_and_functions_from_repo(repo_saved_path):
    all_code_lines = {}
    for root, _, files in os.walk(repo_saved_path):
        for file in files:
            if (not file.endswith(".py")) or file.startswith("__init__"):
                continue
            filepath = os.path.join(root, file)
            try:
                file_lines = extract_classes_and_functions(filepath, repo_saved_path)
                all_code_lines.update(file_lines)
            except Exception as e:
                print(f"Error processing file {filepath}: {e}")
    return all_code_lines

def extract_import_lines(file_content: str):
    """
    Extracts import lines from the given file content: import, import as, from, and from ... import.
    Use ast to parse the file content and extract import statements.
    """
    imports = []
    try:
        tree = ast.parse(file_content)
    except SyntaxError as e:
        import_pattern = re.compile(r'^\s*(import|from)\s+.*$', re.MULTILINE)
        lines = file_content.split("\n")
        for line in lines:
            if import_pattern.match(line):
                imports.append(line.strip())
        return "\n".join(imports)

    # Traverse top-level AST nodes
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    imports.append(f"import {alias.name} as {alias.asname}")
                else:
                    imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module if node.module else "" # Case of 'from . import ...'
            names = []
            for alias in node.names:
                if alias.asname:
                    names.append(f"{alias.name} as {alias.asname}")
                else:
                    names.append(alias.name)
            if node.level > 0: # Handle relative imports, e.g. from .module import name
                module_prefix = "." * node.level
                module = module_prefix + module
            imports.append(f"from {module} import {', '.join(names)}")
    return "\n".join(imports)

class Repo_file_container:
    def __init__(self, repo_saved_path: str):
        self.repo_saved_path = repo_saved_path
        self.file_dic = {}
        self.code_lines = extract_classes_and_functions_from_repo(repo_saved_path)
        self.get_all_files()
    
    def get_all_files(self):
        """
        Returns a list of all Python files in the dataset directory.
        """
        for root, _, files in os.walk(self.repo_saved_path):
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    f.close()
                except Exception as e:
                    logging.info(f"Error reading {file_path}: {e}")
                    continue
                import_lines = extract_import_lines(content)
                prefix = file_path.replace(self.repo_saved_path, "").lstrip("/")
                self.file_dic[prefix] = {"lines": content.split("\n"), "imports": import_lines}

    def get_file_content(self, file_key: str):
        """
        Returns the content of a file given its key.
        """
        return self.file_dic[file_key]
    
    def get_code_lines(self, code_key: str):
        """
        Returns the code information (lines, docstring, type, etc.) for a given code key.
        """
        code_info = self.code_lines.get(code_key)
        if not code_info:
            logging.warning(f"Code key {code_key} not found in code lines.")
            return ""
        code_lines = code_info["line"]
        file_key = code_info["file"]
        file_content = self.get_file_content(file_key)
        if not file_content:
            logging.warning(f"File key {file_key} not found in file dictionary.")
            return ""
        lines = file_content["lines"]
        code_lines = lines[code_lines[0]-1:code_lines[1]]
        full_code = "\n".join(code_lines)

        code_str = "\n".join(code_lines)
        mask_pattern = "# -- Code omitted here --"
        if code_info["type"] != "class":
            impl_start = code_info['docstring_end_line']
            impl_end = code_info['line'][1]
            if impl_end > impl_start:
                impl_lines = file_content["lines"][impl_start: impl_end]
                impl_text = "\n".join(impl_lines)
                if impl_text:
                    num_spaces = len(impl_lines[0]) - len(impl_lines[0].lstrip())
                    tem_mask_str = " " * num_spaces + mask_pattern
                    code_str = code_str.replace(impl_text, tem_mask_str)
            
        else:
            for method in code_info['methods']:
                if method not in self.code_lines:
                    continue
                method_info = self.code_lines[method]
                impl_start = method_info['docstring_end_line']
                impl_end = method_info['line'][1]
                if impl_end > impl_start:
                    impl_lines = file_content["lines"][impl_start: impl_end]
                    impl_text = "\n".join(impl_lines)
                    if impl_text:
                        # Avoid replace empty string!!! Bug of OOM!!!
                        num_spaces = len(impl_lines[0]) - len(impl_lines[0].lstrip())
                        tem_mask_str = " " * num_spaces + mask_pattern
                        code_str = code_str.replace(impl_text, tem_mask_str) 

        return {"full_code": full_code, "omit_code": code_str, "file": file_key}