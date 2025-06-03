"""
Testing template partials.
"""

from django.template import Context, engines
from django.test import TestCase


class PartialTagsTestCase(TestCase):
    def test_partial_tags(self):
        template = """
        {% partialdef testing-partial %}HERE IS THE TEST CONTENT{% endpartialdef %}
        {% partial testing-partial %}
        """

        # Compile and render the template
        engine = engines["django"]
        t = engine.from_string(template)
        # There is inconsistency between from_string and get_template
        # from_string returns Template object, get_template returns TemplateProxy object
        rendered = t.render({})

        # Check the rendered content
        self.assertEqual("HERE IS THE TEST CONTENT", rendered.strip())

    def test_just_partial_from_loader(self):
        engine = engines["django"]

        template = engine.get_template("partial_examples.html#test-partial")
        rendered = template.render(Context({}))
        self.assertEqual("TEST-PARTIAL-CONTENT", rendered.strip())

        template = engine.get_template("partial_examples.html#inline-partial")
        rendered = template.render(Context({}))
        self.assertEqual("INLINE-CONTENT", rendered.strip())
