import ast
import asttokens
import os

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
                all_lines[prefix + ":" + node.name] = {"line": (clazz["start_line"], clazz["end_line"]), "docstring": class_docstring, "docstring_end_line": clazz["docstring_end_line"], "file": prefix}
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        returns = [
                            ast.unparse(stmt.value) if stmt.value else None
                            for stmt in item.body if isinstance(stmt, ast.Return)
                        ]
                        docstring = ast.get_docstring(item)
                        docstring_end_line = get_docstring_end_line(item)
                        decorators = [ast.unparse(d) for d in item.decorator_list]
                        body_text = atok.get_text(item)[item.body[0].col_offset:] if item.body else ""

                        method = {
                            "name": item.name,
                            "start_line": item.decorator_list[0].lineno if item.decorator_list else item.lineno,
                            "end_line": item.end_lineno,
                            "docstring_end_line": docstring_end_line,
                            "parameters": [arg.arg for arg in item.args.args],
                            "returns": returns if returns else None,
                            "docstring": docstring if docstring is not None else "",
                            "decorators": decorators if decorators else None,
                            "body": body_text.strip()
                        }
                        all_lines[prefix + ":" + node.name + "." + item.name] = {"line": (method["start_line"], method["end_line"]), "docstring": method["docstring"], "docstring_end_line": method["docstring_end_line"], "file": prefix}

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

                    function = {
                        "name": node.name,
                        "start_line": node.decorator_list[0].lineno if node.decorator_list else node.lineno,
                        "end_line": node.end_lineno,
                        "docstring_end_line": docstring_end_line,
                        "parameters": [arg.arg for arg in node.args.args],
                        "returns": returns if returns else None,
                        "docstring": docstring if docstring is not None else "",
                        "decorators": decorators if decorators else None,
                        "body": body_text.strip()
                    }
                    all_lines[prefix + ":" + node.name] = {"line": (function["start_line"], function["end_line"]), "docstring": function["docstring"], "docstring_end_line": function["docstring_end_line"], "file": prefix}
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