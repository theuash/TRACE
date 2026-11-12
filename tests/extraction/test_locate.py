from datetime import date

from extraction import locate

BODY = """
<p>CONSOLIDATED BALANCE SHEETS (In millions, except per-share amounts)</p>
<table>
  <tr><td></td><td>September 27, 2026</td><td>September 28, 2025</td></tr>
  <tr><td>Cash and cash equivalents</td><td>36,305</td><td>35,934</td></tr>
  <tr><td>Total current assets</td><td>173,857</td><td>147,957</td></tr>
  <tr><td>Total assets</td><td>404,548</td><td>359,241</td></tr>
  <tr><td>Total liabilities</td><td>292,455</td><td>285,508</td></tr>
</table>
<p>Segment note</p>
<table>
  <tr><td>Total assets by segment</td><td>1</td><td>2</td></tr>
</table>
"""


def test_picks_the_statement_not_the_note(html_file):
    doc = locate.parse_html(html_file(BODY))
    located, warnings = locate.find_statements(doc)

    assert "balance sheet" in located
    assert located["balance sheet"].table_index == 0
    assert warnings == [
        "Could not locate the income statement table in this filing.",
        "Could not locate the cash flow table in this filing.",
    ]


def test_reads_scale_and_periods(html_file):
    doc = locate.parse_html(html_file(BODY))
    located, _ = locate.find_statements(doc)
    sheet = located["balance sheet"]

    assert sheet.scale == 1_000_000
    assert sheet.scale_clear is True
    assert sheet.periods == [date(2026, 9, 27), date(2025, 9, 28)]
