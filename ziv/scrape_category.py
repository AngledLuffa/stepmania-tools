"""
Downloads a category of simfiles from ZiV.  The default is to
download the current week of the summer 2016 contest (as of
2016-12-19) to the current directory.

If you are reading this on github and looking for a way to download
the script, look for the button labeled "Raw" to the upper right.
Download to the directory where you want the simfiles downloaded.
You will need Python installed.  www.python.org
The program is compatible with 3.6.  Python 2 has not been tested.

Run with no arguments to download those files to the current directory.

Run with --help for more help.

If you can't easily add command line arguments (such as running by
double clicking in Windows), you can change the current week
downloaded by editing the line
CURRENT_WEEK = "..."

If you want to download a different category, there is a line below
with "--category" in it.  In that line, change the number after
"default" to the number of the category you want to download.
Make sure to keep the quotes, as in "899".  You will need to change
CURRENT_WEEK=""
to get that to work.

Unforunately, private categories are currently not supported,
as they would require logging in.
"""

# Copyright 2016 by John Bauer
# Distributed under the Apache License 2.0

# TO THE EXTENT PERMITTED BY LAW, THE SOFTWARE IS PROVIDED "AS IS",
# WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE, TITLE AND NON-INFRINGEMENT. IN NO EVENT SHALL
# THE COPYRIGHT HOLDERS OR ANYONE DISTRIBUTING THE SOFTWARE BE LIABLE
# FOR ANY DAMAGES OR OTHER LIABILITY, WHETHER IN CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import argparse
import codecs
import datetime
import os
import re
import sys
import time
import zipfile
from collections import namedtuple, OrderedDict

# python 2.7/3.6 compatability
try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen

try:
    from HTMLParser import HTMLParser
except ImportError:
    from html.parser import HTMLParser


CURRENT_WEEK = "[Round B]"
DEFAULT_CATEGORY = "957"

Simfile = namedtuple("Simfile", "simfileid name age")

AGE_PATTERN = re.compile('^([0-9.]+) (second|minute|hour|day|week|month|year)s? ago$')

AGE_INTERVALS = {
    'second' : 1,
    'minute' : 60,
    'hour' : 60 * 60,
    'day' : 60 * 60 * 24,
    'week' : 60 * 60 * 24 * 7,
    'month' : 60 * 60 * 24 * 31,
    'year' : 60 * 60 * 24 * 366
}

def parse_age(age):
    """
    Turn a z-i-v age string to a number of seconds since update.

    Goal is to overestimate, since this will be used to prescreen
    files we don't need to download when looking for newer files.
    """
    match = AGE_PATTERN.match(age.strip())
    if not match:
        raise RuntimeError("Cannot process '%s' as a simfile age" % age)
    length = float(match.groups()[0])
    interval = match.groups()[1]
    if interval not in AGE_INTERVALS:
        raise RuntimeError("Unknown interval '%s' extracted from '%s'" %
                           (interval, age))
    return int(length * AGE_INTERVALS[interval])


def parse_update_threshold(since):
    if AGE_PATTERN.match(since):
        age = parse_age(since)
        return time.time() - age
    raise RuntimeError("Unable to parse '%s'" % since)


def filter_simfiles_since(simfiles, since):
    now = time.time()
    last_update_threshold = parse_update_threshold(since)
    print("Only downloading files more recent than %s" % datetime.datetime.fromtimestamp(last_update_threshold))
    filtered = {}
    for x in simfiles:
        if now - simfiles[x].age > last_update_threshold:
            filtered[x] = simfiles[x]
    return filtered


