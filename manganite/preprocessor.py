import logging
import re
from textwrap import dedent
from uuid import uuid4

import nbconvert.exporters
import nbconvert.preprocessors
from IPython.core.inputtransformer2 import TransformerManager


class TransformManganiteMagicsPreprocessor(nbconvert.preprocessors.Preprocessor):
    _magic_pattern = re.compile(r'^\s*%%mnn\s+(.*)')
    _title_pattern = re.compile(r'^#\s*(.+)')
    _transformer = TransformerManager()


    def __call__(self, nb, resources):
        return self.preprocess(nb, resources)


    def preprocess(self, nb, resources):
        if not self.has_import(nb):
            return nb, resources

        description = '\n\n'.join([cell['source'] for cell in nb.cells if self.is_description_cell(cell)])
        title = self._title_pattern.match(description)

        nb.cells.insert(0, {
            'id': str(uuid4()),
            'cell_type': 'code',
            'outputs': [],
            'execution_count': 1,
            'metadata': {'tags': ['mnn-ignore']},
            'source': dedent("""\
                import manganite as _mnn_import
                from manganite.cell_manager import CellManager
                _mnn_import.init(title={0!r}, description={1!r})
                _mnn_cell_mgr = CellManager(globals())""".format(title.group(1) if title else None, description))
        })

        return super().preprocess(nb, resources)


    def preprocess_cell(self, cell, resources, index):
        if '%load_ext manganite' in cell['source']:
            cell['source'] = cell['source'].replace('%load_ext manganite', '')

        if 'mnn-ignore' in cell['metadata'].get('tags', []):
            return cell, resources

        if cell['cell_type'] == 'code':
            cell['source'] = self.transform_cell(cell['source'].lstrip())

        return cell, resources


    def has_import(self, nb):
        import_pattern = re.compile(r'import\s+manganite')
        cell_has_import = lambda cell: cell['cell_type'] == 'code' and import_pattern.match(cell['source'])

        return next((True for cell in nb.cells if cell_has_import(cell)), False)


    def is_description_cell(self, cell):
        if 'mnn-ignore' in cell['metadata'].get('tags', []):
            return False

        return cell['cell_type'] == 'markdown'
    

    def transform_cell(self, cell):
        lines = cell.splitlines()
        if len(lines):
            match = self._magic_pattern.match(lines[0])
            if match is None:
                cell = self.strip_system_calls(cell)
                return '_mnn_cell_mgr.add_cell({0!r})'.format(cell)
            else:
                cell = self.strip_system_calls('\n'.join(lines[1:]))
                return '_mnn_cell_mgr.add_magic_cell({0!r}, {1!r})'.format(match.group(1), cell)

        return cell


    # IPython's `!system` calls need to be stripped explicitly at this step
    # because this preprocessor converts cells into strings
    # so any parser later will ignore their contents
    def strip_system_calls(self, cell):
        cell = self._transformer.transform_cell(cell)
        # Bokeh's NotebookHandler follows the same pattern
        # with `magic` and `run_line_magic`
        cell = cell.replace('get_ipython().system', '')
        cell = cell.replace('get_ipython().getoutput', '')

        return cell


def _patch_python_exporter():
    log = logging.getLogger(__name__)
    log.warning('Patching nbconvert PythonExporter before Bokeh creates a NotebookHandler')

    cls = nbconvert.exporters.PythonExporter
    old_init = cls.__init__

    def new_init(self, config=None, **kw):
        old_init(self=self, config=config, **kw)
        self.register_preprocessor(TransformManganiteMagicsPreprocessor())

    cls.__init__ = new_init
