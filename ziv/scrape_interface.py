"""
This is a more friendly interface to the z-i-v scraper than the
command line interface.

By default, when it loads, it is set to download Round B of the
2016 Simfile Shuffle.

If you are reading this on github and looking for a way to download
the script, look for the button labeled "Raw" to the upper right.
Download to the directory where you want the simfiles downloaded.
You will need Python installed.  www.python.org
The program is compatible with 2.7.  Python 3 has not been tested.

There are three other files which are also needed, if downloading
files individually from github.  You can find them by clicking on the
"ziv" breadcrumb where it says step-mani-tools/ziv/scrape_interface.py
The necessary files are "cached.pkl", "scrape_category.py", and
"__init__.py"

Done:
have a menu listing the categories you can download (done)
file picker to choose the directory to save to
have a text field offering with a prefix you can limit to
add a text field for regex as well
set defaults
button that launches the download
a progress bar
button that reloads the categories
filter by date
remember the download directory between executions

TODO:
Break downloads into chunks so there is more granularity for the UI
redirect/copy stdout to a text window
recover from network errors
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

import codecs
import os
import sys

# python 2.7/3.6 compatability
try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    import Tkinter as tk
except ImportError:
    import tkinter as tk

try:
    import ttk
except ImportError:
    from tkinter import ttk

try:
    import tkFileDialog as filedialog
except ImportError:
    from tkinter import filedialog

import scrape_category

DEFAULT_PLATFORM="User"
DEFAULT_CATEGORY="Z-I-v Simfile Shuffle 2016"
DEFAULT_PREFIX="[Round B]"


def config_path():
    """
    Choose a suitable path for the config file.

    This works on mac & windows.

    There are modules that do this, such as appdirs, but I don't want
    random user X to have to learn how to pip install things just to
    use the script.
    """
    user_config = os.path.expanduser("~/.ziv_scraper")
    if os.path.exists(user_config):
        return user_config
    else:
        try:
            os.mkdir(user_config)
            return user_config
        except OSError:
            print("Wanted to make a config directory in %s but unable to" % user_config)
            raise


def config_file():
    return os.path.join(config_path(), "config.txt")


def load_config():
    try:
        with open(config_file(), 'rb') as fin:
            config = pickle.load(fin)
    except (OSError, IOError, pickle.UnpicklingError):
        config = {}
    return config.get("initial_path", None)


def save_config(initial_path):
    config = {"initial_path": initial_path}

    try:
        with open(config_file(), 'wb') as fout:
            pickle.dump(config, fout)
    except:
        try:
            os.remove(config_file())
        except (OSError, IOError):
            pass
        raise



class App(tk.Tk):

    def __init__(self, master, category_map):

        self.frame = tk.Frame(master)
        self.frame.pack()

        self.category_map = category_map

        # Add a dropdown chooser for the platform
        # eg Arcade, Wii, etc
        platform_list = list(category_map.keys())
        max_width = max(len(x) for x in platform_list)
        self.platform_var = tk.StringVar()
        self.platform_var.set(DEFAULT_PLATFORM)
        self.platform_drop = ttk.Combobox(self.frame,
                                          textvariable=self.platform_var,
                                          values=platform_list,
                                          state="readonly",
                                          width=max_width)
        self.platform_drop.bind("<<ComboboxSelected>>", self.choose_platform)
        self.platform_drop.pack(anchor="w")

        # Add a dropdown chooser for the category
        # When the platform changes, the list of available choices
        # will be updated
        category_list = list(category_map[self.platform_var.get()].keys())
        max_width = max(max(len(x) for x in platform.keys())
                        for platform in category_map.values())
        self.category_var = tk.StringVar()
        if DEFAULT_CATEGORY in category_list:
            self.category_var.set(DEFAULT_CATEGORY)
        else:
            self.category_var.set(category_list[0])
        self.category_drop = ttk.Combobox(self.frame,
                                          textvariable=self.category_var,
                                          values=category_list,
                                          state="readonly",
                                          width=max_width)
        self.category_drop.bind("<<ComboboxSelected>>", self.choose_category)
        self.category_drop.pack()

        # Build a frame for the directory chooser
        # Putting things in a small frame keeps them
        # coordinated visually
        # There is a button to show the chooser widget and a
        # label which shows the current directory
        directory_frame = tk.Frame(self.frame)
        directory_chooser = tk.Button(directory_frame,
                                      text='Destination directory',
                                      command=self.ask_directory)
        directory_chooser.pack(side=tk.LEFT)
        self.directory_var = tk.StringVar()
        current_save_dir = load_config()
        if not current_save_dir:
            current_save_dir = os.getcwd()
        self.directory_var.set(current_save_dir)
        directory_label = ttk.Label(directory_frame, textvariable=self.directory_var)
        directory_label.pack(side=tk.LEFT)
        directory_frame.pack(anchor="w")

        # Build a frame for the filters
        # The inner frame will use grid() to make sure the columns
        # line up nicely
        # The left side will have a radio: None, Prefix, Regex
        # The right side will have text entries for Prefix and Regex
        filter_frame = tk.Frame(self.frame)
        self.filter_choice = tk.IntVar()
        self.filter_choice.set(1)
        radio_none = tk.Radiobutton(filter_frame, text="No filter",
                                    variable=self.filter_choice, value=0)
        radio_none.grid(row=0, column=0, sticky=tk.W)

        radio_prefix = tk.Radiobutton(filter_frame, text="Prefix",
                                      variable=self.filter_choice, value=1)
        radio_prefix.grid(row=1, column=0, sticky=tk.W)
        self.prefix_entry = tk.Entry(filter_frame)
        self.prefix_entry.grid(row=1, column=1)
        self.prefix_entry.insert(0, DEFAULT_PREFIX)

        radio_regex = tk.Radiobutton(filter_frame, text="Regex",
                                     variable=self.filter_choice, value=2)
        radio_regex.grid(row=2, column=0, sticky=tk.W)
        self.regex_entry = tk.Entry(filter_frame)
        self.regex_entry.grid(row=2, column=1)

        since_label = ttk.Label(filter_frame, text="Age filter:")
        since_label.grid(row=3, column=0, sticky=tk.W)
        self.since_entry = tk.Entry(filter_frame)
        self.since_entry.grid(row=3, column=1)

        filter_frame.pack(anchor="w")
        
        download_button = tk.Button(self.frame,
                                    text="DOWNLOAD!",
                                    command=self.download)
        download_button.pack(anchor="w")

        # A small block showing current progress
        progress_frame = tk.Frame(self.frame)
        progress_label = ttk.Label(progress_frame, text="Download progress:")
        progress_label.pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(progress_frame, orient="horizontal",
                                        mode="determinate")
        self.progress.pack(anchor="w", fill=tk.BOTH)
        progress_frame.pack(fill=tk.BOTH)

        platform_button = tk.Button(self.frame,
                                    text="Reload platforms and categories",
                                    command=self.reload_platforms)
        platform_button.pack(anchor="w")

    def reload_platforms(self):
        category_map = scrape_category.cached_scrape_platforms(force=True)

        new_platform_list = list(category_map.keys())
        self.platform_drop['values'] = new_platform_list
        platform = new_platform_list[0]
        self.platform_var.set(platform)

        new_category_list = list(category_map[platform].keys())
        self.category_drop['values'] = new_category_list
        self.category_var.set(new_category_list[0])

        self.category_map = category_map

    def ask_directory(self):
        self.frame.update()
        new_dir = filedialog.askdirectory(parent=self.frame,
                                          title="Directory to save simfiles")
        if new_dir:
            self.directory_var.set(new_dir)
            save_config(initial_path=new_dir)

    def choose_platform(self, event):
        platform = self.platform_var.get()
        print("Platform updated to %s" % platform)
        new_category_list = list(self.category_map[platform].keys())
        self.category_drop['values'] = new_category_list
        self.category_var.set(new_category_list[0])

    def choose_category(self, event):
        print("Category updated to %s: %s" % (self.platform_var.get(),
                                              self.category_var.get()))
        # self.category_var.get(), self.platform_var.get()

    def download(self):
        platform = self.platform_var.get()
        category = self.category_var.get()
        category_id = self.category_map[platform][category]
        download_directory = self.directory_var.get()
        print("Downloading %s to %s" % (category_id, download_directory))

        prefix = ""
        regex = ""
        if self.filter_choice.get() == 1:
            prefix = self.prefix_entry.get()
        elif self.filter_choice.get() == 2:
            regex = self.regex_entry.get()
        since = self.since_entry.get()
        titles = scrape_category.get_filtered_records_from_ziv(category=category_id,
                                                               dest=download_directory,
                                                               prefix=prefix,
                                                               regex=regex,
                                                               since=since,
                                                               use_logfile=True)
        print("Found %d matching simfiles" % len(titles))
        self.progress["value"] = 0
        self.progress["maximum"] = len(titles)
        self.download_titles = list(titles.values())
        # Use self.frame.after so that the UI can refresh
        self.frame.after(1, self.continue_download)


    def continue_download(self):
        download_directory = self.directory_var.get()
        simfile = self.download_titles[self.progress["value"]]
        if not scrape_category.simfile_already_downloaded(simfile, dest=download_directory):
            scrape_category.download_simfile(simfile, dest=download_directory,
                                             tidy=True, use_logfile=True,
                                             extract=True)
        self.progress["value"] = self.progress["value"] + 1
        if self.progress["value"] < len(self.download_titles):
            # Use self.frame.after so that the UI can refresh
            self.frame.after(1, self.continue_download)        


def main():
    try:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer)
    except AttributeError:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout)

    category_map = scrape_category.cached_scrape_platforms()

    root = tk.Tk()

    _ = App(root, category_map)

    root.mainloop()

if __name__ == "__main__":
    main()
