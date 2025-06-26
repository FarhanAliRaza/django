"""
Testing template partials.
"""

import os
from unittest import mock

from django.template import Context, TemplateSyntaxError, engines
from django.template.backends.django import DjangoTemplates
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

    def test_undefined_partial_error(self):
        template = """
        {% partial testing-partial %}
        """

        engine = engines["django"]
        t = engine.from_string(template)
        with self.assertRaisesMessage(
            TemplateSyntaxError,
            "No partials are defined. You are trying to access 'testing-partial' "
            "partial",
        ):
            t.render({})


class PartialTagsCacheTestCase(TestCase):
    def test_partials_use_cached_loader_when_configured(self):
        """Test that partials benefit from template caching and file system
        loader is only called once."""

        # Create backend with cached loader
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        backend = DjangoTemplates(
            {
                "NAME": "django",
                "DIRS": [template_dir],
                "APP_DIRS": False,
                "OPTIONS": {
                    "loaders": [
                        (
                            "django.template.loaders.cached.Loader",
                            ["django.template.loaders.filesystem.Loader"],
                        ),
                    ],
                },
            }
        )

        # Get the filesystem loader and mock its get_contents method
        cached_loader = backend.engine.template_loaders[0]
        filesystem_loader = cached_loader.loaders[0]

        with mock.patch.object(
            filesystem_loader, "get_contents", wraps=filesystem_loader.get_contents
        ) as mock_get_contents:
            # Load the full template
            full_template = backend.get_template("partial_examples.html")
            rendered_full = full_template.render({})
            self.assertIn("TEST-PARTIAL-CONTENT", rendered_full)

            # Load just the partial
            partial_template = backend.get_template(
                "partial_examples.html#test-partial"
            )
            rendered_partial = partial_template.render(Context({}))
            self.assertEqual("TEST-PARTIAL-CONTENT", rendered_partial.strip())

            # Assert filesystem was only accessed once
            mock_get_contents.assert_called_once()
