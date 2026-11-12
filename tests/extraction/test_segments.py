from decimal import Decimal

from extraction import locate, segments

BODY = """
<p>Net sales by segment (in millions)</p>
<table>
  <tr><td></td><td>2026</td><td>2025</td></tr>
  <tr><td>U.S.</td><td>167,746</td><td>151,790</td></tr>
  <tr><td>China (1)</td><td>82,378</td><td>64,377</td></tr>
  <tr><td>Other countries</td><td>228,710</td><td>199,994</td></tr>
  <tr><td>Total net sales</td><td>478,834</td><td>416,161</td></tr>
</table>
"""


def test_segments_sum_to_the_reported_total(html_file, make_filing):
    doc = locate.parse_html(html_file(BODY))
    found = segments.find_segments(doc, make_filing(), set(), None)

    assert len(found) == 1
    table = found[0]
    assert table.reported_total == Decimal("478834000000")
    assert [segment.name for segment in table.segments] == ["U.S.", "China (1)", "Other countries"]
    assert sum(segment.value for segment in table.segments) == table.reported_total


def test_no_segment_table_gives_an_empty_list(html_file, make_filing):
    doc = locate.parse_html(html_file("<table><tr><td>Total assets</td><td>1</td></tr></table>"))
    assert segments.find_segments(doc, make_filing(), set(), None) == []
