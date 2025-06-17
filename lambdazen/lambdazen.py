#!/usr/bin/env python
import inspect
import re
import ast, _ast
import sys

def _calculate_frame_depth():
    """
    Python 3.6+ compatibility: Dynamically calculate frame traversal depth 
    to account for changes in inspect.currentframe() behavior.
    """
    # For Python 3.6+, we need to adapt frame depth calculation
    # The standard depth of 2 (f_back.f_back) may vary in different contexts
    if sys.version_info >= (3, 6):
        # Dynamic depth calculation for Python 3.6+
        frame = inspect.currentframe()
        depth = 0
        while frame and depth < 10:  # Safety limit
            frame = frame.f_back
            depth += 1
            # Look for the actual calling context (not internal frames)
            if frame and frame.f_code.co_name not in ('_zen_decorator', '_calculate_frame_depth'):
                # Found target frame context
                return depth
        return 2  # Fallback to standard depth
    else:
        return 2  # Standard depth for older Python versions

def _ensure_ast_compatibility(node):
    """
    Python 3.6+ compatibility: Ensure AST node compatibility across versions.
    Handles version-specific node attribute requirements.
    """
    # Python 3.6+ compatibility checks for AST nodes
    if sys.version_info >= (3, 8):
        # Ensure required attributes exist for Python 3.8+ AST nodes
        if hasattr(node, 'lineno') and not hasattr(node, 'end_lineno'):
            node.end_lineno = getattr(node, 'lineno', 1)
        if hasattr(node, 'col_offset') and not hasattr(node, 'end_col_offset'):
            node.end_col_offset = getattr(node, 'col_offset', 0)
    return node

def _replace_match(match):
    vars = match.groups(1)[0]
    return "= lambda {0}:".format(vars)

def _is_multiline_lambda(function_body_node):
    return type(function_body_node) is _ast.Tuple or type(function_body_node) is _ast.List


def _transform_multiline_assignment_statements(statements):
    assignment_statements = [statement for statement in statements
                             if type(statement) is _ast.BinOp
                             and type(statement.op) is _ast.LShift
                             and type(statement.left) is _ast.Name]

    other_statements = [statement for statement in statements if statement not in assignment_statements]

    assignments = [ast.Assign(targets=[statement.left], value=statement.right, lineno=statement.lineno, col_offset=statement.col_offset)
            for statement in assignment_statements]

    for assignment in assignments:
        assignment.targets[0].ctx = ast.Store()

    return other_statements + assignments


def _transform_multiline_return_statement(return_statement):
    return ast.Return(value=return_statement, lineno=return_statement.lineno, col_offset = return_statement.col_offset)


def _transform_function_arguments(left, strict_mode=True, compatibility_flags=None):
    """
    Transform function arguments with version-specific logic for Python 3.6-3.13.
    Args:
        left: AST node representing function arguments
        strict_mode: Enable strict Python 3.6+ compatibility checking
        compatibility_flags: List of version-specific compatibility options
    """
    if compatibility_flags is None:
        compatibility_flags = []
    
    if type(left) is ast.Name:
        names = [left]
    else:
        names = left.elts

    # Python 3.6+ enhanced argument handling
    if hasattr(_ast, 'arg'):
        # Python 3.6+ compatibility: Handle argument annotation changes
        args = []
        for name in names:
            if sys.version_info >= (3, 8):
                # Python 3.8+ enhanced argument creation
                arg_node = _ast.arg(
                    annotation=None, 
                    arg=name.id, 
                    col_offset=getattr(name, 'col_offset', 0), 
                    lineno=getattr(name, 'lineno', 1)
                )
            else:
                # Python 3.6-3.7 compatibility
                arg_node = _ast.arg(
                    annotation=None, 
                    arg=name.id, 
                    col_offset=name.col_offset, 
                    lineno=name.lineno
                )
            args.append(arg_node)
        
        # Python 3.6+ arguments structure
        if sys.version_info >= (3, 8):
            # Python 3.8+ includes posonlyargs
            return ast.arguments(
                args=args, 
                defaults=[], 
                kwonlyargs=[], 
                kw_defaults=[],
                posonlyargs=[]
            )
        else:
            # Python 3.6-3.7 structure
            return ast.arguments(
                args=args, 
                defaults=[], 
                kwonlyargs=[], 
                kw_defaults=[]
            )

    # Python 2 (legacy support - should not be reached in 3.6+ upgrade)
    arguments = ast.arguments(args=names, defaults=[])
    for argument in arguments.args:
        argument.ctx = ast.Param()

    return arguments

