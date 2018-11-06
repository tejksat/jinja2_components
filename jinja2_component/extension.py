"""

Generic Jinja2 extension for all components

Jinja2 has extensions. Though our components act like Jinja2 extensions,
in that they have different tag names, they are really all the same
thing, extension wise.

Thus, we have one kind of extension which knows how to handle all
registered "components" and dispatch correctly.

"""
import dataclasses
from dataclasses import MISSING
from typing import Set

from jinja2.ext import Extension
from jinja2.nodes import Include, Macro, Scope, Assign, Name, Const

TEMPLATE_FIELD_NAME = 'template'
CHILDREN_FIELD_NAME = 'children'

CHILDREN_MACRO_NAME = 'children'


class ComponentExtension(Extension):
    tags: Set

    def parse(self, parser):
        # Get the component for the tag name that we matched on
        tag_name = parser.stream.current[2]
        component_class = self.environment.components[tag_name]
        field_names = [f.name for f in dataclasses.fields(component_class)]
        has_children = CHILDREN_FIELD_NAME in field_names

        lineno = next(parser.stream).lineno

        node = Scope(lineno=lineno)

        # List of Assign nodes for tag properties
        props = []

        while parser.stream.current.type != 'block_end':
            lineno = parser.stream.current.lineno
            if props:
                parser.stream.expect('comma')
            target = parser.parse_assign_target()
            parser.stream.expect('assign')
            value = parser.parse_expression()
            props.append(Assign(target, value, lineno=lineno))

        # Assign nodes from dataclass fields and the list of tag properties
        assign_nodes = self._dataclass_assign_nodes(component_class, lineno) + props

        if has_children:
            inner_block = list(parser.parse_statements(
                ('name:end' + tag_name,),
                drop_needle=True)
            )
            # create children() macro
            children_macro = Macro()
            children_macro.name = CHILDREN_MACRO_NAME
            children_macro.args = []
            children_macro.defaults = []
            children_macro.body = inner_block
            children_macro_nodes = [children_macro]
        else:
            children_macro_nodes = []

        # include tag template
        include_tag = Include()
        include_tag.template = Name(TEMPLATE_FIELD_NAME, 'load')
        include_tag.ignore_missing = False
        include_tag.with_context = True

        node.body = assign_nodes + children_macro_nodes + [include_tag, ]

        return node

    @staticmethod
    def _dataclass_assign_nodes(component_class, lineno):
        result = []

        def assign_node_for_field(name, value):
            return Assign(Name(name, 'store', lineno=lineno), Const(value), lineno=lineno)

        for f in dataclasses.fields(component_class):
            if f.default is not MISSING:
                result.append(assign_node_for_field(f.name, f.default))
            elif f.default_factory is not MISSING:
                # TODO here we could use `Call` node as the assigning expression
                result.append(assign_node_for_field(f.name, f.default_factory()))

        return result
