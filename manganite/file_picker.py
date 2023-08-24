import os

import panel as pn
import param
from panel.viewable import Viewer
from pathvalidate import sanitize_filename

from manganite import Manganite


class FilePicker(Viewer):
    value = param.FileSelector(label='Selected file')

    def __init__(self, accept=None, **params):
        self._create_subdir(params.get('name', ''))
        self._input = pn.widgets.FileInput(accept=accept)
        # call parent constructor only after initializing widgets
        # for `@param.depends` to work properly
        super().__init__(**params)
        self.param.value.path = os.path.join(self._path, '*')

        self._layout = pn.Column(self._input, self.param.value)


    def __panel__(self):
        return self._layout
    

    # this directory is deleted with its parent
    # on destruction of the current Manganite instance
    def _create_subdir(self, name):
        upload_dir = Manganite.get_instance().get_upload_dir()
        self._path = os.path.join(upload_dir, name)
        os.mkdir(self._path)


    # param==1.13.0 does not update `objects` properly on `path` change
    # so we need to trigger `update()` manually
    @param.depends('value:path', watch=True)
    def _update_selector_objects(self):
        self.param.value.update()


    @param.depends('_input.value', watch=True)
    def _save_upload(self):
        if self._input.value is not None:
            filename = sanitize_filename(self._input.filename)
            filepath = os.path.join(self._path, filename)
            self._input.save(filepath)

            # trigger value change on the first upload
            # or a re-upload of the currently selected file
            self.param.value.update()
            if len(self.param.value.objects) == 1 or self.value == filepath:
                self.value = filepath
