import os
import unittest

import scrape_category

MODULE_DIR = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

class TestScrapeCategory(unittest.TestCase):
    CATEGORY_URL = "file:///" + MODULE_DIR + "/test/%s.html"

    def test_scrape(self):
        """
        Scrape the test category, verify the results
        """
        simfiles = scrape_category.get_category_from_ziv("category_test", self.CATEGORY_URL)
        expected = { '27255': scrape_category.Simfile(simfileid='27255', name='Xingfu de Ditu'),
                     '26965': scrape_category.Simfile(simfileid='26965', name="Don't Sleep in the Subway"),
                     '27015': scrape_category.Simfile(simfileid='27015', name='Ai Qing Fu Xing'),
                     '27017': scrape_category.Simfile(simfileid='27017', name='You Baby'),
                     '26969': scrape_category.Simfile(simfileid='26969', name='Dai Yan Ren'),
                     '27069': scrape_category.Simfile(simfileid='27069', name='Cruise') }
        # could just assert simfiles == expected, but want to easily
        # identify the missing item if something is missing
        assert len(simfiles) == len(expected)
        for i in expected:
            assert i in simfiles
            assert expected[i] == simfiles[i]


if __name__ == '__main__':
    unittest.main()
