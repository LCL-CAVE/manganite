import ast
import inspect
from shlex import split
from textwrap import indent
from warnings import warn

import ast_scope
import param
from pandas import DataFrame
from IPython.core.magic import Magics, magics_class, cell_magic, needs_local_scope
from IPython.core.magic_arguments import argument, magic_arguments


class NumberWrapper(param.Parameterized):
    value = param.Number()


class StringWrapper(param.Parameterized):
    value = param.String()


class DataFrameWrapper(param.Parameterized):
    value = param.DataFrame()


class GlobalWrapper(ast.NodeTransformer):
    def __init__(self, scope_info, tracked_names):
        self.scope_info = scope_info
        self.tracked_names = tracked_names
        self.stores = set()
        self.loads = set()


    def visit_Name(self, node):
        if not isinstance(self.scope_info[node], ast_scope.scope.GlobalScope):
            return node
        
        if node.id not in self.tracked_names:
            return node
        
        if isinstance(node.ctx, ast.Store):
            self.stores.add(node.id)
        else:
            self.loads.add(node.id)

        return ast.Attribute(
            value=ast.Name(id=node.id, ctx=ast.Load()),
            attr='value',
            ctx=node.ctx)


@magics_class
class ManganiteMagics2(Magics):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tracked_names = set()
        self.executed_cells = set()
        self.deferred = {}
        self.current_cell_id = None

    
    def pre_run(self, info):
        self.current_cell_id = info.cell_id


    def post_run(self, result):
        if 'manganite' not in result.info.raw_cell:
            assert self.current_cell_id == result.info.cell_id
        if '%%mnn' not in result.info.raw_cell:
            self.executed_cells.add(self.current_cell_id)
            # rerun_code = self.shell.transform_cell(result.info.raw_cell)
            # def rerun(*events):
            #     exec(rerun_code, self.shell.user_ns, self.shell.user_ns)
            # for dep in loads:
            #     self.shell.user_ns[dep].param.watch(rerun, ['value'])
        self.current_cell_id = None


    def _transform_cell(self, cell, additional_names=set()):
        source_tree = ast.parse(cell)
        scope_info = ast_scope.annotate(source_tree)

        transformer = GlobalWrapper(scope_info, self.tracked_names | self.deferred.keys() | additional_names)
        transformed_tree = transformer.visit(source_tree)
        ast.fix_missing_locations(transformed_tree)
        return (
            ast.unparse(transformed_tree),
            transformer.stores,
            transformer.loads)
    

    def transform_input(self, lines):
        cell, stores, loads = self._transform_cell(''.join(lines))
        if not 'get_ipython().run_cell_magic' in lines[0]:
            frame_info = inspect.stack()[2]
            if frame_info.function == '_run_cell':
                cell_id = frame_info.frame.f_locals['cell_id']
                print('[mnn] non-magic cell {}, uses values of {}'.format(cell_id, loads if len(loads) else 'no widgets'))
                def run_cell(*events):
                    if cell_id in self.executed_cells:
                        print('[mnn] rerunning \n{}      because {} changed'.format(
                            indent(''.join(lines), '        '),
                            [event.obj.name for event in events]))
                        exec(cell, self.shell.user_ns, self.shell.user_ns)
                    else:
                        print('[mnn] running cell {}'.format(cell_id))
                        exec(cell, self.shell.user_ns, self.shell.user_ns)

                deferred_deps = loads & self.deferred.keys()
                if len(deferred_deps):
                    for dep in deferred_deps:
                        self.deferred[dep].add(run_cell)

                        def create_cb():
                            print('[mnn] creating callback ({}) -> cell {}'.format(dep, cell_id))
                            self.shell.user_ns[dep].param.watch(run_cell, ['value'])
                        self.deferred[dep].add(create_cb)
                    print('[mnn] nothing to execute at this time')
                    return ['# nothing to execute at this time\n']
                else:
                    for dep in loads:
                        print('[mnn] creating callback ({}) -> this cell'.format(dep))
                        self.shell.user_ns[dep].param.watch(run_cell, ['value'])
                
        return cell.splitlines(keepends=True)


    def _wrap_variable(self, var, local_ns):
        if var.isidentifier() and var in local_ns:
            value = local_ns[var]
            if param._is_number(value):
                local_ns[var] = NumberWrapper(name=var, value=value)
            elif isinstance(value, str):
                local_ns[var] = StringWrapper(name=var, value=value)
            elif isinstance(value, DataFrame):
                local_ns[var] = DataFrameWrapper(name=var, value=value)
            self.tracked_names.add(var)
    

    def _magic_internals(self, new_tracked, cell_id, cell_source, local_ns, defer):
        if cell_id in self.executed_cells:
            warn('Cell {} is being rerun manually, redefining variables {}'.format(cell_id, new_tracked), stacklevel=0)
            # redefinition
            pass

        first_run_code, stores, loads = self._transform_cell(cell_source)
        rerun_code, _, _ = self._transform_cell(cell_source, additional_names=new_tracked)
        print('[mnn] magic cell {}, defines {}, uses values of {}'.format(cell_id, new_tracked, loads if len(loads) else 'no widgets'))

        def run_cell(*events):
            if cell_id in self.executed_cells:
                print('[mnn] rerunning magic cell {} because {} changed'.format(
                    cell_id,
                    [event.obj.name for event in events]))
                exec(rerun_code, local_ns, local_ns)
            else:
                print('[mnn] running magic cell {}'.format(cell_id))
                exec(first_run_code, local_ns, local_ns)
                self.executed_cells.add(cell_id)
                for var in new_tracked:
                    print('[mnn] wrapping new variable {}'.format(var))
                    self._wrap_variable(var, local_ns)
                    if var in self.deferred:
                        print('[mnn] deferred variable {} created, running downstream cells'.format(var))
                        for downstream in self.deferred[var]:
                            downstream()
                        self.deferred.pop(var)
                for dep in loads:
                    print('[mnn] creating callback ({}) -> this cell'.format(dep))
                    local_ns[dep].param.watch(run_cell, ['value'])

        deferred_deps = loads & self.deferred.keys()
        if len(deferred_deps):
            for dep in deferred_deps:
                self.deferred[dep].add(run_cell)
            defer = True
        
        if defer:
            for var in new_tracked:
                print('[mnn] adding deferred variable {}'.format(var))
                self.deferred[var] = set()
            print('[mnn] nothing to execute at this time')
        else:
            run_cell()

        return run_cell


    @magic_arguments()
    @argument('vars',
              type=str, nargs='+',
              help='List of variables to watch')
    @needs_local_scope
    @cell_magic
    def mnn_watch(self, arg_line, cell_source, local_ns):
        args = ManganiteMagics2.mnn_watch.parser.parse_args(split(arg_line))
        
        self._magic_internals(set(args.vars), self.current_cell_id, cell_source, local_ns, defer=False)


    @magic_arguments()
    @argument('var',
              type=str,
              help='Variable to watch')
    @argument('--trigger', '-t',
              type=str, nargs=2,
              help='Type and label for the trigger widget')
    @needs_local_scope
    @cell_magic
    def mnn_process(self, arg_line, cell_source, local_ns):
        args = ManganiteMagics2.mnn_process.parser.parse_args(split(arg_line))

        local_ns['_mnn_run_{}'.format(args.var)] = self._magic_internals({args.var}, self.current_cell_id, cell_source, local_ns, defer=True)