class CategoryHTMLParser(HTMLParser):
    """
    This class parses a Category page from ziv

    For example:
    http://zenius-i-vanisher.com/v5.2/viewsimfilecategory.php?categoryid=934

    It looks for the first table in the webpage, then extracts the
    song ids and names from that table.

    TODO: An HTML parser that builds an object tree might be easier to
    work with, since we know exactly what format we are working with,
    but for now this is effective.  One disadvantage of looking for
    such a tree is there might not be one in the standard Python
    library, which would make it harder for other people to use.
    """
    def __init__(self):
        HTMLParser.__init__(self)
        self.simfiles = {}

        self.simfileid = None
        self.title = None
        self.age = None

        self.in_table = False
        self.tr_count = 0
        self.in_title = False

        self.in_age = False

    def handle_starttag(self, tag, attrs):
        if not self.in_table and tag == 'table':
            # simfile information on ziv is in a table
            # note that some pages can have multiple tables with songs
            # there is also a table at the bottom with server stats
            # currently we are trying to distinguish that by looking
            # at the class attr
            for k, v in attrs:
                if k == 'class' and v == 'noborder':
                    return
            self.in_table = True
            return

        if not self.in_table:
            return

        if tag == 'tr':
            self.tr_count = self.tr_count + 1
            return

        if self.tr_count < 3:
            # the first two rows of the first table are headers
            return

        # we know we are in the table with the songs
        # we have seen two rows
        # now we are looking for the name and id of the next simfile

        if self.simfileid is None and tag == 'a':
            for attr in attrs:
                if attr[0] == "name" or attr[0] == "id":
                    self.simfileid = attr[1][3:]
            if self.simfileid is None:
                raise RuntimeError("Link does not have name: {}".format(attrs))
            self.in_title = True
        elif self.simfileid is not None and self.age is None and tag == 'td':
            self.in_age = True

    def handle_data(self, data):
        if self.in_title:
            if self.title is None:
                self.title = data
            else:
                # z-i-v doesn't properly write &amp; so we assume
                # the data is split on &
                self.title = self.title + "&" + data
        elif self.in_age:
            # "age" table cells don't seem to contain &
            self.age = data

    def handle_endtag(self, tag):
        if self.in_title:
            assert tag == "a"
            self.in_title = False

        if self.in_age and tag == 'td':
            self.in_age = False

        if self.in_table and tag == 'tr' and self.simfileid is not None:
            # finished a row
            assert self.title is not None
            assert not self.in_title
            assert not self.in_age
            self.simfiles[self.simfileid] = Simfile(self.simfileid, self.title, parse_age(self.age))
            self.simfileid = None
            self.title = None
            self.age = None

        if self.in_table and tag == 'table':
            self.in_table = False

    #def feed(self, data):
    #    HTMLParser.feed(self, data)


class SimfileHomepageHTMLParser(HTMLParser):
    """
    Downloads the simfiles platforms/categories page.

    Results are kept in a member variable in the format
    OrderedDict platform -> categories for that platform
      OrderedDict category -> category id
    """
    def __init__(self):
        HTMLParser.__init__(self)
        self.platforms = OrderedDict()

        self.in_platforms = False
        self.in_new_platform = False
        self.finished_platforms = False
        self.category_name = ""
        self.category_index = "0"

    def handle_starttag(self, tag, attrs):
        # Each new platform is its own <tr>
        # The categories are listed as options in a menu
        if self.in_platforms and tag == 'tr':
            self.in_new_platform = True
            self.platform_name = ""

        if self.in_platforms and tag == 'option':
            value_attrs = [x[1] for x in attrs if x[0] == 'value']
            if len(value_attrs) < 1:
                raise RuntimeError("Found an option with no value")
            self.category_index = value_attrs[0].strip()

    def handle_data(self, data):
        # The word "Platform" shows up once at the start of
        # the table with the information we actually care about
        if data == 'Platform':
            if self.in_platforms or self.finished_platforms:
                raise RuntimeError("Found two Platform sections")
            self.in_platforms = True
            return

        if self.in_new_platform:
            # The text immediately after <tr> is the name of the
            # platform, eg Arcade, etc
            self.platform_name = self.platform_name + data
            return

        if self.in_platforms:
            # All other relevant text is the name of the category
            self.category_name = self.category_name + data


    def handle_endtag(self, tag):
        if not self.in_platforms:
            return

        if tag == 'td' and self.in_new_platform:
            # When reading the name of a new platform, the </td> tells
            # us when its name is finished
            self.in_new_platform = False
            self.platform_name = self.platform_name.strip()
            self.platforms[self.platform_name] = OrderedDict()

        if tag == 'option':
            if self.category_index != '0':
                # Category 0 is the dummy label given for
                # "Select Simfile Category"
                self.category_name = self.category_name.strip()
                self.platforms[self.platform_name][self.category_name] = self.category_index
            self.category_index = '0'
            self.category_name = ""

        if tag == 'table':
            self.in_platforms = False
            self.finished_platforms = True

