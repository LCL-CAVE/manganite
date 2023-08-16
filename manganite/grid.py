from panel.layout.base import ListLike
from panel.reactive import ReactiveHTML


class Grid(ReactiveHTML, ListLike):
    # id attributes are altered by Panel
    # to make them unique for each instance
    _template = '''
    <div id="mnn-grid" class="mnn-grid">
      {% for obj in objects -%}
        <div id="mnn-grid__item" class="mnn-grid__item">
          ${obj}
        </div>
      {%- endfor %}
    </div>
    '''
    
    # `display: contents` on item wrappers
    # lets each item specify its own grid coordinates
    # by setting `grid-row-start` and `grid-column` on itself
    _stylesheets = ['''
    .mnn-grid {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      grid-template-rows: auto;
      place-items: stretch;
    }
                    
    .mnn-grid__item {
      display: contents;
    }
    ''']
