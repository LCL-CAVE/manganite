def _load_jupyter_server_extension(app):
    import panel.io.jupyter_server_extension

    execution_template_lines = panel.io.jupyter_server_extension.EXECUTION_TEMPLATE.splitlines()
    i = next((i for i,line in enumerate(execution_template_lines) if 'PanelExecutor' in line), 0)
    execution_template_lines[i:i] = [
        'from manganite.preprocessor import _patch_python_exporter',
        '_patch_python_exporter()',
        ''
    ]

    panel.io.jupyter_server_extension.EXECUTION_TEMPLATE = '\n'.join(execution_template_lines)
