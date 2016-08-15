import argparse
import codecs
import os
import re
import sys
import urllib2
import zipfile
from collections import namedtuple
from HTMLParser import HTMLParser

Simfile = namedtuple("Simfile", "simfileid name")

# create a subclass and override the handler methods
class CategoryHTMLParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.simfileid = None
        self.title = None
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if self.simfileid is None and tag == 'a':
            for attr in attrs:
                if attr[0] == "name":
                    self.simfileid = attr[1][3:]
            if self.simfileid is None:
                raise RuntimeError("Link does not have name: {}".format(attrs))
            self.in_title = True

    def handle_data(self, data):
        if self.in_title:
            if self.title is None:
                self.title = data
            else:
                # z-i-v doesn't properly write &amp; so we assume
                # the data is split on &
                self.title = self.title + "&" + data

    def handle_endtag(self, tag):
        if self.in_title:
            assert tag == "a"
            self.in_title = False

    def feed(self, data):
        HTMLParser.feed(self, data)
        assert self.title is not None
        assert self.simfileid is not None

class DownloadHTMLParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.link = None
        self.size = None

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        if self.link is not None:
            raise RuntimeError("Found more than one anchor!")

        for attr in attrs:
            if attr[0] == "href":
                self.link = attr[1]

        if self.link is None:
            raise RuntimeError("Found a link with no href: {}".format(attrs))

    def handle_data(self, data):
        if "MB" not in data:
            return

        if self.size is not None:
            raise RuntimeError("Found more than one size")
        data = data.strip()[1:-3]
        self.size = float(data) * 1024 * 1024


def get_content(url, split=True):
    """
    Opens the URL, downloads the page.

    Respects encoding if possible.
    If split=True, splits the page on newlines.
    """
    connection = urllib2.urlopen(url)
    encoding = connection.headers.getparam('charset')
    if encoding is not None:
        content = connection.read().decode(encoding)
    else:
        content = connection.read()
    connection.close()

    if split:
        content = content.split("\n")

    return content


def get_category(category):
    """
    Returns a list of files in the category.

    The result is a list of Simfile tuples: simfile id, name.
    """
    url = "http://zenius-i-vanisher.com/v5.2/viewsimfilecategory.php?categoryid=%s" % category

    print "Downloading category from:"
    print url

    content = get_content(url)
    link_lines = [x for x in content if "viewsimfile.php?simfileid" in x]

    results = {}
    for i in link_lines:
        parser = CategoryHTMLParser()
        parser.feed(i)
        results[parser.simfileid] = Simfile(parser.simfileid, parser.title)

    print "Found %d simfiles" % len(results)

    return results


def get_file_link(simfileid):
    """
    Gets the page for this particular simfile, extracts the link to
    the largest zip file on that link
    """
    url = "http://zenius-i-vanisher.com/v5.2/viewsimfile.php?simfileid=%s" % simfileid

    content = get_content(url)
    zip_lines = [x for x in content if "ZIP" in x]

    results = []
    for i in zip_lines:
        parser = DownloadHTMLParser()
        parser.feed(i)
        results.append((parser.link, parser.size))

    # sort by size, so we download the largest and presumably the most
    # interesting
    results.sort()
    link = results[-1][0]
    link = "http://zenius-i-vanisher.com/v5.2/%s" % link
    return link


def filter_titles(titles, prefix):
    filtered = {}
    for x in titles.keys():
        if titles[x].name.startswith(prefix):
            filtered[x] = titles[x]
    return filtered


def simfile_already_downloaded(simfile, dest, check_zip=True, verbose=True):
    filename = os.path.join(dest, simfile.name)
    if os.path.exists(filename):
        if verbose:
            print "Directory already exists: %s" % filename
        return True

    filename = os.path.join(dest, simfile.name.strip())
    if os.path.exists(filename):
        if verbose:
            print "Directory already exists: %s" % filename
        return True

    if check_zip:
        filename = os.path.join(dest, "sim%s.zip" % simfile.simfileid)
        if os.path.exists(filename):
            if verbose:
                print "Zip file already exists: %s" % filename
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
    except (zipfile.BadZipfile, IOError) as e:
        return False
    finally:
        if simzip != None:
            simzip.close()


def valid_directory_structure(simzip):
    names = simzip.namelist()
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
    # Obviously the subdirectory itself with startswith(itself)
    if any(not x.startswith(directory) for x in names):
        return False
    return True


def flat_directory_structure(simzip):
    """
    Returns True if the zip does not actually contain any directories,
    but is instead just a bunch of files.
    This isn't the way zips are supposed to be organized on z-i-v,
    but some people do submit zip files that way anyway, so it is
    good to compensate.
    """
    names = simzip.namelist()
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
    names = simzip.namelist()
    return names[0].split("/")[0]


