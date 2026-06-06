"""tests/security/test_xss_sanitization.py — XSS/script-injection sanitization tests.
Verifies that nh3 correctly cleans various XSS vectors in *_html fields.
"""

import pytest
from components.renderer import sanitize

@pytest.mark.parametrize("vector", [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>",
    "<a href='javascript:alert(1)'>click me</a>",
    "<iframe src='javascript:alert(1)'></iframe>",
    "<math><mtext><option><fake><script>alert(1)</script></fake></option></mtext></math>",
    "<p style='width: expression(alert(1))'>XSS</p>",
    "<div onmouseover='alert(1)'>Hover me</div>",
    "<a href='http://example.com' onclick='alert(1)'>Link</a>",
    "<p><object data='javascript:alert(1)'></object></p>",
    "<embed src='javascript:alert(1)'></embed>",
    "<details open ontoggle=alert(1)>",
    "<form action='javascript:alert(1)'><input type=submit></form>",
    "<!--<script>alert(1)</script>-->", # Commented out script (should be safe anyway)
    "<scr<script>ipt>alert(1)</script>", # Nested script tags
])
def test_xss_vectors_are_cleaned(vector):
    sanitized = sanitize(vector)
    # The primary goal is that nothing executable remains.
    # Tags like <script> should be removed.
    assert "<script" not in sanitized.lower()
    assert "<iframe" not in sanitized.lower()
    assert "<svg" not in sanitized.lower()
    assert "<math" not in sanitized.lower()
    assert "<object" not in sanitized.lower()
    assert "<embed" not in sanitized.lower()
    assert "<form" not in sanitized.lower()
    
    # Event handlers should be stripped from any remaining tags
    assert "onerror" not in sanitized.lower()
    assert "onload" not in sanitized.lower()
    assert "onclick" not in sanitized.lower()
    assert "onmouseover" not in sanitized.lower()
    assert "ontoggle" not in sanitized.lower()
    
    # javascript: URIs should be removed from href etc.
    assert "javascript:" not in sanitized.lower()
    
    # Style-based XSS (expression, etc.)
    assert "expression(" not in sanitized.lower()

def test_allowed_html_is_preserved():
    html = "<h1>Title</h1><p>This is a <strong>paragraph</strong> with a <a href='https://example.com'>link</a>.</p>"
    sanitized = sanitize(html)
    assert "<h1>Title</h1>" in sanitized
    assert "<p>This is a <strong>paragraph</strong>" in sanitized
    assert "<a href=\"https://example.com\" rel=\"noopener noreferrer\">link</a>" in sanitized

def test_unsupported_tags_are_stripped():
    html = "<marquee>Wheee</marquee><blink>Blinky</blink>"
    sanitized = sanitize(html)
    assert "<marquee>" not in sanitized
    assert "<blink>" not in sanitized
    assert "Wheee" in sanitized
    assert "Blinky" in sanitized

def test_sanitization_handles_none():
    assert sanitize(None) == ""
    assert sanitize("") == ""
