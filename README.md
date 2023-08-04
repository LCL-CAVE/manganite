# Manganite

Manganite is a dashboarding tool built on the powerful [Panel](https://panel.holoviz.org/) framework. Its primary objective is to allow for an easy transition from a linear Jupyter notebook (load data → build an optimization model → run it → plot results) to an interactive web application, without requiring the user to manually convert most of their existing code to callbacks.

## Installation

Currently Manganite can be built from source and installed using `pip`:

```bash
pip install build
python -m build && pip install dist/manganite-0.0.3-py3-none-any.whl
```

The above command should also take care of installing and enabling the necessary Jupyter Server extensions: one for Panel, to enable the preview pane, and one for Manganite, to preprocess the magic commands before passing the notebook to Panel preview. To ensure proper functioning, remember to **restart your Jupyter Server** after installing the package.

## Usage

To start using Manganite, import the package and load the IPython extension, initializing the dashboard builder and enabling the `%%mnn_...` magic commands.

```python
import manganite
%load_ext manganite
```

### User interface

A typical Manganite dashboard is divided into a header, a main area with three tabs, and a sidebar for optimization logs.

The title in the header is taken from the first level-1 header (a line starting with a single `#` sign) in the notebook's Markdown cells and the *Run* button recalculates the cell marked with the [`%%mnn_model`](#mnn_model) command.

The *Description* tab collects all the Markdown cells from the notebook, allowing you to describe the dashboard and introduce the user to the solution you are presenting. You can freely mix Markdown and Python cells in the notebook to make it more readable when opened in Jupyter. If some parts of your Markdown should not be displayed (e.g. when describing an accompanying code cell), you can exclude them by adding an `mnn-ignore` tag to the notebook cell.

The *Inputs* tab contains a 6-column grid on which you can place various widgets, both for collecting user inputs and visualizing them automatically as they change. See [`%%mnn_input`](#mnn_input) for a complete reference of the magic command.

The *Results* tab also displays widgets arranged in a grid, these however only refresh after a run is completed. See [`%%mnn_result`](#mnn_result) for the respective command's syntax.

### Step 1: Describing inputs

Suppose you're building a model that uses a Pandas DataFrame as one of its inputs. You might write something similar to the following code to load the initial data:

```python
import cvxpy as cp
import pandas as pd
import plotly.express as px
```

```python
supplier_df = pd.read_excel('SupplierSourcing.xlsx', index_col=0)
```

If you'd like the dashboard user to be able to modify the input values, you can turn a DataFrame into a widget by adding a magic command at the beginning of the second cell:

```diff
+%%mnn_input supplier_df -d 0 0 3 -h "Supplier data"
 supplier_df = pd.read_excel('SupplierSourcing.xlsx', index_col=0)
```

`%%mnn_input supplier_df` tells Manganite that the `supplier_df` DataFrame is an input. The next parameter, `-d`, specifies the location of the widget within the *Inputs* tab: `-d 0 0 3` means "display at row 0, column 0, span 3 columns". Finally, `-h "Supplier data"` provides a widget title.

### Step 2: Adding reactive visualizations

If you were writing a regular notebook, at this point you could do something like this to plot the loaded data:

```python
fig = px.bar(
  data_frame = (supplier_df
                .reset_index()
                .melt(id_vars='index')
                .loc[lambda x:x['index']=='Capacity (mt/yr)']),
  x='variable',
  y='value',
  labels={'variable':'Supplier', 'value':'Capacity'},
  template='plotly_white')
fig
```

However, since you're building an interactive application, the contents of the DataFrame might change if the user edits some values using the widget. It would make sense to rerun the above code cell so that the plot always reflects the current state of the data. Manganite's `%%mnn_input` magic command does exactly that. With a few small changes you can make your figures respond to data changes.

First, give the plot variable a unique name:

```diff
-fig = px.bar(
+capacity_chart = px.bar(
   data_frame = (supplier_df
                 .reset_index()
                 .melt(id_vars='index')
                 .loc[lambda x:x['index']=='Capacity (mt/yr)']),
   x='variable',
   y='value',
   labels={'variable':'Supplier', 'value':'Capacity'},
   template='plotly_white')
-fig
+capacity_chart
```

Next, you can remove the last line and add the `%%mnn_input` invocation at the beginning, like this:

```diff
+%%mnn_input capacity_chart -d 0 3 3 --recalc-on supplier_df -h "Capacity"
 capacity_chart = px.bar(
   data_frame = (supplier_df
                 .reset_index()
                 .melt(id_vars='index')
                 .loc[lambda x:x['index']=='Capacity (mt/yr)']),
   x='variable',
   y='value',
   labels={'variable':'Supplier', 'value':'Capacity'},
   template='plotly_white')
-capacity_chart
```

Any time `supplier_df` changes, the above notebook cell will be evaluated again, and the `capacity_chart` variable will be wrapped in a Panel widget and placed on the grid, at coordinates [0, 3].

You are not limited to updating one variable per cell. If you don't pass the `-d` parameter, the code will be re-executed without creating any widgets. This is useful if you need to compute a number of helper variables for later use:

```python
%%mnn_input "helper variables" --recalc-on supplier_df
supplierdata = supplier_df.to_numpy() # dataframe to numpy array
n = len(supplierdata[0]) # number of suppliers
p = (supplierdata[0,:]) # prices
u = (supplierdata[1,:]) # whether from union
t = (supplierdata[2,:]) # whether rail transportation
v = (supplierdata[3,:]) # volatility
c = (supplierdata[4,:]) # capacities

x = cp.Variable(n)
```

### Step 3: Defining models

To run an optimization model with Manganite, put the calculations in a single cell and add the `%%mnn_model` command as the first line. The code will be transformed into a function that will be called when the user presses the *Run* button in the top right corner. During the execution, all output and errors will be redirected to the *Log* widget in the sidebar.

```python
%%mnn_model
objective = cp.Minimize(p@x)

constraints = [cp.sum(x) == 1225]
constraints.append(v@x >= (0.19)*cp.sum(x))
constraints.append(u@x >= (1/2)*cp.sum(x))
constraints.append(t@x <= 650)
constraints.append((1-t)@x <= 720)
constraints.append(x[:] <= c[:])
constraints.append(x >= 0)

prob = cp.Problem(objective, constraints)
prob.solve(solver=cp.GUROBI)

print('Solved!') # this will be displayed in the log
```

### Step 4: Visualizing results

Plotting the results is again possible with the `%%mnn_result` magic command. Unlike `%%mnn_input`, cells annotated with this command don't have dependencies and are recalculated after each successful run of the model.

```python
%%mnn_result solution_chart -d 0 0 6 -h "Solution"
solution_chart = px.bar(
  data_frame=pd.DataFrame({
    'Suppliers':supplier_df.columns,
    'Order volume': x.value}),
  x='Suppliers',
  y='Order volume',
  template='plotly_white')
```

## Magic commands syntax

### `%%mnn_input`

```
%%mnn_input identifier --display Y X W --header HEADER --recalc-on WIDGETS...
```

| parameter         | required | value
| ----------------- | -------: | -----
| `identifier`      |      yes | variable name if `--display` present or a unique quoted string otherwise
| `--display`, `-d` |       no | three integers Y X W representing row/column coordinates and width in columns
| `--header`, `-h`  |       no | any quoted string
| `--recalc-on`     |       no | space-delimited list of variables previously created with `%%mnn_input`

### `%%mnn_model`

```
%%mnn_model
```

This command does not take parameters and can only be used once per notebook.

### `%%mnn_result`

```
%%mnn_result identifier --display Y X W --header HEADER
```

| parameter         | required | value
| ----------------- | -------: | -----
| `identifier`      |      yes | variable name if `--display` present or a unique quoted string otherwise
| `--display`, `-d` |       no | three integers Y X W representing row/column coordinates and width in columns
| `--header`, `-h`  |       no | any quoted string

## Serving the application

To serve the notebook without Jupyter, use the command `mnn serve` in your terminal. For available options, refer to [Panel documentation](https://panel.holoviz.org/user_guide/Server_Configuration.html).
