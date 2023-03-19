# Manganite

Manganite is a dashboarding tool built on the powerful [Panel](https://panel.holoviz.org/) framework. Its primary objective is to allow for an easy transition from a linear Jupyter notebook (load data → build an optimization model → run it → plot results) to an interactive web application, without requiring the user to manually convert most of their existing code to callbacks.

## Installation

Currently Manganite can be built from source and installed using `pip`:

```bash
python -m build && pip install dist/manganite-0.0.1-py3-none-any.whl
```

The above command should also take care of installing and enabling the necessary Jupyter Server extensions: one for Panel, to enable the preview pane, and one for Manganite, to preprocess the magic commands before passing the notebook to Panel preview. To ensure proper functioning, remember to **restart your Jupyter Server** after installing the package.

## Usage

To start using Manganite, import the package and load the IPython extension, enabling the `%%autoupdate` magic.

```python
import manganite as mnn
%load_ext manganite
```

### Step 1: Setting up the layout

Initialize the application layout. The `init()` function returns handles to individual tabs, as well as a reference to the optimizer status widget.

> :warning: **This part is likely to change soon:** Instead of a tuple this might be an object with corresponding attributes

```python
inputs, optimize, results, optimizer_done = mnn.init()
```

Create your first Panel widgets: a file input that will accept CSVs, and a DataFrame editor. The DataFrame itself will be available as the editor's `value` attribute.

> :warning: **This part is likely to change soon:** As this is a common combination, we might introduce a separate widget that handles uploads and edits in one line of code

```python
import pandas as pd
import panel as pn

facilities_input = pn.widgets.FileInput()
facilities_df = pn.widgets.Tabulator(
  pd.read_csv('facilities.csv').set_index('Facility'), # load default data
  layout='fit_data_stretch')
```

Link the file input to the editor, so that uploading new data replaces the DataFrame contents.

```python
facilities_input.link(facilities_df, callbacks={
  'value': mnn.create_upload_handler(lambda df: df.set_index('Facility'))
})
```

Now use the `inputs` variable you received from `mnn.init()` to place the widgets on the *Inputs* tab. Both *Inputs* and *Results* tabs are 6-column [GridStacks](https://panel.holoviz.org/reference/layouts/GridStack.html), which means you can place widgets inside using familiar Python syntax.

```python
inputs[0, :2] = pn.Column('## Input files', 'Facilities', facilities_input)
inputs[0, 2:4] = pn.Column('## Facilities', facilities_df)
```

### Step 2: Adding reactive visualizations

If you were writing a regular notebook, at this point you could do something like this to plot the loaded data:

```python
import plotly.graph_objects as go
```

```python
fig = go.Figure(
  layout={'margin': {'t': 5, 'b': 5, 'l': 5, 'r': 5},
  'mapbox': {'style': 'stamen-terrain'}})
fig.add_trace(go.Scattergeo(
  mode='markers',
  lon=facilities_df.value['x'],
  lat=facilities_df.value['y'],
  marker={'size': 10}, name='Facility'))
fig
```

However, since you're building an interactive application, the contents of the DataFrame might change – the user will upload a new CSV or change some values in the editor. It would make sense to rerun the above code cell so that the plot always reflects the current state of the data. Manganite's `%%autoupdate` magic command does exactly that. With a few small changes you can make your figures respond to data changes.

First, give the plot variable a unique name:

```diff
-fig = go.Figure(
+preview = go.Figure(
   layout={'margin': {'t': 5, 'b': 5, 'l': 5, 'r': 5},
   'mapbox': {'style': 'stamen-terrain'}})
-fig.add_trace(go.Scattergeo(
+preview.add_trace(go.Scattergeo(
   mode='markers',
   lon=facilities_df.value['x_fac'],
   lat=facilities_df.value['y_fac'],
   marker={'size': 10}, name='Facility'))
-fig
+preview
```

Next, you can remove the last line and add the `%%autoupdate` invocation at the beginning, like this:

```diff
+%%autoupdate preview --depends-on facilities_df --stage inputs -p 0 4
 preview = go.Figure(
   layout={'margin': {'t': 5, 'b': 5, 'l': 5, 'r': 5},
   'mapbox': {'style': 'stamen-terrain'}})
 preview.add_trace(go.Scattergeo(
   mode='markers',
   lon=facilities_df.value['x_fac'],
   lat=facilities_df.value['y_fac'],
   marker={'size': 10}, name='Facility'))
-preview
```

Any time `facilities_df` changes, the above notebook cell will be evaluated again, and the `preview` variable will be wrapped in a Panel widget and placed on the grid, at coordinates [0, 4]. For a detailed description of `%%autoupdate` syntax, see below.

You are not limited to updating one variable per cell. If you don't pass the `--stage` and `--position` parameters, the code will be re-executed without creating any widgets. This is useful if you need to compute a number of helper variables for later use.

### Step 3: Defining models

To run an optimization model with Manganite, define it as a function and set it as the `on_optimize` handler. It will be launched when the user presses the *Start optimization* button on the *Optimize* tab. The model function can use the widget values directly, or accept them as arguments. If you prefer the latter, you need to bind the widgets to the model with a `pn.bind()` call.

```python
# option 1: no parameters needed

def model():
  # do some calculations
  # ...
  return result_a, result_b, result_c

mnn.on_optimize(model)
```

```python
# option 2: pass widget values as arguments

def model(option_1, option_2):
  # do some calculations
  # ...
  return result_a, result_b, result_c

model_callback = pn.bind(model, option_1=widget_1, option_2=widget_2)
mnn.on_optimize(model_callback)
```

### Step 4: Visualizing results

Plotting the results is again possible with the `%%autoupdate` magic command. You can make your plots depend on the `optimizer_done` widget that `mnn.init()` returned in step 1. To retrieve the return values of the model function, use `mnn.get_result()`

```python
import plotly.express as px
```

```python
%%autoupdate result_plot --depends-on optimizer_done --stage results -p 0 0
if optimizer_done.value == True:
  shipments = mnn.get_result()[1]
  result_plot = px.bar(shipments, barmode='stack',
    title="Customers served by facilities")
```

## %%autoupdate syntax

```
%%autoupdate VARIABLE --depends-on WIDGET1 [WIDGET2 ...]
                     [--stage {inputs,results} --position Y X] 
```

## Serving the application

To serve the notebook without Jupyter, use the command `mnn serve` in your terminal For available options, refer to [Panel documentation](https://panel.holoviz.org/user_guide/Server_Configuration.html).
