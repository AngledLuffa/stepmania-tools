import glob
import os
import shutil
import tempfile
import time
import unittest

import scrape_category

MODULE_DIR = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

EXPECTED_SIMFILES = {
    '27255': scrape_category.Simfile(simfileid='27255', name='Xingfu de Ditu', age=18000),
    '26965': scrape_category.Simfile(simfileid='26965', name="Don't Sleep in the Subway", age=138240),
    '27015': scrape_category.Simfile(simfileid='27015', name='Ai Qing Fu Xing', age=60),
    '27017': scrape_category.Simfile(simfileid='27017', name='You Baby', age=31622400),
    '26969': scrape_category.Simfile(simfileid='26969', name='Dai Yan Ren', age=1451520),
    '27069': scrape_category.Simfile(simfileid='27069', name='Cruise', age=26784000)
}

EXPECTED_FILTERED = {
    '26965': scrape_category.Simfile(simfileid='26965', name="Don't Sleep in the Subway", age=138240),
    '26969': scrape_category.Simfile(simfileid='26969', name='Dai Yan Ren', age=1451520)
}

EXPECTED_FIVE_MINUTES = {
    '27015': scrape_category.Simfile(simfileid='27015', name='Ai Qing Fu Xing', age=60)
}

EXPECTED_ONE_WEEK = {
    '27015': scrape_category.Simfile(simfileid='27015', name='Ai Qing Fu Xing', age=60),
    '27255': scrape_category.Simfile(simfileid='27255', name='Xingfu de Ditu', age=18000),
    '26965': scrape_category.Simfile(simfileid='26965', name="Don't Sleep in the Subway", age=138240)
}

def compare_simfile_records(results, expected):
    # could just assert simfiles == expected, but want to easily
    # identify the missing item if something is missing
    assert len(results) == len(expected)
    for i in expected:
        assert i in results
        assert results[i] == expected[i], "Expected {} got {}".format(expected[i], results[i])


class TestScrapeCategory(unittest.TestCase):
    CATEGORY_URL = "file:///" + MODULE_DIR + "/test/%s.html"

    def test_scrape(self):
        """
        Scrape the test category, verify the results
        """
        simfiles = scrape_category.get_category_from_ziv("category_test", self.CATEGORY_URL)
        compare_simfile_records(simfiles, EXPECTED_SIMFILES)

class TestUtilityMethods(unittest.TestCase):
    def test_parse_age(self):
        expected_results = [
            ("1 hour ago", 3600),
            ("10 seconds ago", 10),
            ("2 days ago", 172800),
            ("1 week ago", 604800)
        ]
        for text, age in expected_results:
            assert age == scrape_category.parse_age(text)

    def test_get_content(self):
        content_url = "file:///" + MODULE_DIR + "/test/small_content.txt"
        content = scrape_category.get_content(content_url, split=True)
        assert content == ["foo", "bar"]
        content = scrape_category.get_content(content_url, split=False)
        assert content == "foo\nbar"
    
    def test_filter_prefix(self):
        filtered = scrape_category.filter_simfiles_prefix(EXPECTED_SIMFILES, "D")
        compare_simfile_records(filtered, EXPECTED_FILTERED)

    def test_filter_since(self):
        filtered = scrape_category.filter_simfiles_since(EXPECTED_SIMFILES, "5 minutes ago")
        compare_simfile_records(filtered, EXPECTED_FIVE_MINUTES)
        filtered = scrape_category.filter_simfiles_since(EXPECTED_SIMFILES, "1 week ago")
        compare_simfile_records(filtered, EXPECTED_ONE_WEEK)

class TestScrapeHomepage(unittest.TestCase):
    PLATFORMS_URL = "file:///" + MODULE_DIR + "/test/simfile_homepage.html"

    def test_get_platforms(self):
        platforms = scrape_category.scrape_platforms(self.PLATFORMS_URL)

        expected_platforms = set(["Arcade", "PlayStation 2", "PlayStation 3",
                                  "Wii", "GameCube", "Xbox", "Xbox 360",
                                  "Mobile", "User"])

        assert set(platforms.keys()) == expected_platforms
        assert len(platforms['Arcade']) == 32
        expected_category_name = "Dance Dance Revolution (AC) (Japan)"
        assert expected_category_name in platforms['Arcade']
        assert platforms['Arcade'][expected_category_name] == "37"

    def test_cached_platforms(self):
        cache_dir = tempfile.mkdtemp()
        platforms = scrape_category.scrape_platforms(self.PLATFORMS_URL)
        try:
            # test the case of needing to create the cache
            assert len(glob.glob("%s/*" % cache_dir)) == 0
            cached_platforms = scrape_category.cached_scrape_platforms(self.PLATFORMS_URL, cache_dir=cache_dir)
            assert platforms == cached_platforms
            cache_files = glob.glob("%s/*" % cache_dir)
            assert len(cache_files) == 1
            cache_file = cache_files[0]

            original_time = os.path.getmtime(cache_file)

            # test using the cache
            # the file should not be changed
            time.sleep(0.02)
            cached_platforms = scrape_category.cached_scrape_platforms(self.PLATFORMS_URL, cache_dir=cache_dir)
            assert platforms == cached_platforms
            assert len(glob.glob("%s/*" % cache_dir)) == 1
            cache_time = os.path.getmtime(cache_file)
            assert original_time == cache_time

            # test the "force" option - check that the new mod time is
            # later than the previous mod time
            time.sleep(0.02)
            cached_platforms = scrape_category.cached_scrape_platforms(self.PLATFORMS_URL, force=True, cache_dir=cache_dir)
            assert platforms == cached_platforms
            assert len(glob.glob("%s/*" % cache_dir)) == 1
            force_time = os.path.getmtime(cache_file)
            assert force_time > original_time
        finally:
            shutil.rmtree(cache_dir)


if __name__ == '__main__':
    unittest.main()
