from extraction.locate import scale_of

APPLE_CAPTION = (
    "(in millions, except number of shares, which are reflected in thousands, and per-share"
    " amounts): Period Ended"
)


def test_apples_caption_is_millions_not_thousands():
    assert scale_of(APPLE_CAPTION) == 1_000_000


def test_a_plain_thousands_table_still_reads_thousands():
    assert scale_of("(in thousands)") == 1_000


def test_nearest_mention_wins():
    assert scale_of("results in millions then in thousands") == 1_000


def test_no_scale_is_none():
    assert scale_of("consolidated statements of income") is None
