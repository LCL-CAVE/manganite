import ast
import re
import sys
from collections import namedtuple
from datetime import date, datetime
from shlex import split

import ast_scope
import panel as pn
import param
from pandas import DataFrame
from IPython.core.magic_arguments import MagicArgumentParser

from manganite import Manganite


class BoolWrapper(param.Parameterized):
    value = param.Boolean()


class NumberWrapper(param.Parameterized):
    value = param.Number()


class StringWrapper(param.Parameterized):
    value = param.String()


class DatetimeWrapper(param.Parameterized):
    value = param.Date()


class DataFrameWrapper(param.Parameterized):
    value = param.DataFrame()


WrappableTypes = {
    bool: BoolWrapper,
    int: NumberWrapper,
    float: NumberWrapper,
    str: StringWrapper,
    date: DatetimeWrapper,
    datetime: DatetimeWrapper,
    DataFrame: DataFrameWrapper}


def inspect_var(ns: dict, name: str):
    assert name.isidentifier()

    if name not in ns:
        return 'undefined'
    if isinstance(ns[name], param.Parameterized):
        return 'wrapped'
    if isinstance(ns[name], tuple(WrappableTypes.keys())):
        return 'wrappable'
    return 'non_wrappable'


class CellTransformer(ast.NodeTransformer):
    def __init__(self, scope_info, ns):
        self.scope_info = scope_info
        self.ns = ns
        self.stores = set()
        self.loads = set()
        self.undef_stores = set()
        self.undef_loads = set()


    def visit_Name(self, node):
        if not isinstance(self.scope_info[node], ast_scope.scope.GlobalScope):
            return node
        
        var_state = inspect_var(self.ns, node.id)

        # collect potentially deferred references
        if var_state == 'undefined':
            if isinstance(node.ctx, ast.Store):
                self.undef_stores.add(node.id)
            else:
                self.undef_loads.add(node.id)

        if isinstance(node.ctx, ast.Store):
            self.stores.add(node.id)
        else:
            self.loads.add(node.id)
        
        if var_state != 'wrapped':
            return node

        return ast.Attribute(
            value=ast.Name(id=node.id, ctx=ast.Load()),
            attr='value',
            ctx=node.ctx)


CellTransformInfo = namedtuple('CellTransformInfo', ['source', 'stores', 'loads', 'new', 'undefined'])


