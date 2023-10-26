[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/LCL-CAVE/codespaces-manganite)

# Manganite

Manganite is a dashboarding tool built on the powerful [Panel](https://panel.holoviz.org/) framework. Its primary objective is to allow for an easy transition from a linear Jupyter notebook (load data → build a model → run it → plot results) to an interactive web application, without requiring the user to manually convert most of their existing code to callbacks.

## Installation

Mangnite can be installed on Linux, Windows, or Mac with ``pip``:

```bash
pip install manganite
```

The above command should also take care of installing and enabling the necessary Jupyter Server extensions: one for Panel, to enable the preview pane, and one for Manganite, to preprocess the magic commands before passing the notebook to Panel preview. To ensure proper functioning, remember to **restart your Jupyter Server** after installing the package.

## How it works

Manganite parses your Jupyter notebook and builds a dependency tree between its cells. Scalar variables and Pandas DataFrames are transparently wrapped in [Param](https://param.holoviz.org/) classes, which lets them watch their values for changes and propagate these changes downstream.

Any variable of a [supported type](#widget-types) can be bound to a dashboard widget. The binding is bidirectional, so any change to the variable's value through the user interface will be reflected in the code and vice versa. Every time one of these variables is modified, any other cell that reads its value is re-evaluated and all the related widgets are updated, creating an interactive experience for the end user.

Cells that contain long-running function calls can also be marked as executed on demand, and all their dependent cells will also wait for them to finish, making it possible to control complex optimization processes and plot their results.

## Usage

To start using Manganite, import the package and load the IPython extension, initializing the dashboard builder and enabling the `%%mnn` magic command. Typically this should be the first cell in the notebook.

```python
import manganite
%load_ext manganite
```

For each subsequent cell, you have the option to annotate it with `%%mnn widget` if it should display something, `%%mnn execute` if it should run only after a button is pressed, or skip the annotation altogether for no side effects. See the [reference](#mnn-magic-command) for a detailed description of the magic command.

### User interface

A typical Manganite dashboard is divided into a header, a main area with tabs, and a sidebar for optimization logs.

The title in the header is taken from the first level-1 header (a line starting with a single `#` sign) in the notebook's Markdown cells.

The *Description* tab collects all the Markdown cells from the notebook, allowing you to describe the dashboard and introduce the user to the solution you are presenting. You can freely mix Markdown and Python cells in the notebook to make it more readable when opened in Jupyter. If some parts of your Markdown should not be displayed (e.g. when describing an accompanying code cell), you can exclude them by adding an `mnn-ignore` tag to the notebook cell.

The other tabs contain a 6-column grid on which you can place various widgets, both for collecting user inputs and visualizing them automatically as they change.

### Step 1: Describing inputs

Suppose you're modeling a supplier sourcing problem, using a Pandas DataFrame as one of its inputs. You might write something similar to the following code to load the initial data:

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
+%%mnn widget --type table --var supplier_df --tab "Inputs" --header "Supplier data"
 supplier_df = pd.read_excel('SupplierSourcing.xlsx', index_col=0)
```

Let's break down the magic command above:

- `%%mnn widget` tells Manganite that this cell defines a dashboard widget
- `--type table` specifies what the widget will be, in this case a table, currently the only available choice for representing a DataFrame
- `--var supplier_df` points to the variable that will be bound to the widget
- `--tab "Inputs"` places the widget on a tab called *Inputs* – if it doesn't exist at this point, it will be created
- `--header "Supplier data"` gives the table a header, so that the user knows what data they are modifying

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

However, since you're building an interactive application, the contents of the DataFrame might change if the user edits some values using the widget. It would make sense to rerun the above code cell so that the plot always reflects the current state of the data. Manganite's dependency tree takes care of that. With a few small changes you can display figures that respond to data changes.

First, give the plot variable a unique name – this ensures it won't get overwritten by other plots:

```diff
-px.bar(
+capacity_chart = px.bar(
   data_frame = (supplier_df
                 .reset_index()
                 .melt(id_vars='index')
                 .loc[lambda x:x['index']=='Capacity (mt/yr)']),
   x='variable',
   y='value',
   labels={'variable':'Supplier', 'value':'Capacity'},
   template='plotly_white')
+capacity_chart
```

Next, you add the `%%mnn widget` invocation at the beginning, like this:

```diff
+%%mnn widget --type plot --var capacity_chart --tab "Inputs" --header "Capacity"
 capacity_chart = px.bar(
   data_frame = (supplier_df
                 .reset_index()
                 .melt(id_vars='index')
                 .loc[lambda x:x['index']=='Capacity (mt/yr)']),
   x='variable',
   y='value',
   labels={'variable':'Supplier', 'value':'Capacity'},
   template='plotly_white')
capacity_chart
```

Since this cell accesses the variable `supplier_df`, Manganite knows that any time `supplier_df` changes, it needs to be evaluated again. The `capacity_chart` variable will be wrapped in a Panel widget and placed on the grid, next to the table we created in the previous step.

Cells without an annotation behave just the same, except they don't display anything on recalculation. This is useful if you need to compute a number of helper variables for later use:

```python
# this is just a regular notebook cell
# but Manganite will still rerun it if supplier_df is changed
# because x depends on n depends on supplierdata depends on supplier_df

supplierdata = supplier_df.to_numpy()
n = len(supplierdata[0]) # number of suppliers
p = (supplierdata[0,:]) # prices
u = (supplierdata[1,:]) # whether from union
t = (supplierdata[2,:]) # whether rail transportation
v = (supplierdata[3,:]) # volatility
c = (supplierdata[4,:]) # capacities

x = cp.Variable(n)
```

### Step 3: Defining models

To run an optimization model with Manganite, put the calculations in a single cell and add the `%%mnn execute` command as the first line. The code will be transformed into a function that will be called when the user presses a button. If you use the `--tab` argument, you can place the button on a tab like any other widget, otherwise it will show in the page header on the right.

During the execution of a cell annotated with `%%mnn execute`, all standard output and exceptions will be redirected to the *Log* widget in the sidebar.

```python
%%mnn execute --on button "Optimize" --returns x
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

Plotting the results is yet another use of the `%%mnn widget` magic command. 
Since in the `%%mnn execute` cell above the `--returns` argument was set to `x`, all further cells that reference `x` will hold off their first execution until the above cell finishes at least once. This way the entire *Results* tab can be hidden until the optimization succeeds.

```python
%%mnn widget --type plot --var solution_chart --tab "Results" --header "Solution"
solution_chart = px.bar(
  data_frame=pd.DataFrame({
    'Suppliers':supplier_df.columns,
    'Order volume': x.value}), # we access x here
  x='Suppliers',
  y='Order volume',
  template='plotly_white')
```

You can further explore this example by opening [supplier_sourcing.ipynb](examples/supplier_sourcing.ipynb).

### Step 5: Deploy the dashboard as a web application

The final step is to serve the dashboard as a web application so that you can view it with a web browser. Assuming the file name is `supplier_selection.ipynb`, you simply add a cell containing the following line and execute the notebook.

```
!mnn serve manganite-demo.ipynb
```

Of course, this will block the notebook from further use. An alternative is to call the following from the terminal

```
mnn serve manganite-demo.ipynb --autoreload
```

The resulting dashboard will automatically reload each time you save the notebook, which allows you to make changes and view the results live in the browser.

## Reference

### `%%mnn` magic command

> :bulb: square brackets indicate optionality

```
%%mnn widget --type TYPE [PARAMS] --var VAR_NAME --tab TAB [--position ROW COL SPAN] --header HEADER
```

| name                 | required | value
| -------------------- | -------: | -----
| `TYPE`               |      yes | one of [supported types](#widget-types)
| `PARAMS`             |       no | context-dependent parameters, see [supported types](#widget-types)
| `VAR_NAME`           |      yes | name of the variable to be bound to the widget
| `TAB`                |      yes | any quoted string; if no tab with such label exists, it will be created
| `ROW`, `COL`, `SPAN` |       no | three integers representing row/column coordinates (0-based) and width in columns on a 6-column grid

```
%%mnn execute --on TRIGGER PARAMS [--tab TAB] --returns VAR_NAME
```

| name       | required | value
| ---------- | -------: | -----
| `TRIGGER`  |      yes | currently always `button`
| `PARAMS`   |      yes | currently always a quoted string (button label)
| `TAB`      |       no | any quoted string; if no tab with such label exists, it will be created; if not present, the button will be added to the app header
| `VAR_NAME` |      yes | name of the variable representing the main result of the process; all further cells referencing it will hold off their first execution until the current cell finishes at least once

### Widget types

Widgets in Manganite are strictly tied to the types of their bound variables. The table below lists all possible configurations.

| variable type       | widget `TYPE` | widget `PARAMS`
| ------------------- | ------------- | ---------------
| `bool`              | `checkbox`    | n/a
| `bool`              | `switch`      | n/a
| `str`               | `text`        | n/a
| `str`               | `select`      | name of the variable holding the options (a collection of strings, can be any of `list`, `tuple`, `set`)
| `str`               | `radio`       | same as for `select`
| `str`               | `file`        | optional comma-separated list of [unique file type specifiers](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/file#unique_file_type_specifiers) for filtering available files
| `int`               | `slider`      | `MIN:MAX:STEP` where all values are integer literals
| `int`               | `text`        | n/a
| `float`             | `slider`      | `MIN:MAX:STEP` where all values are number literals
| `float`             | `text`        | n/a
| `datetime.date`     | `date`        | n/a
| `datetime.datetime` | `datetime`    | n/a
| `pandas.DataFrame`  | `table`       | n/a

## Serving the application

The `mnn serve` command is a simple wrapper for the `panel serve` command. For available options, we refer to the [Panel documentation](https://panel.holoviz.org/how_to/server/index.html).

## Running Manganite in GitHub Codespaces

GitHub Codespaces provides a seamless environment for running and experimenting with Manganite. To get started, follow these simple steps:

1. **Create a GitHub Codespace:**

   - Using Codespces requires a github login. Log in to your account or create a new one.
   - Open the [Manganite Codespace repository](https://github.com/daniel-dobos-unilu/codespaces-manganite)
   - Click on the "Code" button and then select "Open with Codespaces."

2. **Access Manganite in Codespaces:**

   GitHub Codespaces will create a development environment for you. Once the environment is ready, you will find Manganite available to use in the Codespaces terminal.

3. **Explore Manganite and app Galery:**

  You can now start experimenting with Manganite! Check out the app galery with different usecases and explore the widgets, and learn how to create dashboards with ease.