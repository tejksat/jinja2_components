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

from jinja2 import nodes
from jinja2.ext import Extension

TMP_COMPONENT_DICT_NAME = '__component'
COMPONENT_DICT_NAME = 'component'

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

        node = nodes.Scope(lineno=lineno)

        # list of `Pair` nodes for tag properties to update "component" dictionary
        component_dict_update_items = []

        while parser.stream.current.type != 'block_end':
            lineno = parser.stream.current.lineno
            if component_dict_update_items:
                parser.stream.expect('comma')
            name = parser.stream.expect('name')
            parser.stream.expect('assign')
            value = parser.parse_expression()
            component_dict_update_items.append(nodes.Pair(nodes.Const(name.value), value))

        # dictionary initialization in the "component" name
        prepare_component_dict = [self._initialize_component_dict(component_class, lineno)]

        if component_dict_update_items:
            component_dict_delta = nodes.Dict(component_dict_update_items)
            # `Getattr` for "update" function of the dictionary "component"
            update_component_dict_fun = nodes.Getattr(nodes.Name(TMP_COMPONENT_DICT_NAME, 'load'), 'update', 'load')
            # `Call` for `component.update(<prop name>, <prop value>)`
            call_component_dict_update = nodes.Call(update_component_dict_fun, [component_dict_delta], [], None, None)
            prepare_component_dict.append(nodes.ExprStmt(call_component_dict_update))

        # assign `component = __component` and `__component = None`
        prepare_component_dict.extend([
            nodes.Assign(nodes.Name(COMPONENT_DICT_NAME, 'store', lineno=lineno),
                         nodes.Name(TMP_COMPONENT_DICT_NAME, 'load', lineno=lineno),
                         lineno=lineno),
            nodes.Assign(nodes.Name(TMP_COMPONENT_DICT_NAME, 'store', lineno=lineno),
                         nodes.Const(None, lineno=lineno),
                         lineno=lineno)
        ])

        if has_children:
            inner_block = list(parser.parse_statements(
                ('name:end' + tag_name,),
                drop_needle=True)
            )
            # create children() macro
            children_macro = nodes.Macro()
            children_macro.name = CHILDREN_MACRO_NAME
            children_macro.args = []
            children_macro.defaults = []
            children_macro.body = inner_block
            children_macro_nodes = [children_macro]
        else:
            children_macro_nodes = []

        # include tag template
        include_tag = nodes.Include()
        # use `template` item of the "component" dictionary for template path
        include_tag.template = nodes.Getitem(nodes.Name(COMPONENT_DICT_NAME, 'load', lineno=lineno),
                                             nodes.Const(TEMPLATE_FIELD_NAME, lineno=lineno), 'load', lineno=lineno)
        include_tag.ignore_missing = False
        include_tag.with_context = True

        node.body = prepare_component_dict + children_macro_nodes + [include_tag, ]

        return node

    @staticmethod
    def _initialize_component_dict(component_class, lineno):
        items = []

        def pair_node_for_field(name, value):
            return nodes.Pair(nodes.Const(name, lineno=lineno), nodes.Const(value, lineno=lineno), lineno=lineno)

        for f in dataclasses.fields(component_class):
            if f.default is not MISSING:
                items.append(pair_node_for_field(f.name, f.default))
            elif f.default_factory is not MISSING:
                # TODO here we could use `Call` node as the assigning expression
                items.append(pair_node_for_field(f.name, f.default_factory()))

        component_dict = nodes.Dict(items, lineno=lineno)

        # `Assign` dictionary to the "component" name
        return nodes.Assign(nodes.Name(TMP_COMPONENT_DICT_NAME, 'store', lineno=lineno), component_dict, lineno=lineno)
