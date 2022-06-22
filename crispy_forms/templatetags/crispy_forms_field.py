from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Tuple

from django import forms, template
from django.conf import settings
from django.template import Context, Variable, loader

from crispy_forms.utils import get_template_pack

if TYPE_CHECKING:
    from django.forms import BoundField, Field
    from django.template.base import Parser, Token
    from django.utils.safestring import SafeString


register = template.Library()


@register.filter
def is_checkbox(field: BoundField) -> bool:
    return isinstance(field.field.widget, forms.CheckboxInput)


@register.filter
def is_password(field: BoundField) -> bool:
    return isinstance(field.field.widget, forms.PasswordInput)


@register.filter
def is_radioselect(field: BoundField) -> bool:
    return isinstance(field.field.widget, forms.RadioSelect) and not isinstance(
        field.field.widget, forms.CheckboxSelectMultiple
    )


@register.filter
def is_select(field: BoundField) -> bool:
    return isinstance(field.field.widget, forms.Select)


@register.filter
def is_checkboxselectmultiple(field: BoundField) -> bool:
    return isinstance(field.field.widget, forms.CheckboxSelectMultiple)


@register.filter
def is_file(field: BoundField) -> bool:
    return isinstance(field.field.widget, forms.FileInput)


@register.filter
def is_clearable_file(field: BoundField) -> bool:
    return isinstance(field.field.widget, forms.ClearableFileInput)


@register.filter
def is_multivalue(field: BoundField) -> bool:
    return isinstance(field.field.widget, forms.MultiWidget)


@register.filter
def classes(field: Field) -> str | None:
    """
    Returns CSS classes of a field
    """
    return field.widget.attrs.get("class", None)


@register.filter
def css_class(field: BoundField) -> str:
    """
    Returns widgets class name in lowercase
    """
    return field.field.widget.__class__.__name__.lower()


def pairwise(iterable: Iterable[str]) -> zip[Tuple[str, str]]:
    """s -> (s0,s1), (s2,s3), (s4, s5), ..."""
    a = iter(iterable)
    return zip(a, a)


class CrispyFieldNode(template.Node):
    def __init__(self, field: str, attrs: dict[str, str]):
        self.field = field
        self.attrs = attrs

    def render(self, context: Context) -> str:
        # Nodes are not threadsafe so we must store and look up our instance
        # variables in the current rendering context first
        if self not in context.render_context:
            context.render_context[self] = (
                Variable(self.field),
                self.attrs,
            )

        field, attrs = context.render_context[self]
        field = field.resolve(context)

        # There are special django widgets that wrap actual widgets,
        # such as forms.widgets.MultiWidget, admin.widgets.RelatedFieldWidgetWrapper
        widgets = getattr(field.field.widget, "widgets", [getattr(field.field.widget, "widget", field.field.widget)])

        if isinstance(attrs, dict):
            attrs = [attrs] * len(widgets)

        converters = getattr(settings, "CRISPY_CLASS_CONVERTERS", {})

        for widget, attr in zip(widgets, attrs):
            class_name = widget.__class__.__name__.lower()
            class_name = converters.get(class_name, class_name)
            css_class = widget.attrs.get("class", "")
            if css_class:
                if css_class.find(class_name) == -1:
                    css_class += " %s" % class_name
            else:
                css_class = class_name

            widget.attrs["class"] = css_class

            for attribute_name, attribute in attr.items():
                attribute_name = Variable(attribute_name).resolve(context)
                attributes = Variable(attribute).resolve(context)

                if attribute_name in widget.attrs:
                    # multiple attribtes are in a single string, e.g.
                    # "form-control is-invalid"
                    for attr in attributes.split():
                        if attr not in widget.attrs[attribute_name].split():
                            widget.attrs[attribute_name] += " " + attr
                else:
                    widget.attrs[attribute_name] = attributes

        return str(field)


@register.tag(name="crispy_field")
def crispy_field(parser: Parser, token: Token) -> CrispyFieldNode:
    """
    {% crispy_field field attrs %}
    """
    tokens = token.split_contents()
    field = tokens.pop(1)
    attrs = {}

    # We need to pop tag name, or pairwise would fail
    tokens.pop(0)
    for attribute_name, value in pairwise(tokens):
        attrs[attribute_name] = value

    return CrispyFieldNode(field, attrs)


@register.simple_tag()
def crispy_addon(
    field: BoundField, append: str = "", prepend: str = "", form_show_labels: bool = True
) -> SafeString | None:
    """
    Renders a form field using bootstrap's prepended or appended text::

        {% crispy_addon form.my_field prepend="$" append=".00" %}

    You can also just prepend or append like so

        {% crispy_addon form.my_field prepend="$" %}
        {% crispy_addon form.my_field append=".00" %}
    """
    if field:
        if not prepend and not append:
            raise TypeError("Expected a prepend and/or append argument")
        context = {
            "field": field,
            "form_show_errors": True,
            "form_show_labels": form_show_labels,
            "crispy_prepended_text": prepend,
            "crispy_appended_text": append,
        }
        template = loader.get_template("%s/layout/prepended_appended_text.html" % get_template_pack())
    return template.render(context)