class CellManager():
    def __init__(self, ns):
        self.ns = ns
        self.deferred = {}
        self.panels = {}
        self.process_callbacks = {}


    def transform(self, source) -> CellTransformInfo:
        source_tree = ast.parse(source)
        scope_info = ast_scope.annotate(source_tree)

        transformer = CellTransformer(scope_info, self.ns)
        transformed_tree = transformer.visit(source_tree)
        ast.fix_missing_locations(transformed_tree)
        return CellTransformInfo(
            ast.unparse(transformed_tree),
            transformer.stores,
            transformer.loads,
            transformer.undef_stores,
            transformer.undef_loads - transformer.undef_stores)


    def wrap(self, name: str, widget_attrs=None):
        if widget_attrs is None:
            for t, Wrapper in WrappableTypes.items():
                if isinstance(self.ns[name], t):
                    self.ns[name] = Wrapper(name=name, value=self.ns[name])
                    break
        else:
            var_type = type(self.ns[name])
            widget_type = widget_attrs['type']
            params = widget_attrs['params']
            if var_type == int:
                if widget_type == 'slider' and type(params) == str:
                    constraints = list(map(lambda x: int(x), params.split(':')))
                    if 2 <= len(constraints) <= 3 and constraints[0] < constraints[1]:
                        start, end = constraints[:2]
                        step = constraints[2] if len(constraints) == 3 else 1
                        self.ns[name] = pn.widgets.IntSlider(
                            name=name,
                            value=self.ns[name],
                            start=start,
                            end=end,
                            step=step)
                else:
                    self.ns[name] = pn.widgets.IntInput(name=name, value=self.ns[name])
            elif var_type == float:
                if widget_type == 'slider' and type(params) == str:
                    constraints = list(map(lambda x: float(x), params.split(':')))
                    if 2 <= len(constraints) <= 3 and constraints[0] < constraints[1]:
                        start, end = constraints[:2]
                        step = constraints[2] if len(constraints) == 3 else min(0.1, (end - start) / 10)
                        self.ns[name] = pn.widgets.FloatSlider(
                            name=name,
                            value=self.ns[name],
                            start=start,
                            end=end,
                            step=step)
                else:
                    self.ns[name] = pn.widgets.FloatInput(name=name, value=self.ns[name])
            elif var_type == str:
                if widget_type == 'select' and type(params) == str:
                    if params in self.ns and isinstance(self.ns[params], (list, set, tuple)):
                        options = list(self.ns[params])
                        value = self.ns[name] if self.ns[name] in options else options[0]
                        self.ns[name] = pn.widgets.Select(name=name, options=options, value=value)
                elif widget_type == 'radio' and type(params) == str:
                    if params in self.ns and isinstance(self.ns[params], (list, set, tuple)):
                        options = list(self.ns[params])
                        value = self.ns[name] if self.ns[name] in options else options[0]
                        self.ns[name] = pn.widgets.RadioBoxGroup(name=name, options=options, value=value)
                elif widget_type == 'text':
                    self.ns[name] = pn.widgets.TextInput(name=name,value=self.ns[name])
            elif var_type == bool:
                label = params if type(params) == str else name
                if widget_type == 'switch':
                    self.ns[name] = pn.widgets.Switch(
                        name=label, value=self.ns[name],
                        stylesheets=[':host { width: 40px; }'])
                else:
                    self.ns[name] = pn.widgets.Checkbox(name=label, value=self.ns[name])
            elif var_type == date:
                self.ns[name] = pn.widgets.DatePicker(name=name, value=self.ns[name])
            elif var_type == datetime:
                self.ns[name] = pn.widgets.DatetimePicker(name=name, value=self.ns[name])
            elif var_type == DataFrame:
                self.ns[name] = pn.widgets.Tabulator(self.ns[name])


    def add_cell(self, raw_source, process_var=None, widget_attrs=None):
        _, stores, loads, new, undefined = self.transform(raw_source)

        defer = process_var is not None
        first_run = True
        def run_cell(*events):
            nonlocal first_run

            source = self.transform(raw_source).source
            exec(source, self.ns, self.ns)
            for name in stores:
                var_state = inspect_var(self.ns, name)

                if var_state == 'wrappable':
                    if widget_attrs and widget_attrs['name'] == name:
                        self.wrap(name, widget_attrs)
                    else:
                        self.wrap(name)
                
                if var_state != 'undefined':
                    if name in self.deferred and len(self.deferred[name]):
                        for cb in self.deferred[name]:
                            cb()
                        self.deferred.pop(name)

            if widget_attrs and widget_attrs['name'] in self.ns:
                name = widget_attrs['name']
                widget_attrs['display'](self.ns[name])

            if first_run:
                first_run = False
                if not process_var:
                    for name in loads - stores:
                        var_state = inspect_var(self.ns, name)
                        if var_state == 'wrapped':
                            self.ns[name].param.watch(run_cell, ['value'])

        deferred_deps = undefined & self.deferred.keys()
        process_deps = loads & self.process_callbacks.keys()

        if len(deferred_deps):
            defer = True
            for name in deferred_deps:
                self.deferred[name].add(run_cell)

        if len(process_deps):
            defer = True
            for name in process_deps:
                self.process_callbacks[name].add(run_cell)

        if defer:
            if process_var:
                self.process_callbacks[process_var] = set()
            for name in new:
                self.deferred[name] = set()
        else:
            run_cell()
        
        return run_cell
    

    def add_process_cell(self, args, raw_source):
        run_cell = self.add_cell(raw_source, process_var=args.returns)
        label = args.on[1]

        mnn = Manganite.get_instance()
        def run_process(*events):
            sys.stdout = mnn._optimizer_terminal
            sys.stderr = mnn._optimizer_terminal
            mnn._optimizer_terminal.write(
                '\033[32;1m[{}]\nExecuting "{}"...\033[0m\n\n\n'.format(
                    datetime.now().isoformat(sep=' ', timespec='seconds'),
                    label))
            try:
                run_cell()
                for cb in self.process_callbacks[args.returns]:
                    cb()
            finally:
                sys.stdout.flush()
                sys.stderr.flush()
                mnn._optimizer_terminal.write('\n\n')
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
        
        button = pn.widgets.Button(
            name=label,
            stylesheets=[':host { width: fit-content; }'])
        button.on_click(run_process)
        if args.tab is not None:
            button.styles['grid_column_end'] = 'span 1'
            Manganite.get_instance().get_tab(args.tab).append(button)
        else:
            Manganite.get_instance().get_header().append(button)


    def add_widget_cell(self, args, raw_source):
        def display_widget(widget):
            if args.var in self.panels:
                self.panels[args.var].object = widget
            else:
                self.panels[args.var] = pn.panel(widget)
                tab_grid = Manganite.get_instance().get_tab(args.tab)
                grid_cell = pn.Column(
                    pn.pane.Markdown('### {}'.format(args.header or args.var)),
                    self.panels[args.var])

                y, x, w = args.position
                if y >= 0:
                    grid_cell.styles['grid_row_start'] = str(y + 1)
                if x >= 0 and x < 6:
                    grid_cell.styles['grid_column_start'] = str(x + 1)
                grid_cell.styles['grid_column_end'] = 'span {}'.format(w if 0 < w <= 6 else 3)

                tab_grid.append(grid_cell)

        widget = {
            'name': args.var,
            'type': args.type[0],
            'params': args.type[1] if len(args.type) > 1 else None,
            'display': display_widget}
        self.add_cell(raw_source, widget_attrs=widget)


    def add_magic_cell(self, arg_line, raw_source):
        parser = MagicArgumentParser()
        subparsers = parser.add_subparsers(dest='magic_type')

        process_parser = subparsers.add_parser('execute')
        process_parser.add_argument('--on', type=str, nargs=2)
        process_parser.add_argument('--tab', type=str, required=False)
        process_parser.add_argument('--returns', type=str)

        widget_parser = subparsers.add_parser('widget')
        widget_parser.add_argument('--var', type=str)
        widget_parser.add_argument('--tab', type=str)
        widget_parser.add_argument('--type', type=str, nargs='+')
        widget_parser.add_argument('--header', type=str)
        widget_parser.add_argument('--position', type=int, nargs=3,
            required=False, default=(-1, -1, 3))

        argv = split(arg_line)

        # check for slider range arguments, like `-50:50:5` or `0.0:1.0:0.01`
        # and prepend a space so that negative values are not parsed as --args
        range_spec = re.compile(':'.join(3 * [r'[+-]?(\d*\.)?\d+']))
        argv = [' ' + arg if range_spec.match(arg) else arg for arg in argv]

        args = parser.parse_args(argv)
        if args.magic_type == 'execute':
            self.add_process_cell(args, raw_source)
        elif args.magic_type == 'widget':
            self.add_widget_cell(args, raw_source)
            