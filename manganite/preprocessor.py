import logging
import re
from textwrap import dedent

import nbconvert.exporters
import nbconvert.preprocessors


class TransformManganiteMagicsPreprocessor(nbconvert.preprocessors.Preprocessor):
    _magic_pattern = re.compile(r'^\s*%%(mnn_(input|model|result))(\s+(.*))?')
    _title_pattern = re.compile(r'^#\s*(.+)')


    def is_description_cell(self, cell):
        if 'mnn-ignore' in cell['metadata'].get('tags', []):
            return False

        return cell['cell_type'] == 'markdown'


    def transform_magics(self, magic, line, cell):
        return '_mnn_magics.{0}({1!r}, {2!r}, globals())'.format(magic, line, cell)


    def preprocess(self, nb, resources):
        description = '\n\n'.join([cell['source'] for cell in nb.cells if self.is_description_cell(cell)])
        title = self._title_pattern.match(description)

        nb.cells.insert(0, {
            'cell_type': 'code',
            'outputs': [],
            'execution_count': 1,
            'metadata': {},
            'source': dedent("""\
                import manganite as _mnn_import
                from manganite.magics import ManganiteMagics
                _mnn_import.init(title={0!r}, description={1!r})
                _mnn_magics = ManganiteMagics()""".format(title.group(1) if title else None, description))
        })

        return super().preprocess(nb, resources)


    def preprocess_cell(self, cell, resources, index):
        if 'mnn-ignore' in cell['metadata'].get('tags', []):
            return cell, resources

        if cell['cell_type'] == 'code':
            lines = cell['source'].lstrip().splitlines()
            if len(lines):
                match = self._magic_pattern.match(lines[0])
                if match is not None:
                    cell['source'] = self.transform_magics(match.group(1), match.group(4), '\n'.join(lines[1:]))

        return cell, resources


    def __call__(self, nb, resources):
        return self.preprocess(nb, resources)


def _patch_python_exporter():
    log = logging.getLogger(__name__)
    log.warning('Patching nbconvert PythonExporter before Bokeh creates a NotebookHandler')

    cls = nbconvert.exporters.PythonExporter
    old_init = cls.__init__

    def new_init(self, config=None, **kw):
        old_init(self=self, config=config, **kw)
        self.register_preprocessor(TransformManganiteMagicsPreprocessor())

    cls.__init__ = new_init