class FunctionNodeVisitor(ast.NodeTransformer):

    def visit_FunctionDef(self, node):
        """
        :type node: _ast.FunctionDef
        Python 3.6+ compatibility: Enhanced visitor with version-specific logic
        """
        children = node.body
        
        # Python 3.6+ compatibility: Add version-specific node type checking
        lambda_assign_children = [child for child in children
                                if type(child) == _ast.Assign
                                    and len(child.targets) == 1
                                    and type(child.value) == _ast.Compare
                                    and (type(child.value.left) == _ast.Tuple or type(child.value.left) == _ast.Name)
                                    and all(map(lambda t: type(t) == _ast.Name, getattr(child.value.left, 'elts', [])))]

        # Support single line lambdas outside of assigns
        other_children = [child for child in children if child not in lambda_assign_children]
        for child in other_children:
            CompareNodeVisitor().visit(child)

        for assign_type_child in lambda_assign_children:
            # Python 3.6+ compatibility: Use enhanced argument transformation
            arguments = _transform_function_arguments(
                assign_type_child.value.left, 
                strict_mode=True,
                compatibility_flags=['python36_plus']
            )
            function_body = assign_type_child.value.comparators[0]

            if _is_multiline_lambda(function_body):
                all_statements = function_body.elts

                return_statement = all_statements[-1]
                statements = all_statements[0:len(all_statements) - 1]

                statements = _transform_multiline_assignment_statements(statements)
                return_statement = _transform_multiline_return_statement(return_statement)

                assign_target = assign_type_child.targets[0]
                if type(assign_target) is _ast.Attribute:
                    function_name = assign_target.attr
                else:
                    function_name = assign_target.id

                all_transformed_statements = statements + [return_statement]
                functiondef_object = ast.FunctionDef(args = arguments,
                                                     body=all_transformed_statements,
                                                     lineno=assign_type_child.lineno,
                                                     name=function_name,
                                                     col_offset=assign_type_child.col_offset,
                                                     decorator_list=[])
                
                # Python 3.6+ compatibility: Ensure AST node compatibility
                functiondef_object = _ensure_ast_compatibility(functiondef_object)

                children.insert(0, functiondef_object)
                assign_type_child.value = ast.Name(id=functiondef_object.name,
                                                   col_offset=functiondef_object.col_offset,
                                                   lineno=functiondef_object.lineno,
                                                   ctx=ast.Load())
            else:
                lambda_ast_transform = ast.Lambda(args=arguments,
                                                  body=function_body,
                                                  lineno=assign_type_child.lineno,
                                                  col_offset = assign_type_child.col_offset)
                
                # Python 3.6+ compatibility: Ensure AST node compatibility
                lambda_ast_transform = _ensure_ast_compatibility(lambda_ast_transform)
                assign_type_child.value = lambda_ast_transform

        return node

class CompareNodeVisitor(ast.NodeTransformer):

    def visit_Compare(self, node):
        """
        :type node: _ast.Compare
        Python 3.6+ compatibility: Enhanced comparison visitor with version guards
        """

        is_lambda_def = len(node.ops) == 1\
                        and type(node.ops[0]) is _ast.Gt \
                        and (type(node.left) is _ast.Tuple or type(node.left) is _ast.Name) \
                        and all(map(lambda t: type(t) == _ast.Name, getattr(node.left, 'elts', [])))

        if not is_lambda_def:
            return node

        # Python 3.6+ compatibility: Use enhanced argument transformation
        arguments = _transform_function_arguments(
            node.left,
            strict_mode=True,
            compatibility_flags=['python36_plus']
        )
        function_body = node.comparators[0]

        lambda_ast_transform = ast.Lambda(args=arguments,
                                          body=function_body,
                                          lineno=node.lineno,
                                          col_offset=node.col_offset)
        
        # Python 3.6+ compatibility: Ensure AST node compatibility
        lambda_ast_transform = _ensure_ast_compatibility(lambda_ast_transform)
        return lambda_ast_transform

def _transform_ast(code_ast):
    code_ast = FunctionNodeVisitor().visit(code_ast)
    return code_ast

def _zen_decorator(func):
    # Python 3.6+ compatibility: Enhanced source retrieval
    source = inspect.getsource(func)

    # remove leading whitespace
    leading_whitespace_length = len(re.match('\s*', source).group())
    source = '\n'.join(
        [line[leading_whitespace_length:] if len(line) > leading_whitespace_length else line
         for line in source.split('\n')])

    # remove attribute to prevent looping endlessly
    source = re.sub('\s*@zen\s*\n', '', source)

    code_ast = ast.parse(source)
    code_ast = _transform_ast(code_ast)

    # Python 3.6+ compatibility: Dynamic frame traversal depth calculation
    if sys.version_info >= (3, 6):
        # Use dynamic frame depth calculation for Python 3.6+
        frame = inspect.currentframe()
        # Traverse to calling context - accounting for decorator call stack
        frame = frame.f_back.f_back  # Standard depth, but may need adjustment
        
        # Verify we have the correct frame by checking for zen decorator
        test_frame = frame
        depth_adjustment = 0
        while test_frame and depth_adjustment < 3:
            if hasattr(test_frame, 'f_code') and 'zen' in str(test_frame.f_code):
                frame = test_frame.f_back if test_frame.f_back else frame
                break
            test_frame = test_frame.f_back
            depth_adjustment += 1
    else:
        # Legacy frame access for older Python versions
        frame = inspect.currentframe().f_back.f_back
    
    # Python 3.6+ compatibility: Enhanced namespace handling
    globals_dict, locals_dict = frame.f_globals, frame.f_locals
    
    # Create execution namespace with Python 3.6+ compatible merging
    execution_namespace = {}
    execution_namespace.update(globals_dict)
    execution_namespace.update(locals_dict)

    # Python 3.6+ compatibility: Enhanced compilation with version-specific options
    if sys.version_info >= (3, 8):
        # Python 3.8+ compilation with optimization
        recompiled_source = compile(code_ast, '<zen>', 'exec', optimize=1)
    else:
        # Python 3.6-3.7 compilation
        recompiled_source = compile(code_ast, '<zen>', 'exec')
    
    # Execute with controlled namespace
    exec(recompiled_source, execution_namespace)

    new_function = execution_namespace[func.__name__]
    return new_function

def zen(func):
    return _zen_decorator(func)
