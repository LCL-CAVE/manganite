import sys
from io import BytesIO

import panel as pn
import pandas as pd


__version__ = '0.0.1'

CSS_FIX = """
.grid-stack-item-content > * { margin: 0 !important; }
"""

_layout = {}
_optimizer_button = None
_optimizer_terminal = None
_optimizer_result = None
optimizer_done = None


def init(*args, **kwargs):
    global _layout, _optimizer_button, _optimizer_terminal, optimizer_done

    pn.extension(
        'gridstack', 'tabulator', 'plotly', *args,
        template='material', theme='dark',
        raw_css=[CSS_FIX], **kwargs)

    _optimizer_terminal = pn.widgets.Terminal(sizing_mode='stretch_both', write_to_console=True)
    _optimizer_button = pn.widgets.Button(name='Start optimization')
    optimizer_done = pn.widgets.BooleanStatus(value=False)

    _layout['inputs'] = tab_inputs = pn.layout.gridstack.GridStack(
        sizing_mode='stretch_both', ncols=6, mode='override')
    _layout['optimize'] = tab_optimize = pn.layout.gridstack.GridStack(sizing_mode='stretch_width',
        ncols=2)
    tab_optimize[0, 0] = pn.Column('## Parameters', _optimizer_button)
    tab_optimize[0, 1] = pn.Column('## Log', _optimizer_terminal)
    _layout['results'] = tab_results = pn.layout.gridstack.GridStack(
        sizing_mode='stretch_width', ncols=6, mode='override')

    main_layout = pn.Tabs(
        ('Inputs', tab_inputs),
        ('Optimizer', tab_optimize),
        ('Results', tab_results)
    ).servable()
    return tab_inputs, tab_optimize, tab_results, optimizer_done


def get_layout():
    return _layout


def create_upload_handler(transform=None):
    def callback(target, event):
        if event.new is not None:
            df = pd.read_csv(BytesIO(event.new))
            if transform is not None:
                df = transform(df)
            target.value = df
    return callback


def on_optimize(cb):
    def wrapped_cb(*events):
        global _optimizer_result
        sys.stdout = _optimizer_terminal
        sys.stderr = _optimizer_terminal
        _optimizer_terminal.clear()
        optimizer_done.value = False
        try:
            _optimizer_result = cb()
            optimizer_done.value = True
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
    _optimizer_button.on_click(wrapped_cb)


def get_result():
    return _optimizer_result


def load_ipython_extension(ipython):
    from .magics import ManganiteMagics
    ipython.register_magics(ManganiteMagics)


def _jupyter_server_extension_points():
    return [{
        'module': 'manganite.jupyter'
    }]
