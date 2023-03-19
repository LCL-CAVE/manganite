import logging
import re
from textwrap import dedent

import nbconvert.exporters
import nbconvert.preprocessors


class TransformManganiteMagicsPreprocessor(nbconvert.preprocessors.Preprocessor):
    _magic_pattern = re.compile(r'^\s*%%autoupdate\s+(.*)')

    def transform_autoupdate(self, line, cell):
        return dedent("""\
            from manganite.magics import ManganiteMagics
            ManganiteMagics().autoupdate({0!r}, {1!r}, globals())""".format(line, cell))

    def preprocess_cell(self, cell, resources, index):
        if cell['cell_type'] == 'code':
            lines = cell['source'].lstrip().splitlines()
            if len(lines):
                match = self._magic_pattern.match(lines[0])
                if match is not None:
                    cell['source'] = self.transform_autoupdate(match.group(1), '\n'.join(lines[1:]))
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