class DownloadHTMLParser(HTMLParser):
    """
    Parses individual *lines*, not pages
    Extracts a simfile link and download size from a line

    The expectation is that the format will look like

    <tr><td class="border">ZIP</td><td class="border"><a href="download.php?type=ddrsimfile&amp;simfileid=29051">ZIP</a> (63.29MB) <span style="color: gray">6.1 months ago</span></td></tr>

    Possibly there will be some links for owner commands in the first
    <td>, such as a delete command.

    TODO: it might be better to parse the whole webpage, since the
    user might have put the word ZIP in their description, for
    example.
    """
    def __init__(self):
        HTMLParser.__init__(self)
        self.link = None
        self.size = None

        self._saw_end_td = False

    def handle_starttag(self, tag, attrs):
        if not self._saw_end_td:
            # The first <td> may contain owner commands,
            # which we want to ignore
            return
        
        if tag != "a":
            return

        if self.link is not None:
            raise RuntimeError("Found more than one anchor!")

        for attr in attrs:
            if attr[0] == "href":
                self.link = attr[1]

        if "download.php" not in self.link:
            raise RuntimeError("Found a link that points to an unexpected URL: {}".format(self.link))
                
        if self.link is None:
            raise RuntimeError("Found a link with no href: {}".format(attrs))

    def handle_endtag(self, tag):
        if tag == 'td':
            self._saw_end_td = True
        
    def handle_data(self, data):
        if "MB" not in data:
            return

        if self.size is not None:
            raise RuntimeError("Found more than one size")
        data = data.strip()[1:-3]
        self.size = float(data) * 1024 * 1024


def get_content(url, split=True, force_decode=False):
    """
    Opens the URL, downloads the page.

    Respects encoding if possible.
    If split=True, splits the page on newlines.
    """
    connection = urlopen(url)
    try:
        encoding = connection.headers.get_charset()
    except AttributeError:
        encoding = connection.headers.getparam('charset')
    if encoding is not None:
        content = connection.read().decode(encoding)
    else:
        content = connection.read()
        if force_decode:
            content = content.decode('utf-8')
    connection.close()

    if split:
        content = content.split("\n")

    return content


ZIV_SIMFILE_CATEGORIES = "https://zenius-i-vanisher.com/v5.2/simfiles.php?category=simfiles"

def scrape_platforms(url=ZIV_SIMFILE_CATEGORIES):
    """
    Returns a map from platform to list of categories for that platform.

    The url can be set to read from z-i-v or from a unit test file.
    """
    print("Downloading simfiles home page from:")
    print(url)

    content = get_content(url, split=False, force_decode=True)
    parser = SimfileHomepageHTMLParser()
    parser.feed(content)
    return parser.platforms


def cached_scrape_platforms(url=ZIV_SIMFILE_CATEGORIES,
                            force=False, cache_dir=None):
    """
    Reads & writes the platform list to cached.pkl in the module directory.

    If cached.pkl doesn't exist, it gets created here.
    """
    if cache_dir is None:
        cache_dir = os.path.split(__file__)[0]
    cache_file = os.path.join(cache_dir, "cached.pkl")

    if os.path.exists(cache_file):
        if force:
            os.remove(cache_file)
        else:
            try:
                with open(cache_file, 'rb') as fin:
                    platform_map = pickle.load(fin)
            except (OSError, IOError):
                print("Unable to load cached file, ignoring")
            if isinstance(platform_map, OrderedDict):
                return platform_map

    platform_map = scrape_platforms(url)
    # if anything goes wrong, make a best effort attempt to clean up a
    # partially written cached.pkl
    try:
        with open(cache_file, "wb") as fout:
            pickle.dump(platform_map, fout)
    except:
        try:
            os.remove(cache_file)
        except (OSError, IOError):
            pass
        raise
    return platform_map


