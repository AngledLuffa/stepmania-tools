import glob
import os
import shutil
import tempfile
import time
import unittest
import zipfile

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

EXPECTED_REGEX = {
    '27069': scrape_category.Simfile(simfileid='27069', name='Cruise', age=26784000)
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

class TestFileLinks(unittest.TestCase):
    SIMFILE_URL = "file:///" + MODULE_DIR + "/test/simfile_%s.html"
    SIMFILE_OWNER_URL = "file:///" + MODULE_DIR + "/test/simfile_owner_%s.html"

    def test_file_link(self):
        link = scrape_category.get_file_link_from_ziv("29051", url=self.SIMFILE_URL)
        expected_link = "http://zenius-i-vanisher.com/v5.2/download.php?type=ddrsimfilecustom&simfileid=29051"
        assert link == expected_link

    def test_file_link_as_owner(self):
        link = scrape_category.get_file_link_from_ziv("29051", url=self.SIMFILE_OWNER_URL)
        expected_link = "http://zenius-i-vanisher.com/v5.2/download.php?type=ddrsimfilecustom&simfileid=29051"
        assert link == expected_link

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

    def test_filter_regex(self):
        filtered = scrape_category.filter_simfiles_regex(EXPECTED_SIMFILES, ".*rui.*")
        compare_simfile_records(filtered, EXPECTED_REGEX)
        
    def test_filter_since(self):
        filtered = scrape_category.filter_simfiles_since(EXPECTED_SIMFILES, "5 minutes ago")
        compare_simfile_records(filtered, EXPECTED_FIVE_MINUTES)
        filtered = scrape_category.filter_simfiles_since(EXPECTED_SIMFILES, "1 week ago")
        compare_simfile_records(filtered, EXPECTED_ONE_WEEK)

    def test_filter_mac_files(self):
        names = ["foo", "bar", "__MAC_blah", "foo/__MAC_bar"]
        expected_names = ["foo", "bar"]
        result = scrape_category.filter_mac_files(names)
        assert result == expected_names


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


class TestAlreadyDownloaded(unittest.TestCase):
    def touch(self, dest, filename):
        with open(os.path.join(dest, filename), "w"):
            pass

    def setUp(self):
        self.dest = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dest)

    def test_already_downloaded(self):
        simfile = scrape_category.Simfile(simfileid='27069',
                                          name='Cruise',
                                          age=26784000)
        self.touch(self.dest, 'Cruise')
        assert scrape_category.simfile_already_downloaded(simfile, self.dest)
        
    def test_already_downloaded_sanitize(self):
        simfile = scrape_category.Simfile(simfileid='27069',
                                          name='Cruise.',
                                          age=26784000)
        self.touch(self.dest, 'Cruise')
        assert scrape_category.simfile_already_downloaded(simfile, self.dest)

    def test_already_downloaded_zipfile(self):
        simfile = scrape_category.Simfile(simfileid='27069',
                                          name='Cruise.',
                                          age=26784000)
        self.touch(self.dest, 'sim27069.zip')
        assert scrape_category.simfile_already_downloaded(simfile, self.dest)

    def test_not_downloaded(self):
        simfile = scrape_category.Simfile(simfileid='27069',
                                          name='Cruise.',
                                          age=26784000)
        assert not scrape_category.simfile_already_downloaded(simfile, self.dest)

