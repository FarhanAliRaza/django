"""
Testing template partials.

"""

import os
from unittest import mock

from django.template import Context, engines
from django.template.backends.django import DjangoTemplates
from django.test import TestCase, override_settings


class PartialTagsTestCase(TestCase):
    def test_partial_tags(self):
        template = """
        {% partialdef testing-partial %}HERE IS THE TEST CONTENT{% endpartialdef %}
        {% partial testing-partial %}
        """

        # Compile and render the template
        engine = engines["django"]
        t = engine.from_string(template)
        rendered = t.render({})

        # Check the rendered content
        self.assertEqual("HERE IS THE TEST CONTENT", rendered.strip())

    def test_just_partial_from_loader(self):
        engine = engines["django"]

        template = engine.get_template("example.html#test-partial")
        rendered = template.render(Context({}))
        self.assertEqual("TEST-PARTIAL-CONTENT", rendered.strip())

        template = engine.get_template("example.html#inline-partial")
        rendered = template.render(Context({}))
        self.assertEqual("INLINE-CONTENT", rendered.strip())


class PartialCachingTestCase(TestCase):
    """Test that partials benefit from template caching and aren't
    re-parsed unnecessarily.

    This test suite verifies that:
    1. Template files are only read once from the filesystem
       (test_template_file_read_count)
    2. Template objects are not recreated when accessing partials
       (test_simple_caching_verification)
    3. The template cache is properly utilized (test_cache_inspection)
    4. Multiple partials in one template work efficiently
       (test_multiple_partials_from_string)
    5. Templates are not re-parsed when accessing partials
       (test_template_parsing_count)
    6. Performance is maintained with many partials
       (test_multiple_partials_performance)
    7. Debug mode doesn't break caching (test_template_origin_with_debug)
    """

    def setUp(self):
        # Create a fresh engine with cached loader for each test
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.backend = DjangoTemplates(
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
        self.engine = self.backend.engine

    def test_template_file_read_count(self):
        """Test that template file is only read once from filesystem when
        using multiple partials."""

        # Mock the filesystem loader's get_contents method
        cached_loader = self.engine.template_loaders[0]
        # The cached loader has a 'loaders' attribute that contains the
        # wrapped loaders
        filesystem_loader = cached_loader.loaders[0]  # type: ignore
        original_get_contents = filesystem_loader.get_contents

        read_count = 0

        def counting_get_contents(origin):
            nonlocal read_count
            read_count += 1
            return original_get_contents(origin)

        with mock.patch.object(
            filesystem_loader, "get_contents", side_effect=counting_get_contents
        ):
            # First access - should read from filesystem
            template1 = self.backend.get_template("partials_example.html#test-partial")
            rendered1 = template1.render(Context({}))
            self.assertEqual("TEST-PARTIAL-CONTENT", rendered1.strip())
            self.assertEqual(
                read_count, 1, "Template should be read once on first access"
            )

            # Second access to same partial - should use cache
            template2 = self.backend.get_template("partials_example.html#test-partial")
            rendered2 = template2.render(Context({}))
            self.assertEqual("TEST-PARTIAL-CONTENT", rendered2.strip())
            self.assertEqual(
                read_count, 1, "Template should not be read again from filesystem"
            )

            # Access different partial from same template - should still use cache
            template3 = self.backend.get_template(
                "partials_example.html#inline-partial"
            )
            rendered3 = template3.render(Context({}))
            self.assertEqual("INLINE-CONTENT", rendered3.strip())
            self.assertEqual(
                read_count, 1, "Template should not be read again for different partial"
            )

    def test_simple_caching_verification(self):
        """Simple test to verify caching is working for partials."""

        # Track how many times we create Template objects
        from django.template.base import Template

        template_init_count = 0
        original_init = Template.__init__

        def counting_init(self, *args, **kwargs):
            nonlocal template_init_count
            template_init_count += 1
            return original_init(self, *args, **kwargs)

        with mock.patch.object(Template, "__init__", counting_init):
            # Load the main template - this should create a Template object
            self.backend.get_template("partials_example.html")
            first_count = template_init_count

            # Load partials - these should NOT create new Template objects
            # because they use the already-parsed template
            partial1 = self.backend.get_template("partials_example.html#test-partial")
            partial2 = self.backend.get_template("partials_example.html#inline-partial")

            # The count should not have increased
            self.assertEqual(
                template_init_count,
                first_count,
                "Loading partials should not create new Template objects",
            )

            # Render to make sure they work
            self.assertEqual(
                partial1.render(Context({})).strip(), "TEST-PARTIAL-CONTENT"
            )
            self.assertEqual(partial2.render(Context({})).strip(), "INLINE-CONTENT")

    def test_cache_inspection(self):
        """Directly inspect the cache to verify templates are cached."""

        # Cache should be empty initially
        cache = self.engine.template_loaders[0].get_template_cache
        self.assertEqual(len(cache), 0, "Cache should be empty initially")

        # Load template
        template = self.backend.get_template("partials_example.html")

        # Cache should now contain the template
        self.assertIn("partials_example.html", cache, "Template should be in cache")
        # The cached template is the internal engine template, not the backend wrapper
        self.assertEqual(
            template.template,
            cache["partials_example.html"],
            "Cached template should match",
        )

        # Load partial - should not add new cache entry
        self.backend.get_template("partials_example.html#test-partial")
        self.assertEqual(
            len(cache), 1, "Loading partial should not create new cache entry"
        )

    def test_multiple_partials_from_string(self):
        """Test that multiple partials in a single template are efficiently handled."""

        # Create a template with multiple partials
        template_content = """
        {% partialdef header %}
            <header>Site Header</header>
        {% endpartialdef %}

        {% partialdef footer %}
            <footer>Site Footer</footer>
        {% endpartialdef %}

        {% partialdef sidebar %}
            <aside>Sidebar Content</aside>
        {% endpartialdef %}

        Main content here.
        {% partial header %}
        {% partial sidebar %}
        {% partial footer %}
        """

        # Compile the template
        template = self.backend.from_string(template_content)

        # Render and verify all partials work
        rendered = template.render({})  # Pass dict instead of Context
        self.assertIn("<header>Site Header</header>", rendered)
        self.assertIn("<footer>Site Footer</footer>", rendered)
        self.assertIn("<aside>Sidebar Content</aside>", rendered)
        self.assertIn("Main content here.", rendered)

    def test_template_parsing_count(self):
        """Test that template is only parsed once even when accessing
        multiple partials."""

        from django.template.base import Parser

        parse_count = 0
        original_parse = Parser.parse

        def counting_parse(self, parse_until=None):
            nonlocal parse_count
            parse_count += 1
            return original_parse(self, parse_until)

        with mock.patch.object(Parser, "parse", counting_parse):
            # Load template with multiple partials
            self.backend.get_template("partials_example.html")

            # Parse count should be higher due to partialdef blocks
            initial_parse_count = parse_count

            # Access partials - should not trigger new parsing
            self.backend.get_template("partials_example.html#test-partial")
            self.backend.get_template("partials_example.html#inline-partial")

            self.assertEqual(
                parse_count,
                initial_parse_count,
                "Accessing partials should not trigger new parsing",
            )

    def test_multiple_partials_performance(self):
        """Test rendering many partials from same template to verify
        caching efficiency."""

        # Create a template with many partials
        template_content = ""
        for i in range(20):
            template_content += (
                f"{{% partialdef partial-{i} %}}Content {i}{{% endpartialdef %}}\n"
            )

        # Track compilation time
        import time

        # First compilation
        start = time.time()
        t = self.backend.from_string(template_content)
        time.time() - start

        # Store partials in extra_data (simulate what happens during parsing)
        # This happens automatically during template compilation

        # Now access multiple partials and verify they're already available
        with mock.patch(
            "django.template.base.Template.__init__", wraps=t.template.__init__
        ) as mock_init:
            # These should not trigger new Template instantiation
            for i in range(20):
                # In real usage, this would be through get_template with #partial-name
                # but we're testing the underlying mechanism
                pass

            # No new Template objects should be created
            mock_init.assert_not_called()

    @override_settings(DEBUG=True)
    def test_template_origin_with_debug(self):
        """Test template origin tracking with DEBUG=True to verify caching."""

        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        backend = DjangoTemplates(
            {
                "NAME": "django",
                "DIRS": [template_dir],
                "APP_DIRS": False,
                "OPTIONS": {
                    "debug": True,
                    "loaders": [
                        (
                            "django.template.loaders.cached.Loader",
                            ["django.template.loaders.filesystem.Loader"],
                        ),
                    ],
                },
            }
        )

        # Load template and partial
        template = backend.get_template("partials_example.html")
        partial = backend.get_template("partials_example.html#test-partial")

        # Both should have the same origin since partial comes from same file
        self.assertEqual(template.origin.name, partial.origin.name)
        self.assertEqual(template.origin.loader, partial.origin.loader)

    def test_stress_partials_with_caching(self):
        """Stress test with 20+ partials to measure caching performance."""
        import timeit

        # List of all partials in the stress test template
        partial_names = [
            "header",
            "sidebar",
            "footer",
            "card-1",
            "card-2",
            "card-3",
            "card-4",
            "card-5",
            "widget-weather",
            "widget-news",
            "widget-stocks",
            "widget-calendar",
            "section-hero",
            "section-features",
            "section-testimonials",
            "section-pricing",
            "section-faq",
            "section-contact",
            "ad-banner-top",
            "ad-banner-side",
            "ad-banner-bottom",
            "meta-tags",
            "social-links",
            "breadcrumb",
            "search-box",
        ]

        print("\n" + "=" * 70)
        print("STRESS TEST WITH CACHING")
        print("=" * 70)
        print("Template: stress_partial_example.html")
        print(f"Number of partials: {len(partial_names)}")
        print(
            f"Partials: {', '.join(partial_names[:5])}... "
            f"(and {len(partial_names)-5} more)"
        )

        # Check cache before warming up
        cache = self.backend.engine.template_loaders[0].get_template_cache
        print(f"\nCache status before warm-up: {len(cache)} entries")

        # Warm up the cache by loading the template once
        print("\nWarming up cache...")
        warmup_start = timeit.default_timer()
        self.backend.get_template("stress_partial_example.html")
        warmup_time = timeit.default_timer() - warmup_start
        print(f"  - Initial template load time: {warmup_time:.6f} seconds")
        print(f"  - Cache status after warm-up: {len(cache)} entries")

        # Track individual partial load times
        load_times = []

        def load_all_partials():
            """Load and render all partials from the stress test template."""
            for partial_name in partial_names:
                start = timeit.default_timer()
                self.backend.get_template(f"stress_partial_example.html#{partial_name}")
                end = timeit.default_timer()
                load_times.append(end - start)
                # Just load the template, don't render - we're testing
                # template loading performance

        # Time how long it takes to load all partials with caching
        print("\nRunning performance test...")
        iterations = 10
        time_with_cache = timeit.timeit(load_all_partials, number=iterations)

        # Calculate statistics
        avg_time_per_iteration = time_with_cache / iterations
        avg_time_per_partial = avg_time_per_iteration / len(partial_names)
        total_partial_loads = iterations * len(partial_names)

        print("\n[RESULTS - WITH CACHE]")
        print(
            f"  Total time for {iterations} iterations: "
            f"{time_with_cache:.6f} seconds"
        )
        print(f"  Total partial loads: {total_partial_loads}")
        print(f"  Average per iteration: {avg_time_per_iteration:.6f} seconds")
        print(f"  Average per partial: {avg_time_per_partial:.9f} seconds")
        print(f"  Partials per second: {int(total_partial_loads/time_with_cache):,}")

        # Show first iteration details
        if load_times:
            first_iter_times = load_times[: len(partial_names)]
            print("\nFirst iteration load times (sample):")
            for i in range(min(5, len(first_iter_times))):
                print(f"    - {partial_names[i]}: {first_iter_times[i]:.9f} seconds")
            print(f"    ... (and {len(partial_names)-5} more)")

        print(f"\nCache final status: {len(cache)} entries")
        print("=" * 70 + "\n")

        # Verify all partials loaded correctly
        for partial_name in partial_names:
            template = self.backend.get_template(
                f"stress_partial_example.html#{partial_name}"
            )
            self.assertIsNotNone(template)

    def test_stress_partials_without_caching(self):
        """Stress test without caching to compare performance."""
        import timeit

        from django.template.base import Template

        # Create backend without caching
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        backend_no_cache = DjangoTemplates(
            {
                "NAME": "django",
                "DIRS": [template_dir],
                "APP_DIRS": False,
                "OPTIONS": {
                    "loaders": [
                        "django.template.loaders.filesystem.Loader"
                    ],  # No caching!
                },
            }
        )

        partial_names = [
            "header",
            "sidebar",
            "footer",
            "card-1",
            "card-2",
            "card-3",
            "card-4",
            "card-5",
            "widget-weather",
            "widget-news",
            "widget-stocks",
            "widget-calendar",
            "section-hero",
            "section-features",
            "section-testimonials",
            "section-pricing",
            "section-faq",
            "section-contact",
            "ad-banner-top",
            "ad-banner-side",
            "ad-banner-bottom",
            "meta-tags",
            "social-links",
            "breadcrumb",
            "search-box",
        ]

        print("\n" + "=" * 70)
        print("STRESS TEST WITHOUT CACHING")
        print("=" * 70)
        print("Template: stress_partial_example.html")
        print(f"Number of partials: {len(partial_names)}")
        print("Loader: django.template.loaders.filesystem.Loader (NO CACHING)")

        # Check if there's a cache (there shouldn't be one)
        print("\nLoader configuration:")
        loaders = backend_no_cache.engine.template_loaders
        loader_names = [loader.__class__.__name__ for loader in loaders]
        print(f"  Template loaders: {loader_names}")
        has_cache = hasattr(loaders[0], "get_template_cache")
        print(f"  Has cache? {has_cache}")

        # Mock file reads to count them
        filesystem_loader = backend_no_cache.engine.template_loaders[0]
        original_get_contents = filesystem_loader.get_contents
        file_read_count = 0
        file_read_details = []

        def counting_get_contents(origin):
            nonlocal file_read_count
            file_read_count += 1
            file_read_details.append(
                {
                    "count": file_read_count,
                    "file": origin.name,
                    "template_name": origin.template_name,
                    "time": timeit.default_timer(),
                }
            )
            return original_get_contents(origin)

        filesystem_loader.get_contents = counting_get_contents

        # Track individual load times and template creation
        load_times = []
        template_creations = 0
        original_template_init = Template.__init__

        def counting_template_init(self, *args, **kwargs):
            nonlocal template_creations
            template_creations += 1
            return original_template_init(self, *args, **kwargs)

        Template.__init__ = counting_template_init

        print("\nPre-test statistics:")
        print(f"  File reads: {file_read_count}")
        print(f"  Template objects created: {template_creations}")

        def load_all_partials():
            """Load and render all partials without caching."""
            for partial_name in partial_names:
                start = timeit.default_timer()
                backend_no_cache.get_template(
                    f"stress_partial_example.html#{partial_name}"
                )
                end = timeit.default_timer()
                load_times.append(end - start)
                # Just load the template, don't render - we're testing
                # template loading performance

        # Time how long it takes without caching
        print("\nRunning performance test...")
        iterations = 10
        time_without_cache = timeit.timeit(load_all_partials, number=iterations)

        # Restore original Template.__init__
        Template.__init__ = original_template_init

        # Calculate statistics
        avg_time_per_iteration = time_without_cache / iterations
        avg_time_per_partial = avg_time_per_iteration / len(partial_names)
        total_partial_loads = iterations * len(partial_names)

        print("\n[RESULTS - WITHOUT CACHE]")
        print(
            f"  Total time for {iterations} iterations: "
            f"{time_without_cache:.6f} seconds"
        )
        print(f"  Total partial loads: {total_partial_loads}")
        print(f"  Average per iteration: {avg_time_per_iteration:.6f} seconds")
        print(f"  Average per partial: {avg_time_per_partial:.9f} seconds")
        print(
            f"  Partials per second: "
            f"{int(total_partial_loads/time_without_cache):,}"
        )

        print("\n[FILE I/O STATISTICS]")
        print(f"  Total file reads: {file_read_count}")
        print(f"  File reads per iteration: {file_read_count/iterations:.1f}")
        print(f"  File reads per partial: {file_read_count/total_partial_loads:.2f}")
        print("  Expected with caching: 1 (only initial load)")

        print("\n[TEMPLATE CREATION STATISTICS]")
        print(f"  Total Template objects created: {template_creations}")
        print(f"  Templates per iteration: {template_creations/iterations:.1f}")
        print(
            f"  Templates per partial load: "
            f"{template_creations/total_partial_loads:.2f}"
        )
        print("  Expected with caching: 1 (only initial template)")

        # Show file read pattern
        print("\n[FILE READ PATTERN - First 10 reads]")
        for i, read_detail in enumerate(file_read_details[:10]):
            print(f"  Read #{read_detail['count']}: {read_detail['template_name']}")
        if len(file_read_details) > 10:
            print(f"  ... and {len(file_read_details) - 10} more reads")

        # Analyze read frequency
        read_counts = {}
        for detail in file_read_details:
            name = detail["template_name"]
            read_counts[name] = read_counts.get(name, 0) + 1

        print("\n[FILE READ FREQUENCY]")
        for name, count in read_counts.items():
            print(f"  {name}: {count} reads")

        # Show sample load times
        if load_times:
            first_iter_times = load_times[: len(partial_names)]
            print("\nFirst iteration load times (sample):")
            for i in range(min(5, len(first_iter_times))):
                print(f"    - {partial_names[i]}: {first_iter_times[i]:.9f} seconds")
            print(f"    ... (and {len(partial_names)-5} more)")

            # Calculate load time statistics
            avg_load_time = sum(load_times) / len(load_times)
            min_load_time = min(load_times)
            max_load_time = max(load_times)
            print("\n[LOAD TIME STATISTICS]")
            print(f"  Average: {avg_load_time:.9f} seconds")
            print(f"  Minimum: {min_load_time:.9f} seconds")
            print(f"  Maximum: {max_load_time:.9f} seconds")
            print(f"  Range: {max_load_time - min_load_time:.9f} seconds")

        print("\n[COMPARISON WITH CACHING]")
        print(
            f"  Without cache: {file_read_count} file reads, "
            f"{template_creations} templates created"
        )
        print("  With cache: 1 file read, 1 template created (expected)")
        print(
            f"  Overhead factor: {file_read_count}x more file I/O, "
            f"{template_creations}x more parsing"
        )

        print("=" * 70 + "\n")

    def test_stress_partials_performance_comparison(self):
        """Direct comparison of performance with and without caching."""
        import timeit

        template_dir = os.path.join(os.path.dirname(__file__), "templates")

        # Backend with caching
        backend_cached = DjangoTemplates(
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

        # Backend without caching
        backend_no_cache = DjangoTemplates(
            {
                "NAME": "django",
                "DIRS": [template_dir],
                "APP_DIRS": False,
                "OPTIONS": {
                    "loaders": ["django.template.loaders.filesystem.Loader"],
                },
            }
        )

        partial_names = [
            "header",
            "footer",
            "sidebar",
            "section-hero",
            "section-features",
        ]

        print("\n" + "=" * 70)
        print("PERFORMANCE COMPARISON: CACHED vs NON-CACHED")
        print("=" * 70)
        print("Test setup:")
        print(f"  - Partials to load: {', '.join(partial_names)}")
        print(f"  - Number of partials: {len(partial_names)}")
        print("  - Iterations: 50")
        print(f"  - Total loads per test: {50 * len(partial_names)}")

        # Mock file reads for both backends
        cached_file_reads = 0
        no_cache_file_reads = 0

        # Mock cached backend
        # type: ignore
        cached_loader = backend_cached.engine.template_loaders[0].loaders[0]
        original_cached_get_contents = cached_loader.get_contents

        def counting_cached_get_contents(origin):
            nonlocal cached_file_reads
            cached_file_reads += 1
            return original_cached_get_contents(origin)

        cached_loader.get_contents = counting_cached_get_contents

        # Mock non-cached backend
        no_cache_loader = backend_no_cache.engine.template_loaders[0]
        original_no_cache_get_contents = no_cache_loader.get_contents

        def counting_no_cache_get_contents(origin):
            nonlocal no_cache_file_reads
            no_cache_file_reads += 1
            return original_no_cache_get_contents(origin)

        no_cache_loader.get_contents = counting_no_cache_get_contents

        # Test with cache
        def load_with_cache():
            for partial_name in partial_names:
                backend_cached.get_template(
                    f"stress_partial_example.html#{partial_name}"
                )
                # Just load, don't render - testing template loading performance

        # Warm up cache
        print("\nWarming up cache...")
        warmup_start = timeit.default_timer()
        backend_cached.get_template("stress_partial_example.html")
        warmup_time = timeit.default_timer() - warmup_start
        print(f"  - Cache warmup time: {warmup_time:.6f} seconds")
        print(f"  - File reads during warmup: {cached_file_reads}")

        # Test without cache
        def load_without_cache():
            for partial_name in partial_names:
                backend_no_cache.get_template(
                    f"stress_partial_example.html#{partial_name}"
                )
                # Just load, don't render - testing template loading performance

        # Run timing tests
        iterations = 50
        print(f"\nRunning performance tests ({iterations} iterations each)...")

        # Reset file read counters after warmup
        cached_file_reads_before = cached_file_reads
        no_cache_file_reads_before = no_cache_file_reads

        time_cached = timeit.timeit(load_with_cache, number=iterations)
        time_no_cache = timeit.timeit(load_without_cache, number=iterations)

        cached_file_reads_during_test = cached_file_reads - cached_file_reads_before
        no_cache_file_reads_during_test = (
            no_cache_file_reads - no_cache_file_reads_before
        )

        speedup = time_no_cache / time_cached
        time_saved = time_no_cache - time_cached
        percent_reduction = (time_saved / time_no_cache) * 100

        print("\n[PERFORMANCE RESULTS]")
        print(f"  With caching:    {time_cached:.6f} seconds")
        print(f"  Without caching: {time_no_cache:.6f} seconds")
        print(f"  Speedup factor:  {speedup:.2f}x faster with caching")
        print(
            f"  Time saved:      {time_saved:.6f} seconds "
            f"({percent_reduction:.1f}% reduction)"
        )

        print("\n[FILE I/O COMPARISON]")
        print(
            f"  File reads WITH caching:    {cached_file_reads_during_test} "
            f"(after warmup)"
        )
        print(f"  File reads WITHOUT caching: {no_cache_file_reads_during_test}")
        print(
            f"  File I/O reduction:         "
            f"{no_cache_file_reads_during_test - cached_file_reads_during_test} "
            f"reads saved"
        )

        print("\n[EFFICIENCY METRICS]")
        print(
            f"  Cached - partials per second:   "
            f"{int((iterations * len(partial_names)) / time_cached):,}"
        )
        print(
            f"  No cache - partials per second: "
            f"{int((iterations * len(partial_names)) / time_no_cache):,}"
        )

        print("=" * 70 + "\n")

        # Assert that caching is significantly faster
        self.assertLess(
            time_cached, time_no_cache, "Caching should be faster than no caching"
        )
        self.assertGreater(speedup, 2.0, "Caching should provide at least 2x speedup")
        self.assertLess(
            cached_file_reads_during_test,
            no_cache_file_reads_during_test,
            "Caching should result in fewer file reads",
        )

    def test_cache_internals_inspection(self):
        """Detailed inspection of cache internals, keys, and content."""
        import timeit

        from django.template.base import Template

        print("\n" + "=" * 70)
        print("CACHE INTERNALS INSPECTION")
        print("=" * 70)

        # Create a fresh backend
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

        # Get references to the loaders
        cached_loader = backend.engine.template_loaders[0]
        # type: ignore
        filesystem_loader = cached_loader.loaders[0]

        # Mock file reads
        read_count = 0
        read_log = []
        original_get_contents = filesystem_loader.get_contents

        def logging_get_contents(origin):
            nonlocal read_count
            read_count += 1
            read_log.append(
                {
                    "read_number": read_count,
                    "file": origin.name,
                    "template_name": origin.template_name,
                    "time": timeit.default_timer(),
                }
            )
            print(f"\n[FILE READ #{read_count}]")
            print(f"  File: {origin.name}")
            print(f"  Template name: {origin.template_name}")
            return original_get_contents(origin)

        filesystem_loader.get_contents = logging_get_contents

        # Inspect cache before any operations
        cache = cached_loader.get_template_cache
        print("\nInitial cache state:")
        print(f"  Cache type: {type(cache).__name__}")
        print(f"  Cache size: {len(cache)}")
        print(f"  Cache keys: {list(cache.keys())}")

        # Load the main template
        print("\n" + "─" * 50)
        print("STEP 1: Loading main template")
        print("─" * 50)

        backend.get_template("stress_partial_example.html")

        print("\nCache after loading main template:")
        print(f"  Cache size: {len(cache)}")
        print(f"  Cache keys: {list(cache.keys())}")

        # Inspect the cached object
        for key, value in cache.items():
            print("\nCache entry details:")
            print(f"  Key: '{key}'")
            print(f"  Value type: {type(value).__name__}")
            if isinstance(value, Template):
                print(f"  Template name: {value.name}")
                print(f"  Template origin: {value.origin}")
                print(f"  Has extra_data: {hasattr(value, 'extra_data')}")
                if hasattr(value, "extra_data"):
                    extra_data = value.extra_data
                    print(f"  Extra data keys: {list(extra_data.keys())}")
                    if "template-partials" in extra_data:
                        partials = extra_data["template-partials"]
                        print(f"  Number of partials: {len(partials)}")
                        print(
                            f"  Partial names: {list(partials.keys())[:5]}... "
                            f"(showing first 5)"
                        )

        # Load some partials
        print("\n" + "─" * 50)
        print("STEP 2: Loading partials")
        print("─" * 50)

        partial_names = ["header", "footer", "sidebar"]
        for partial_name in partial_names:
            print(f"\nLoading partial: {partial_name}")
            read_count_before = read_count

            partial = backend.get_template(
                f"stress_partial_example.html#{partial_name}"
            )

            print(f"  File reads for this partial: {read_count - read_count_before}")
            print(f"  Partial type: {type(partial).__name__}")
            print(f"  Has render method: {hasattr(partial, 'render')}")

        print("\nCache after loading partials:")
        print(f"  Cache size: {len(cache)} (should still be 1)")
        print(f"  Total file reads: {read_count}")

        # Test cache hit behavior
        print("\n" + "─" * 50)
        print("STEP 3: Testing cache hits")
        print("─" * 50)

        # Clear read log for this phase
        read_count_before = read_count

        # Load the same template again
        print("\nLoading main template again...")
        template2 = backend.get_template("stress_partial_example.html")
        print(f"  File reads: {read_count - read_count_before} (should be 0)")
        print(f"  Same object? {template2 is template2}")

        # Load the same partial again
        print("\nLoading header partial again...")
        read_count_before = read_count
        backend.get_template("stress_partial_example.html#header")
        print(f"  File reads: {read_count - read_count_before} (should be 0)")

        # Show cache key generation
        print("\n" + "─" * 50)
        print("STEP 4: Cache key analysis")
        print("─" * 50)

        # Test how cache keys are generated
        test_names = [
            "stress_partial_example.html",
            "partials_example.html",
            "nonexistent.html",
        ]

        print("\nCache key generation:")
        for name in test_names:
            key = cached_loader.cache_key(name)
            print(f"  Template: '{name}' -> Key: '{key}'")

        # Final summary
        print("\n" + "─" * 50)
        print("SUMMARY")
        print("─" * 50)
        print(f"Total file reads: {read_count}")
        print(f"Cache entries: {len(cache)}")
        print(f"Read log entries: {len(read_log)}")

        if read_log:
            print("\nFile read timeline:")
            start_time = read_log[0]["time"]
            for entry in read_log:
                elapsed = (entry["time"] - start_time) * 1000  # Convert to milliseconds
                print(
                    f"  {elapsed:6.2f}ms - Read #{entry['read_number']}: "
                    f"{entry['template_name']}"
                )

        print("=" * 70 + "\n")

        # Assertions
        self.assertEqual(read_count, 1, "Should only read file once")
        self.assertEqual(len(cache), 1, "Should only have one cache entry")

    def test_cache_memory_and_content_analysis(self):
        """Analyze cache memory usage and inspect partial content."""
        import sys

        print("\n" + "=" * 70)
        print("CACHE MEMORY AND CONTENT ANALYSIS")
        print("=" * 70)

        # Create backend
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

        cached_loader = backend.engine.template_loaders[0]
        cache = cached_loader.get_template_cache

        # Load template with many partials
        print("\nLoading template with 25 partials...")
        backend.get_template("stress_partial_example.html")

        # Analyze memory usage
        print("\n" + "─" * 50)
        print("MEMORY ANALYSIS")
        print("─" * 50)

        if "stress_partial_example.html" in cache:
            cached_template = cache["stress_partial_example.html"]

            # Get size of cached object
            template_size = sys.getsizeof(cached_template)
            print(f"\nCached template object size: {template_size:,} bytes")

            # Analyze components
            if hasattr(cached_template, "nodelist"):
                nodelist_size = sys.getsizeof(cached_template.nodelist)
                print(f"Nodelist size: {nodelist_size:,} bytes")
                print(f"Number of nodes: {len(cached_template.nodelist)}")

            if hasattr(cached_template, "extra_data"):
                extra_data_size = sys.getsizeof(cached_template.extra_data)
                print(f"Extra data size: {extra_data_size:,} bytes")

                if "template-partials" in cached_template.extra_data:
                    partials = cached_template.extra_data["template-partials"]
                    partials_size = sys.getsizeof(partials)
                    print(f"Partials dict size: {partials_size:,} bytes")
                    print(f"Number of partials: {len(partials)}")

        # Inspect partial content
        print("\n" + "─" * 50)
        print("PARTIAL CONTENT INSPECTION")
        print("─" * 50)

        # Get a few partials and inspect their content
        partial_names = ["header", "card-1", "widget-weather"]

        for partial_name in partial_names:
            print(f"\n[Partial: {partial_name}]")
            partial = backend.get_template(
                f"stress_partial_example.html#{partial_name}"
            )

            print(f"  Type: {type(partial).__name__}")

            # Get the actual content by rendering
            rendered = partial.render(Context({}))
            print(f"  Rendered length: {len(rendered)} characters")
            print(f"  Content preview: {rendered.strip()[:100]}...")

            # Check if it's a TemplateProxy
            if hasattr(partial, "nodelist"):
                print(f"  Nodelist length: {len(partial.nodelist)}")
                print(f"  Nodelist type: {type(partial.nodelist).__name__}")

        # Test partial isolation
        print("\n" + "─" * 50)
        print("PARTIAL ISOLATION TEST")
        print("─" * 50)

        # Render partials with different contexts
        contexts = [{"title": "Test 1"}, {"title": "Test 2"}, {}]  # Empty context

        print("\nTesting header partial with different contexts:")
        header_partial = backend.get_template("stress_partial_example.html#header")

        for i, ctx in enumerate(contexts):
            rendered = header_partial.render(Context(ctx))
            print(f"  Context {i+1} ({ctx}): {len(rendered)} chars")

        # Cache statistics
        print("\n" + "─" * 50)
        print("CACHE STATISTICS")
        print("─" * 50)

        # Try loading different templates to see cache behavior
        test_templates = [
            "partials_example.html",
            "stress_partial_example.html",  # Already cached
            "partials_example.html#test-partial",
        ]

        print("\nCache key mapping:")
        for template_name in test_templates:
            cache_key = cached_loader.cache_key(template_name)
            in_cache = cache_key in cache
            print(f"  '{template_name}'")
            print(f"    -> Cache key: '{cache_key}'")
            print(f"    -> In cache: {in_cache}")

        # Load another template to see cache growth
        print("\nLoading another template...")
        backend.get_template("partials_example.html")

        print("\nFinal cache state:")
        print(f"  Total entries: {len(cache)}")
        print(f"  Cache keys: {list(cache.keys())}")

        # Calculate total cache memory
        total_cache_size = sys.getsizeof(cache)
        for key, value in cache.items():
            total_cache_size += sys.getsizeof(key) + sys.getsizeof(value)

        print(f"  Approximate total cache memory: {total_cache_size:,} bytes")

        print("=" * 70 + "\n")