ZIV_CATEGORY = "http://zenius-i-vanisher.com/v5.2/viewsimfilecategory.php?categoryid=%s"

def get_category_from_ziv(category, url=ZIV_CATEGORY):
    """
    Returns a list of files in the category.

    The result is a list of Simfile tuples: simfile id, name.

    Passing in the base url for the category is useful to test
    from a local file.
    """
    url = url % category

    print("Downloading category from:")
    print(url)

    content = get_content(url, split=False, force_decode=True)
    parser = CategoryHTMLParser()
    parser.feed(content)
    results = parser.simfiles

    print("Found %d simfiles" % len(results))

    return results


ZIV_SIMFILE = "http://zenius-i-vanisher.com/v5.2/viewsimfile.php?simfileid=%s"

def get_file_link_from_ziv(simfileid, url=ZIV_SIMFILE):
    """
    Gets the page for this particular simfile, extracts the link to
    the largest zip file on that link
    """
    url = url % simfileid
    content = get_content(url, split=True, force_decode=True)
    zip_lines = [x for x in content if "ZIP" in x]

    results = []
    for i in zip_lines:
        parser = DownloadHTMLParser()
        parser.feed(i)
        if parser.link is not None:
            results.append((parser.link, parser.size))

    # sort by size, so we download the largest and presumably the most
    # interesting
    results.sort()
    link = results[-1][0]
    link = "http://zenius-i-vanisher.com/v5.2/%s" % link
    return link


def filter_simfiles_prefix(simfiles, prefix):
    """
    Given a map of simfile objects, only keep those which start with prefix
    """
    filtered = {}
    for x in simfiles.keys():
        if simfiles[x].name.startswith(prefix):
            filtered[x] = simfiles[x]
    return filtered


def filter_simfiles_regex(simfiles, regex):
    """
    Given a map of simfile objects, only keep those which match the regex
    """
    pattern = re.compile(regex)
    filtered = {}
    for x in simfiles.keys():
        if pattern.match(simfiles[x].name):
            filtered[x] = simfiles[x]
    return filtered


def simfile_already_downloaded(simfile, dest, check_zip=True, verbose=True):
    filename = os.path.join(dest, simfile.name)
    if os.path.exists(filename):
        if verbose:
            print('Directory already exists: "%s"' % filename)
        return True

    filename = os.path.join(dest, sanitize_name(simfile.name))
    if os.path.exists(filename):
        if verbose:
            print('Directory already exists: "%s"' % filename)
        return True

    if check_zip:
        filename = os.path.join(dest, "sim%s.zip" % simfile.simfileid)
        if os.path.exists(filename):
            if verbose:
                print("Zip file already exists: %s" % filename)
            return True

    return False


def valid_zipfile_directory_structure(filename):
    """
    Open the given file, then check its directory structure.

    Useful for testing from the interpreter or command line, for
    example, as you can pass in a filename instead of opening the zip
    yourself.
    """
    simzip = None
    try:
        simzip = zipfile.ZipFile(filename)
        result = valid_directory_structure(simzip=simzip)
        simzip.close()
        return result
    except (zipfile.BadZipfile, IOError):
        return False
    finally:
        if simzip != None:
            simzip.close()


def valid_directory_structure(simzip):
    names = filter_mac_files(simzip.namelist())
    if len(names) == 0:
        return False
    # In most cases, a directory containing the files is zipped into
    # the archive.  However, that's not necessarily the case.  What
    # does happen, though, is that even the directories have a "/" in
    # them (they end with "/").  Therefore, what we can do is take the
    # first directory segment of the first filename.  If all the other
    # files share that name, then we have a valid directory structure.
    # TODO: this doesn't actually check for music files, simfiles, etc
    # in the first directory, but that's okay
    if any(x.find("/") < 0 for x in names):
        return False
    dirs = [x.split("/")[0] for x in names]
    dirs.sort(key=len)
    directory = dirs[0] + "/"
    # All files have to be in the same subdirectory directory.
    # Obviously the subdirectory itself satisfies startswith(itself)
    if any(not x.startswith(directory) for x in names):
        return False
    return True


