import shutil
import tempfile
import weakref
from html import escape
from textwrap import dedent

import panel as pn

from .grid import Grid

__version__ = '0.0.5'

CSS_FIX = """
html { font-family: Roboto, sans-serif; }
#sidebar { background-color: #fafafa; }
#sidebar > .mdc-drawer__content > .mdc-list { box-sizing: border-box; height: 100%; }
#pn-Modal.mdc-dialog--open { background: rgba(0, 0, 0, 0.25); backdrop-filter: blur(2px); }
#pn-Modal .mdc-dialog__content { padding: 0; --mnn-debug-accordion-font: 0.75em monospace; }
#pn-Modal .mdc-dialog__surface { max-width: 75vw; }
:host(.card-title) h3 { font: var(--mnn-debug-accordion-font, inherit); }
"""

SIDEBAR_OUTER_WIDTH = 400
SIDEBAR_INNER_WIDTH = SIDEBAR_OUTER_WIDTH - 10 - 1

pn.extension(
    'terminal', 'gridstack', 'tabulator', 'plotly', 'mathjax', 'codeeditor',
    raw_css=[CSS_FIX], sizing_mode='stretch_width',
    notifications=True, design='material')


class Manganite:
    _nb_instance = None
    _server_instances = {}


    def __init__(self, *args, **kwargs):
        title = kwargs.pop('title', None) or 'Manganite App'
        description = kwargs.pop('description', None)

        if pn.state.curdoc: # shared environment
            Manganite._server_instances[pn.state.curdoc] = self
        else: # running in JupyterLab
            Manganite._nb_instance = self

        self._upload_dir = tempfile.mkdtemp(prefix='mnn_uploads__')
        self._finalizer = weakref.finalize(self, shutil.rmtree, self._upload_dir)

        self._init_terminal()
        self._init_debugger()

        self._layout = {'Description': pn.Column()}

        if description is not None:
            self._layout['Description'].append(pn.pane.Markdown(description))

        self._tabs = pn.Tabs(('Description', self._layout['Description']))
        
        self._header = pn.FlexBox(justify_content='end')
        self._header.append(self._debugger_button)

        self._sidebar = pn.FlexBox(
            flex_direction='column',
            flex_wrap='nowrap',
            width=SIDEBAR_INNER_WIDTH) # explicit width for proper initial terminal size
        self._sidebar.append('## Log')
        self._sidebar.append(self._optimizer_terminal)

        self._modal = pn.Column(
            '### Exceptions',
            pn.pane.Alert(
                dedent("""\
                    **Caution**: except for SyntaxErrors, cell previews show the code
                    **after it has been transformed by Manganite**, so it might
                    differ slightly from the original notebook."""),
                alert_type='warning',
                margin=(0, 10, 10, 10),
                stylesheets=['p { margin: 0; }']),
            self._exceptions,
            margin=(0, 0),
            stylesheets=[':host { width: 75vw; max-width: 150ch; }'])

        self._template = pn.template.MaterialTemplate(
            collapsed_sidebar=True,
            header=[self._header],
            header_background='#000228',
            sidebar=[self._sidebar],
            main=[self._tabs],
            sidebar_width=SIDEBAR_OUTER_WIDTH,
            modal=[self._modal],
            title=title
        ).servable()


    def _init_terminal(self):
        terminal_options = {'fontSize': 14}
        theme = pn.state.session_args.get('theme')
        if theme is None or theme[0] != 'dark':
            terminal_options['theme'] = {
                'background': '#fafafa',
                'foreground': '#000'
            }

        self._optimizer_terminal = pn.widgets.Terminal(
            write_to_console=True,
            options=terminal_options,
            stylesheets=['.terminal-container { width: 100% !important; } .xterm .xterm-viewport { width: auto !important; }'])
    

    def _init_debugger(self):
        self._exceptions = pn.Accordion(
            margin=(0, 0),
            stylesheets=['.accordion { margin: 0; }'])

        self._debugger_button = pn.widgets.Button(
            button_type='danger',
            name='Debug',
            icon='bug-off',
            visible=False,
            stylesheets=[':host { width: fit-content; order: 1; } .bk-TablerIcon { vertical-align: initial; }'])
        self._debugger_button.on_click(lambda e: self._template.open_modal())
    
    def get_tab(self, name):
        if name not in self._layout:
            self._layout[name] = Grid()
            self._tabs.append((name, self._layout[name]))
        
        return self._layout[name]
    

    def get_header(self):
        return self._header
    

    def get_upload_dir(self):
        return self._upload_dir


    def add_exception(self, cell_number, line_number, cell_source, error_class, error_message):
        if line_number is None:
            location = 'cell {}, magic command'.format(cell_number)
            line_number = 1
        else:
            location = 'cell {}, line {}'.format(cell_number, line_number)
        preview_title = '{} in {}: {}'.format(error_class, location, escape(error_message))
        notification_content = '{}<br><small>{}</small>'.format(error_class, location)

        preview = pn.widgets.CodeEditor(
            name=preview_title,
            value=cell_source,
            language='python' if error_class != 'UsageError' else 'sh',
            readonly=True,
            theme='github',
            sizing_mode='stretch_width',
            margin=(0, 0))

        # annotations seem to work only when set
        # after the widget has been added to the layout
        def annotate_line(e):
            preview.annotations = [{
                'row': line_number - 1,
                'column': 0,
                'text': error_message,
                'type': 'error'
            }]
        self._debugger_button.on_click(annotate_line)

        self._exceptions.append(preview)
        if len(self._exceptions) == 1:
            self._debugger_button.name = '1 exception'
            self._debugger_button.visible = True
            self._modal.insert(2,
                pn.pane.Alert(
                    dedent("""\
                        **Hint:** further exceptions below cell {}
                        might occur due to its incomplete execution.""".format(cell_number)),
                    margin=(0, 10, 10, 10),
                    stylesheets=['p { margin: 0; }']))
        else:
            self._debugger_button.name = '{} exceptions'.format(len(self._exceptions))

        if pn.state.loaded:
            pn.state.notifications.error(notification_content)
        else:
            pn.state.onload(lambda: pn.state.notifications.error(notification_content))


    @classmethod
    def get_instance(cls):
        if pn.state.curdoc:
            if pn.state.curdoc not in cls._server_instances:
                if cls._nb_instance and pn.state.curdoc is cls._nb_instance._template.server_doc():
                    cls._server_instances[pn.state.curdoc] = cls._nb_instance
            return cls._server_instances[pn.state.curdoc]
        return cls._nb_instance


def init(*args, **kwargs):
    mnn = Manganite(*args, **kwargs)
    return mnn


def load_ipython_extension(ipython):
    from .magics import ManganiteMagics
    init()
    ipython.register_magics(ManganiteMagics)


def _jupyter_server_extension_points():
    return [{
        'module': 'manganite.jupyter'
    }]
