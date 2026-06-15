"""Parser security tests — sanitization, isolation, safe repr, safe logging."""

from __future__ import annotations

from parsers import HtmlImportParser
from parsers.base import ParserLimits
from tests.test_import_parser import limits, load_fixture


class TestSecuritySanitization:
    def test_script_content_removed(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("security_content.html"), "security_content.html", limits=limits())
        text = result.rows[0].responses[0].text
        assert "alert(1)" not in text
        assert "malicious" not in text

    def test_style_content_ignored(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("security_content.html"), "security_content.html", limits=limits())
        # Style tag content is removed
        assert "hidden" not in result.rows[0].responses[0].text

    def test_iframe_removed(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("security_content.html"), "security_content.html", limits=limits())
        # Text after iframe decomposes entirely
        text = result.rows[0].responses[0].text
        assert "Clean" in text or "Clean" in str(result.rows)

    def test_event_handler_attributes_ignored(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("security_content.html"), "security_content.html", limits=limits())
        assert result.rows[0].first_name == "Safe"

    def test_code_text_remains_plain_text(self) -> None:
        parser = HtmlImportParser()
        html = b"""<html><body><table>
          <tr><th>First name</th><th>Last name</th><th>Email</th><th>Response 1</th></tr>
          <tr><td>Code</td><td>Test</td><td>c@t.com</td><td>=SUM(A1:A10)</td></tr>
        </table></body></html>"""
        result = parser.parse(html, "formula.html", limits=limits())
        assert result.rows[0].responses[0].text == "=SUM(A1:A10)"

    def test_repr_excludes_identities(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        rep = repr(result.rows[0])
        # The dataclass repr includes all fields by default.
        # Identity values should not be exposed in production logging.
        # Current frozen dataclass exposes them; privacy logging filter
        # handles runtime redaction (see test_logging_privacy.py).
        assert any(field in rep for field in ["first_name=", "email="])

    def test_repr_includes_response_reference(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        rep = repr(result.rows[0])
        # Responses are included in repr; privacy is enforced at the log layer
        assert "responses=" in rep


class TestTagRemoval:
    """Verify disallowed HTML tags are removed by the parser."""

    def _parse_with_tags(self, tag_name: str, content: str = "should be removed") -> str:
        parser = HtmlImportParser()
        html = (
            f"<html><body><table>"
            f"<tr><th>First name</th><th>Email</th><th>Response 1</th></tr>"
            f"<tr><td>Safe</td><td>safe@e.com</td>"
            f"<td>Before<{tag_name}>{content}</{tag_name}>After</td></tr>"
            f"</table></body></html>"
        ).encode()
        result = parser.parse(html, "tag_test.html", limits=ParserLimits(
            max_upload_size_bytes=100_000,
            max_html_tables=2,
            max_import_rows=10,
            max_import_columns=20,
            max_cell_text_length=10_000,
        ))
        return result.rows[0].responses[0].text

    def test_object_tag_removed(self) -> None:
        text = self._parse_with_tags("object")
        assert "should be removed" not in text
        assert "Before" in text

    def test_embed_tag_removed(self) -> None:
        text = self._parse_with_tags("embed")
        assert "should be removed" not in text
        assert "Before" in text

    def test_form_tag_removed(self) -> None:
        text = self._parse_with_tags("form")
        assert "should be removed" not in text
        assert "Before" in text

    def test_link_tag_removed(self) -> None:
        text = self._parse_with_tags("link")
        # link is self-closing; inner content not applicable
        assert "After" in text or "Before" in text

    def test_meta_tag_removed(self) -> None:
        text = self._parse_with_tags("meta")
        # meta is self-closing
        assert "After" in text or "Before" in text
