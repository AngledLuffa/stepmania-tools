import os
import unittest

import scrape_category

MODULE_DIR = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

EXPECTED_SIMFILES = {
    '27255': scrape_category.Simfile(simfileid='27255', name='Xingfu de Ditu', age='5 hours ago'),
    '26965': scrape_category.Simfile(simfileid='26965', name="Don't Sleep in the Subway", age='1.6 days ago'),
    '27015': scrape_category.Simfile(simfileid='27015', name='Ai Qing Fu Xing', age='1 minute ago'),
    '27017': scrape_category.Simfile(simfileid='27017', name='You Baby', age='1 year ago'),
    '26969': scrape_category.Simfile(simfileid='26969', name='Dai Yan Ren', age='2.4 weeks ago'),
    '27069': scrape_category.Simfile(simfileid='27069', name='Cruise', age='10 months ago')
}

EXPECTED_FILTERED = {
    '26965': scrape_category.Simfile(simfileid='26965', name="Don't Sleep in the Subway", age='1.6 days ago'),
    '26969': scrape_category.Simfile(simfileid='26969', name='Dai Yan Ren', age='2.4 weeks ago'),
}

def compare_simfile_records(results, expected):
    # could just assert simfiles == expected, but want to easily
    # identify the missing item if something is missing
    assert len(results) == len(expected)
    for i in expected:
        assert i in results
        assert results[i] == expected[i]


class TestScrapeCategory(unittest.TestCase):
    CATEGORY_URL = "file:///" + MODULE_DIR + "/test/%s.html"

    def test_scrape(self):
        """
        Scrape the test category, verify the results
        """
        simfiles = scrape_category.get_category_from_ziv("category_test", self.CATEGORY_URL)
        compare_simfile_records(simfiles, EXPECTED_SIMFILES)

class TestUtilityMethods(unittest.TestCase):
    def test_filter(self):
        filtered = scrape_category.filter_simfiles_prefix(EXPECTED_SIMFILES, "D")
        compare_simfile_records(filtered, EXPECTED_FILTERED)

if __name__ == '__main__':
    unittest.main()