class TestDirectoryStructure(unittest.TestCase):
    def get_valid(self, filename):
        filename = os.path.join(MODULE_DIR, "test/zips", filename)
        with zipfile.ZipFile(filename) as zfile:
            return scrape_category.valid_directory_structure(zfile)

    def get_flat(self, filename):
        filename = os.path.join(MODULE_DIR, "test/zips", filename)
        with zipfile.ZipFile(filename) as zfile:
            return scrape_category.flat_directory_structure(zfile)

    def get_directory(self, filename):
        filename = os.path.join(MODULE_DIR, "test/zips", filename)
        with zipfile.ZipFile(filename) as zfile:
            return scrape_category.get_directory(zfile)

    def test_valid_directory_structure(self):
        # Looks like most simfiles
        assert self.get_valid("good_basic.zip")
        # Simfile directory not explicitely given, but still good
        assert self.get_valid("good_onefile.zip")
        # Zipped with the special mac files included
        # Those files should be ignored
        assert self.get_valid("good_macfile.zip")
        # Should be good even though there is an inner directory
        assert self.get_valid("good_innerdirectory.zip")
        # Should be good - name has a space
        assert self.get_valid("good_spaces.zip")
        # One file, no directory
        assert self.get_valid("good_spaces_onefile.zip")
        # Has a " in the name
        # We test later that it gets removed in various places
        assert self.get_valid("good_illegal_char.zip")

        # bad because an extra file at the top level
        assert not self.get_valid("bad_toplevel.zip")
        # bad because two directories
        assert not self.get_valid("bad_twodirectories.zip")
        # empty zips are not usable
        assert not self.get_valid("bad_empty.zip")

        # flat, but not considered 'valid'
        assert not self.get_valid("flat_simfile.zip")

    def test_flat_directory_structure(self):
        assert not self.get_flat("good_basic.zip")
        assert not self.get_flat("good_onefile.zip")
        assert not self.get_flat("good_macfile.zip")
        assert not self.get_flat("good_innerdirectory.zip")
        assert not self.get_flat("good_spaces.zip")
        assert not self.get_flat("good_spaces_onefile.zip")
        assert not self.get_flat("good_illegal_char.zip")
        assert not self.get_flat("bad_toplevel.zip")
        assert not self.get_flat("bad_twodirectories.zip")
        assert not self.get_flat("bad_empty.zip")

        assert self.get_flat("flat_simfile.zip")

    def test_get_directory(self):
        assert "foo" == self.get_directory("good_basic.zip")
        assert "foo" == self.get_directory("good_onefile.zip")
        assert "foo" == self.get_directory("good_macfile.zip")
        assert "foo" == self.get_directory("good_innerdirectory.zip")
        assert "foo" == self.get_directory("good_spaces.zip")
        assert "foo" == self.get_directory("good_spaces_onefile.zip")
        assert "foo" == self.get_directory("good_illegal_char.zip")

class TestExtract(unittest.TestCase):
    def setUp(self):
        self.dest = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dest)

    def check_results(self, expected_files, inner_directory, temp_filename):
        expected_inner_dirs = set([os.path.join(self.dest, inner_directory),
                                   temp_filename])
        created_inner_dirs = set(glob.glob("%s/*" % self.dest))
        assert created_inner_dirs == expected_inner_dirs

        expected_inner_files = set([
            os.path.join(self.dest, inner_directory, expected_file)
            for expected_file in expected_files
        ])
        created_inner_files = set(glob.glob("%s/*/*" % self.dest))
        assert created_inner_files == expected_inner_files

    def copy_test_simfile(self, filename, copy_to=None):
        original_filename = os.path.join(MODULE_DIR, "test/zips", filename)
        if copy_to is None:
            copy_to = filename
        temp_filename = os.path.join(self.dest, copy_to)
        shutil.copyfile(original_filename, temp_filename)
        return temp_filename

    def run_zip_test(self, filename, expected_files,
                     inner_directory=None):
        temp_filename = self.copy_test_simfile(filename)

        with zipfile.ZipFile(temp_filename) as simzip:
            if not inner_directory:
                inner_directory = scrape_category.get_directory(simzip)
            scrape_category.extract_zip(simzip, self.dest, inner_directory)
            self.check_results(expected_files, inner_directory, temp_filename)

    def run_simfile_test(self, filename, expected_files):
        temp_filename = self.copy_test_simfile(filename, copy_to="sim100.zip")
        simfile_name = "Bar"

        simfile = scrape_category.Simfile("100", simfile_name, 1000)
        scrape_category.extract_simfile(simfile, self.dest)

        with zipfile.ZipFile(temp_filename) as simzip:
            if scrape_category.flat_directory_structure(simzip):
                inner_directory = simfile_name
            else:
                inner_directory = "foo"

        self.check_results(expected_files, inner_directory, temp_filename)

    def test_extract_zip_spaces(self):
        self.run_zip_test("good_spaces.zip", ["foo.sm"])

    def test_extract_zip_flat(self):
        self.run_zip_test("flat_simfile.zip", ["foo.txt", "bar.txt"],
                          inner_directory="foo")

    def test_extract_zip_illegal_char(self):
        self.run_zip_test("good_illegal_char.zip", ["foo.sm"])

    def test_extract_simfile_spaces(self):
        self.run_simfile_test("good_spaces.zip", ["foo.sm"])

    def test_extract_simfile_flat(self):
        self.run_simfile_test("flat_simfile.zip", ["foo.txt", "bar.txt"])

    def test_extract_simfile_illegal_char(self):
        self.run_simfile_test("good_illegal_char.zip", ["foo.sm"])

# TODO test:
# get_simfile_from_ziv (add a fake .zip to our test directory, "download" it)
# sanitize_name
# unlink_zip
# log files:
#   get_log_filename
#   renaming_message
#   log_renaming_message
#   get_logged_titles - this may need renaming anyway
# the whole thing:
#   download_simfile - would require passing in local URLs
#   download_simfiles
#   download_category
# get_filtered_titles_from_ziv


if __name__ == '__main__':
    unittest.main()