def extract_fixing_spaces(simzip, dest, inner_directory):
    """
    Unfortunately, some files have spaces at the end of their
    directory names, and on Windows that screws everything up.  This
    method fixes it by reading the files manually and writing them to
    the correct location.
    """
    inner_directory = inner_directory.strip()
    directory = os.path.join(dest, inner_directory)
    os.mkdir(directory)

    for name in simzip.namelist():
        filename = name.split("/")[1].strip()
        if not filename:
            continue
        data = simzip.read(name)
        new_name = os.path.join(directory, filename)
        fout = open(new_name, "wb")
        fout.write(data)
        fout.close()


def extract_simfile(simfile, dest):
    """
    Given an (id, name) tuple and the destination arg, extract
    the simfile to the appropriate location.

    Tries to compensate for a couple error cases.
    If the zipfile does not contain a folder, a folder is created
    with the simfile's name.
    If the simfile's name has trailing or leading spaces, this
    causes IOErrors on Windows, but that is also fixable.

    Return value is the directory extracted to.
    """
    filename = os.path.join(dest, "sim%s.zip" % simfile.simfileid)

    simzip = None
    try:
        simzip = zipfile.ZipFile(filename)
        if flat_directory_structure(simzip):
            # There is no inner directory, but we will treat the
            # directory we create as the location for the files
            extracted_directory = simfile.name.strip()
            dest_dir = os.path.join(dest, extracted_directory)
            simzip.extractall(dest_dir)
        elif not valid_directory_structure(simzip):
            print "Invalid directory structure in %s" % filename
        else:
            # Check for leading or trailing whitespace in the filename
            extracted_directory = get_directory(simzip)
            if extracted_directory != extracted_directory.strip():
                extract_fixing_spaces(simzip, dest, extracted_directory)
                extracted_directory = extracted_directory.strip()
            else:
                simzip.extractall()
    except (zipfile.BadZipfile, IOError) as e:
        print "Unable to extract %s" % filename
    if simzip is not None:
        simzip.close()

    return extracted_directory


def get_simfile(simfileid, link, dest, extract):
    filename = os.path.join(dest, "sim%s.zip" % simfileid)
    print "Downloading %s to %s" % (link, filename)
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


LOG_PATTERN = re.compile("^(.*) extracted to (.*) instead of (.*)$")

def get_log_filename(dest):
    return os.path.join(dest, "download_log.txt")

def renaming_message(simfile, actual):
    return "%s extracted to %s instead of %s" % (simfile.simfileid, actual, simfile.name)

def log_renaming_message(simfile, actual, dest):
    message = renaming_message(simfile, actual)
    log_filename = get_log_filename(dest)
    with open(log_filename, "a") as fout:
        fout.write(message)
        fout.write("\n")
        fout.close()


def get_logged_titles(titles, dest):
    log_filename = get_log_filename(dest)
    updated = titles.copy()
    if not os.path.exists(log_filename):
        return updated
    with open(log_filename) as fin:
        for line in fin.readlines():
            match = LOG_PATTERN.match(line.strip())
            if not match:
                continue
            simfileid = match.groups()[0]
            name = match.groups()[1]
            if simfileid not in titles:
                continue
            updated[simfileid] = Simfile(simfileid, name)
    return updated


if __name__ == "__main__":
    # If a file doesn't have an inner folder, such as 29303,
    # we extract the zip to the correct location.
    #
    # If a directory has trailing whitespace, such as 29308,
    # the files are extracted manually to the correct location.
    #
    # Some files, such as 29437, extract to a different folder name
    # than the name given in the category.  We track those names in a
    # file named download_log.txt in the destination directory.
    # TODO: add a flag for turning off that feature.
    #
    # TODO: 
    # 29287 from Midspeed does not unzip correctly, zipfile.BadZipfile
    #
    # TODO features:
    # Add a flag for dates to search for
    # Search all directories for the files, in case you are
    #   rearranging the files after downloading?
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout)

    argparser = argparse.ArgumentParser(description='Download an entire category from z-i-v.  The prefix argument lets you set a prefix, such as for one week worth of simfile contests.')
    argparser.add_argument("--category", default="934",
                           help="Which category number to download")
    argparser.add_argument("--prefix", default="[Food Week]",
                           help="Only keep files with this prefix")
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

    args = argparser.parse_args()

    titles = get_category(args.category)
    if args.prefix:
        titles = filter_titles(titles, args.prefix)
    titles = get_logged_titles(titles, args.dest)

    count = 0
    for simfile in titles.values():
        if not simfile_already_downloaded(simfile, args.dest):
            link = get_file_link(simfile.simfileid)
            count = count + 1
            get_simfile(simfile.simfileid, link, args.dest, args.extract)
            if args.extract:
                extracted_directory = extract_simfile(simfile, args.dest)
                if extracted_directory != simfile.name:
                    log_renaming_message(simfile, extracted_directory, args.dest)
                    simfile = simfile._replace(name=extracted_directory)
                if (args.tidy and simfile_already_downloaded(simfile,
                                                             args.dest,
                                                             check_zip=False,
                                                             verbose=False)):
                    unlink_zip(simfile, args.dest)

    print "Downloaded %d simfiles" % count
