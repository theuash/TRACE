from decimal import Decimal

from lxml import html as lxml_html

from extraction.table_parser import parse_rows

TABLE = """
<table>
  <tr>
    <td>Total assets</td><td>$</td><td>404,548</td><td></td><td>$</td><td>359,241</td><td></td>
  </tr>
  <tr><td>Property, plant and equipment, net</td><td>(1,234)</td><td>1,000</td></tr>
  <tr><td>Cash and cash equivalents</td><td>\u2014</td><td>9</td></tr>
  <tr><td></td><td></td><td></td></tr>
</table>
"""


def rows():
    return parse_rows(lxml_html.fromstring(TABLE))


def test_currency_split_into_its_own_cell_is_ignored():
    total_assets = rows()[0]
    assert total_assets.label == "Total assets"
    assert total_assets.values == [Decimal("404548"), Decimal("359241")]
    assert total_assets.raws == ["404,548", "359,241"]


def test_parentheses_negative_and_wellformed_penalty():
    row = rows()[1]
    assert row.values[0] == Decimal("-1234")
    assert row.wellformed == 0.6


def test_dash_is_zero_not_missing():
    row = rows()[2]
    assert row.values[0] == Decimal(0)
    assert row.wellformed == 0.4


def test_empty_rows_are_dropped():
    assert len(rows()) == 3
