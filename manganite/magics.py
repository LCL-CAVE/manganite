from IPython.core.magic import Magics, magics_class, cell_magic, needs_local_scope


@magics_class
class ManganiteMagics(Magics):
    def __init__(self, *args, **kwargs):
        super(ManganiteMagics, self).__init__(*args, **kwargs)


    # dummy magic for running cells unmodified in Jupyter
    @needs_local_scope
    @cell_magic
    def mnn(self, arg_line, cell_source, local_ns):
        exec(cell_source, local_ns, local_ns)