def filter_mac_files(names):
    """
    Get rid of random system files from zips build on macs
    """
    return [x for x in names
            if not x.startswith("__MAC") and x.find("/__MAC") < 0]


def flat_directory_structure(simzip):
    """
    Returns True if the zip does not actually contain any directories,
    but is instead just a bunch of files.
    This isn't the way zips are supposed to be organized on z-i-v,
    but some people do submit zip files that way anyway, so it is
    good to compensate.
    """
    names = filter_mac_files(simzip.namelist())
    if len(names) == 0:
        return False
    for name in names:
        if name.find("/") >= 0:
            return False
    return True


def get_directory(simzip):
    """
    Assumes the directory structure inside the zip is valid,
    so it assumes there is exactly one directory and returns that.
    Eg, call valid_directory_structure before calling this function.
    """
    names = filter_mac_files(simzip.namelist())
    inner_directory = names[0].split("/")[0].strip()
    return sanitize_name(inner_directory)


def extract_zip(simzip, dest, inner_directory):
    """
    Unfortunately, some files have spaces at the end of their
    directory names, and on Windows that screws everything up.  This
    method fixes it by reading the files manually and writing them to
    the correct location.
    """
    inner_directory = sanitize_name(inner_directory)
    directory = os.path.join(dest, inner_directory)
    os.mkdir(directory)

    # skip files that have _MAC in them
    namelist = filter_mac_files(simzip.namelist())
    # sort so that we always create subdirectories first if needed
    namelist.sort(key=len)

    for name in namelist:
        path_pieces = [sanitize_name(x) for x in name.split("/")]
        if path_pieces[0] != inner_directory:
            # this can happen in the case of a file with no inner folder
            path_pieces = [inner_directory] + path_pieces
        path_pieces = [dest] + path_pieces
        path = os.path.join(*path_pieces)
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.mkdir(dirname)
        filename = os.path.basename(path)
        if not filename:
            continue
        data = simzip.read(name)
        new_name = os.path.join(directory, filename)
        fout = open(new_name, "wb")
        fout.write(data)
        fout.close()


def sanitize_name(name):
    """
    Remove ?*" to sanitize Windows filenames.

    TODO: there are a few other characters to remove on Windows
    """
    name = name.strip().replace("?", "").replace("*", "").replace('"', "")
    name = re.sub("[.]+", ".", name)
    name = re.sub("[.]$", ".", name)
    return name


def extract_simfile(simfile, dest):
    """
    Given an (id, name) tuple and the destination arg,
    extract the simfile to the appropriate location.

    Tries to compensate for a couple error cases.
    If the zipfile does not contain a folder, a folder is created
    with the simfile's name.
    If the simfile's name has trailing or leading spaces, this
    causes IOErrors on Windows, but that is also fixable.

    Return value is the directory extracted to.
    """
    filename = os.path.join(dest, "sim%s.zip" % simfile.simfileid)

    simzip = None
    extracted_directory = None
    try:
        simzip = zipfile.ZipFile(filename)
        if flat_directory_structure(simzip):
            # There is no inner directory, but we will treat the
            # directory we create as the location for the files
            extracted_directory = sanitize_name(simfile.name)
            extract_zip(simzip, dest, extracted_directory)
        elif not valid_directory_structure(simzip):
            print("Invalid directory structure in %s" % filename)
        else:
            # This will check for spaces at the start or end of the
            # filenames, which are not okay in Windows
            # Another reason we can't use extractall because we want
            # to eliminate files such as _MACOSX
            extracted_directory = get_directory(simzip)
            extracted_directory = sanitize_name(extracted_directory)
            extract_zip(simzip, dest, extracted_directory)
    except (zipfile.BadZipfile, IOError, WindowsError):
        print("Unable to extract %s" % filename)
        if (extracted_directory is not None and
            os.path.exists(extracted_directory)):
            print("Warning: there may be a partial download in %s" % extracted_directory)
            # return None so the caller doesn't clean up the .zip
            extracted_directory = None
    if simzip is not None:
        simzip.close()

    return extracted_directory


