from dataclasses import dataclass, field
from typing import List

import pytest
from jinja2 import DictLoader, UndefinedError

from jinja2_component.environment import ComponentEnvironment


def test_no_template_field():
    @dataclass
    class NoTemplateField:
        name: str

    env = ComponentEnvironment([NoTemplateField])
    env.loader = DictLoader({'template.html', '<html></html>'})

    # TODO we should throw the exact error at some point
    with pytest.raises(TypeError):
        env.get_template('template.html')


def test_template_path_expression():
    @dataclass
    class TemplatePathExpression:
        name: str = 'TemplatePathExpression'

    env = ComponentEnvironment([TemplatePathExpression])
    env.loader = DictLoader({
        'main.html': '<html><body>'
                     '{% set extension = ".html" %}'
                     '{% TemplatePathExpression template = "component" + extension %}'
                     '<body></html>',
        'component.html': '<span>Component</span>'
    })

    template = env.get_template('main.html')
    assert template.render() == '<html><body><span>Component</span><body></html>'


def test_component_with_children():
    @dataclass
    class ComponentWithChildren:
        children: bool
        template: str = 'component.html'

    env = ComponentEnvironment([ComponentWithChildren])
    env.loader = DictLoader({
        'main.html': '<html><body>'
                     '{% ComponentWithChildren %}'
                     '<span>Body of the tag for the {{ component.template }}</span>'
                     '{% endComponentWithChildren %}'
                     '</body></html>',
        'component.html': '<div class="header"></div>'
                          '<div class="content">{{ children() }}</div>'
                          '<div class="footer"></div>'
    })

    template = env.get_template('main.html')
    assert template.render() == '<html><body>' \
                                '<div class="header"></div>' \
                                '<div class="content">' \
                                '<span>Body of the tag for the component.html</span>' \
                                '</div>' \
                                '<div class="footer"></div>' \
                                '</body></html>'


def test_access_children_in_childfree_component():
    @dataclass
    class ComponentWithoutChildren:
        template: str = 'component.html'

    env = ComponentEnvironment([ComponentWithoutChildren])
    env.loader = DictLoader({
        'main.html': '<html><body>'
                     '{% ComponentWithoutChildren %}'
                     '</body></html>',
        'component.html': '{{ children() }}'
    })

    template = env.get_template('main.html')

    with pytest.raises(UndefinedError):
        template.render()


def test_dataclass_fields_render():
    def build_color_list():
        return ['red', 'green', 'blue']

    @dataclass
    class PaintTool:
        # defaults with prop value
        paint_color: str
        # defaults without prop value
        effect: str
        # default value without prop value
        default_color: str = 'red'
        # default factory without prop value
        color_list: List[str] = field(default_factory=build_color_list)
        # default value with prop value
        size: int = 10
        # default factory with prop value
        properties: List[str] = field(default_factory=list)

        template: str = 'paint_tool.html'

    env = ComponentEnvironment([PaintTool])
    env.loader = DictLoader({
        'painter.html': '<html><body>'
                        '{% PaintTool paint_color = "green", size = 15, properties = ["soft", "tapered"] %}'
                        '</body></html>',
        'paint_tool.html': '<ul>'
                           '<li>{{ component.paint_color }}</li>'
                           '<li>{{ component.effect }}</li>'
                           '<li>{{ component.default_color }}</li>'
                           '<li>colors: {{ component.color_list|join(", ") }}</li>'
                           '<li>{{ component.size }}</li>'
                           '<li>properties: {{ component.properties|join(", ") }}</li>'
                           '</ul>',
    })
    template = env.get_template('painter.html')

    assert template.render() == '<html><body>' \
                                '<ul>' \
                                '<li>green</li>' \
                                '<li></li>' \
                                '<li>red</li>' \
                                '<li>colors: red, green, blue</li>' \
                                '<li>15</li>' \
                                '<li>properties: soft, tapered</li>' \
                                '</ul>' \
                                '</body></html>'


def test_nested_elements():
    @dataclass
    class Page:
        children: bool
        title: str
        template: str = 'page.html'

    @dataclass
    class Navigation:
        template: str = 'navigation.html'

    @dataclass
    class Article:
        children: bool
        template: str = 'article.html'

    env = ComponentEnvironment([Page, Navigation, Article])
    env.loader = DictLoader({
        'main.html': '<html>'
                     '{% Page title = "Jinja2" %}'
                     '{% Navigation %}'
                     '{% Article title = "AST Nodes" %}'
                     '<ul><li>Include</li><li>Macro</li><li>Scope</li><li>Assign</li><li>Name</li><li>Const</li></ul>'
                     '{% endArticle %}'
                     '{% endPage %}'
                     '</html>',
        'page.html': '<head><title>{{ component.title }}</title><head><body>{{ children() }}</body>',
        'navigation.html': '<div class="navigation">'
                           '<div class="button prev">Prev</div>'
                           '<div class="button next">Next</div>'
                           '</div>',
        'article.html': '<div class="article">'
                        '<div class="title">{{ component.title }}</div>'
                        '<div class="content">{{ children() }}</div>'
                        '</div>',
    })

    template = env.get_template('main.html')
    assert template.render() == '<html>' \
                                '<head><title>Jinja2</title><head>' \
                                '<body>' \
                                '<div class="navigation">' \
                                '<div class="button prev">Prev</div><div class="button next">Next</div>' \
                                '</div>' \
                                '<div class="article">' \
                                '<div class="title">AST Nodes</div>' \
                                '<div class="content"><ul>' \
                                '<li>Include</li>' \
                                '<li>Macro</li>' \
                                '<li>Scope</li>' \
                                '<li>Assign</li>' \
                                '<li>Name</li>' \
                                '<li>Const</li>' \
                                '</ul></div>' \
                                '</div>' \
                                '</body>' \
                                '</html>'
