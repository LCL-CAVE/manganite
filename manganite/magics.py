from dataclasses import dataclass, field
from typing import Callable
from warnings import warn

import panel as pn
import param
from IPython.core.magic import Magics, magics_class, cell_magic, needs_local_scope
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring


@dataclass
class RerunnableCell():
    deps: list = field(default_factory=list)
    pane: pn.viewable.Viewable = None
    rerun: Callable = None


@magics_class
class ManganiteMagics(Magics):
    _cells = {}

    @magic_arguments()
    @argument('name',
              type=str,
              help='Unique name to bind to')
    # @argument('--type', '-t',
    #           type=str, choices=['fig', 'df'], default='fig',
    #           help='Widget type')
    @argument('--depends-on', '-d',
              type=str, nargs='+',
              help='List of variables which should trigger a cell rerun on change')
    @argument('--stage', '-s',
              type=str, choices=['inputs', 'results'],
              help='Tab to place the widget on')
    @argument('--position', '-p',
              type=int, nargs=2,
              help='Grid coordinates to place the widget at')
    @needs_local_scope
    @cell_magic
    def autoupdate(self, arg_line, cell_source, local_ns):
        from manganite import get_layout

        args = parse_argstring(ManganiteMagics.autoupdate, arg_line)

        if not args.name.isidentifier():
            raise NameError('Name {} is not a valid identifier'.format(args.name))
        if args.name in local_ns:
            warn('Widget {} already defined, overwriting'.format(args.name))
            # TODO: if local_ns['_autoupdate_{}'.format(args.name)]: unwatch

        for dep in args.depends_on:
            if dep not in local_ns:
                raise NameError('Dependency {} is not in the global scope'.format(dep))
            if not issubclass(local_ns[dep].__class__, param.Parameterized):
                raise TypeError('Dependency {} is not a watchable value'.format(dep))

        cell = ManganiteMagics._cells.setdefault(args.name, RerunnableCell(deps=args.depends_on))

        exec(cell_source, local_ns, local_ns)
        if args.name in local_ns:
            cell.pane = pn.panel(local_ns[args.name])
            if args.stage and args.position:
                y, x = args.position
                get_layout()[args.stage][y, x] = cell.pane

        def rerun(*events):
            exec(cell_source, local_ns, local_ns)
            if args.name in local_ns:
                if cell.pane is None:
                    cell.pane = pn.panel(local_ns[args.name])
                    if args.stage and args.position:
                        y, x = args.position
                        get_layout()[args.stage][y, x] = cell.pane
                else:
                    cell.pane.object = local_ns.get(args.name)

        local_ns['_autoupdate_{}'.format(args.name)] = cell

        for dep in args.depends_on:
            local_ns[dep].param.watch(rerun, ['value'])