def get_simfile_from_ziv(simfile, link, dest):
    filename = os.path.join(dest, "sim%s.zip" % simfile.simfileid)
    print('Downloading "%s" from %s to %s' % (simfile.name, link, filename))
    content = get_content(link, split=False)
    fout = open(filename, "wb")
    fout.write(content)
    fout.close()


def unlink_zip(simfile, dest):
    """
    If we successfully download and extract a zip, we will probably
    want to clean up after ourselves
    """
    filename = os.path.join(dest, "sim%s.zip" % simfile.simfileid)
    os.unlink(filename)


LOG_PATTERN = re.compile('^(.*) extracted to "(.*)" instead of "(.*)"$')

def get_log_filename(dest):
    return os.path.join(dest, "download_log.txt")

def renaming_message(simfile, actual):
    return '%s extracted to "%s" instead of "%s"' % (simfile.simfileid, actual, simfile.name)

def log_renaming_message(simfile, actual, dest):
    message = renaming_message(simfile, actual)
    log_filename = get_log_filename(dest)
    with codecs.open(log_filename, "a", encoding="utf-8") as fout:
        fout.write(message)
        fout.write("\n")
        fout.close()


def update_records_from_log(records, dest):
    log_filename = get_log_filename(dest)
    updated = records.copy()
    if not os.path.exists(log_filename):
        return updated
    with codecs.open(log_filename, encoding="utf-8") as fin:
        for line in fin.readlines():
            match = LOG_PATTERN.match(line.strip())
            if not match:
                continue
            simfileid = match.groups()[0]
            name = match.groups()[1]
            if simfileid not in records:
                continue
            updated[simfileid] = records[simfileid]._replace(name=name)
    return updated


def build_argparser():
    argparser = argparse.ArgumentParser(description='Download an entire category from z-i-v.  The default arguments download the %s week of the summer 2016 contest.  All you need to do to download that week is run the python script in the directory you want to have the simfiles.  The prefix argument lets you set a prefix, such as a different week of the contest, and the dest argument lets you specify a different directory to store the files.' % CURRENT_WEEK)
    argparser.add_argument("--category",
                           default="{}".format(DEFAULT_CATEGORY),
                           help="Which category number to download")
    argparser.add_argument("--prefix", default=CURRENT_WEEK,
                           help="Only download files with this prefix.  Default %s" % CURRENT_WEEK)
    argparser.add_argument("--regex", default="",
                           help="Only download files which match this regex.")
    argparser.add_argument("--dest", default="",
                           help="Where to put the simfiles.  Defaults to CWD")

    argparser.add_argument("--extract", dest="extract",
                           action="store_true",
                           help="Extract the zip files")
    argparser.add_argument("--no-extract", dest="extract",
                           action="store_false",
                           help="Don't extract the zip files")
    argparser.set_defaults(extract=True)

    argparser.add_argument("--tidy", dest="tidy", action="store_true",
                           help="Delete zip files after extracting")
    argparser.add_argument("--no-tidy", dest="tidy", action="store_false",
                           help="Don't delete zip files after extracting")
    argparser.set_defaults(tidy=True)

    argparser.add_argument("--use-logfile", dest="use_logfile",
                           action="store_true",
                           help="Use download_log.txt to record where downloads are unzipped")
    argparser.add_argument("--no-use-logfile", dest="use_logfile",
                           action="store_false",
                           help="Don't use download_log.txt")
    argparser.set_defaults(use_logfile=True)

    argparser.add_argument("--since", default="",
                           help="Only download files updated since this date.  Setting this argument will re-download existing simfiles.")

    return argparser


