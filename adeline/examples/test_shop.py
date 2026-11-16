from unittest.mock import patch
import shop


def test_bad():
    with patch("shop.calculate_total", return_value=100):
        assert shop.calculate_total(["book"]) == 100


def test_boundary():
    with patch("shop.fetch_price", return_value=20):
        assert shop.calculate_total(["book", "pen"]) == 40