def download_simfile(simfile, dest, tidy, use_logfile, extract, link=None):
    """
    Given a single simfile record, download that simfile to the dest directory.
    """
    if link is None:
        link = get_file_link_from_ziv(simfile.simfileid)
    get_simfile_from_ziv(simfile, link, dest)
    if extract:
        extracted_directory = extract_simfile(simfile, dest)
        if (extracted_directory is not None and
            extracted_directory != simfile.name):
            if use_logfile:
                # If we aren't using the logfile, there will be no
                # record of where the file goes, so we can't update
                # the location and then delete the zip
                log_renaming_message(simfile, extracted_directory, dest)
                simfile = simfile._replace(name=extracted_directory)
        # If we were asked to clean up after ourselves, verify that
        # everything went right, and if so, delete the zip
        if (tidy and simfile_already_downloaded(simfile, dest,
                                                check_zip=False,
                                                verbose=False)):
            unlink_zip(simfile, dest)


def download_simfiles(records, dest, tidy, use_logfile, extract):
    """
    Downloads the simfiles and returns how many zips were actually downloaded.

    records : map from ziv id to Simfile
    dest : directory to send the simfiles (and logs)
    tidy : clean up zips if the simfiles are successfully extracted
    use_logfile : write a log to that directory
    """
    count = 0
    for simfile in records.values():
        if not simfile_already_downloaded(simfile, dest):
            download_simfile(simfile, dest, tidy, use_logfile, extract)
            count = count + 1
    return count


def get_filtered_records_from_ziv(category, dest,
                                  prefix, regex, since, use_logfile):
    records = get_category_from_ziv(category)
    if prefix:
        records = filter_simfiles_prefix(records, prefix)
        print("%d simfiles matched prefix" % len(records))

    if regex:
        records = filter_simfiles_regex(records, regex)
        print("%d simfiles matched regex" % len(records))

    if since:
        since = since.strip()
    if since:
        records = filter_simfiles_since(records, since)
        print("%d simfiles matched date" % len(records))

    if use_logfile:
        records = update_records_from_log(records, dest)
    return records


def download_category(category, dest,
                      prefix="",
                      regex="",
                      since="",
                      use_logfile=True,
                      extract=True,
                      tidy=True):
    records = get_filtered_records_from_ziv(category=category,
                                            dest=dest,
                                            prefix=prefix,
                                            regex=regex,
                                            since=since,
                                            use_logfile=use_logfile)

    count = download_simfiles(records=records,
                              dest=dest,
                              tidy=tidy,
                              use_logfile=use_logfile,
                              extract=extract)
    print("Downloaded %d simfiles" % count)


def main():
    # If a file doesn't have an inner folder, such as 29303,
    # we extract the zip to the correct location.
    #
    # If a directory has trailing whitespace, such as 29308,
    # the files are extracted manually to the correct location.
    # ? and * also get removed.
    #
    # 30853 has consecutive . which also confuses Windows.
    #
    # Some files, such as 29437, extract to a different folder name
    # than the name given in the category.  We track those names in a
    # file named download_log.txt in the destination directory.
    # Tracking in the logfile can be turned off with --no-use-logfile
    #
    # Some files such as 29506 include mac-specific subdirectories.
    # Those get filtered when the zip is extracted.
    #
    # TODO: 
    # 29287 from Midspeed does not unzip correctly, zipfile.BadZipfile
    #
    # TODO features:
    # Added a --since flag, but --before would be nice too.
    # Add a --force option for date ranges
    # Add an option to look at the dates of the existing files and
    #   update newer ones
    # Search all directories for the files, in case you are
    #   rearranging the files after downloading?
    # Allow logging in
    #
    # TODO other stuff:
    # write unit tests
    # use the logging library
    try:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer)
    except AttributeError:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout)

    argparser = build_argparser()
    args = argparser.parse_args()

    download_category(category=args.category,
                      dest=args.dest,
                      prefix=args.prefix,
                      regex=args.regex,
                      since=args.since,
                      use_logfile=args.use_logfile,
                      extract=args.extract,
                      tidy=args.tidy)

if __name__ == "__main__":
    main()
