"""
Plan:
have a menu listing the categories you can download
have a text field offering with a prefix you can limit to
add a text field for regex as well
button that launches the download

advanced: a progress bar
"""

import Tkinter as tk
import scrape_category

class App(tk.Tk):

    def __init__(self, master, category_map):

        frame = tk.Frame(master)
        frame.pack()

        platform_list = list(category_map.keys())
        self.platform_var = tk.StringVar()
        self.platform_var.set(platform_list[0])
        self.platform_drop = tk.OptionMenu(frame, self.platform_var,
                                           *platform_list,
                                           command=self.choose_platform)
        self.platform_drop.pack(side=tk.LEFT)

        category_list = list(category_map[platform_list[0]].keys())
        self.category_var = tk.StringVar()
        self.category_var.set(category_list[0])
        self.category_drop = tk.OptionMenu(frame, self.category_var,
                                           *category_list,
                                           command=self.choose_category)
        self.category_drop.pack(side=tk.LEFT)

        self.category_map = category_map
        
    def choose_platform(self, platform):
        print "Platform updated to %s" % platform
        self.category_var.set('')
        self.category_drop['menu'].delete(0, 'end')
        new_category_list = list(category_map[platform].keys())
        for category in new_category_list:
            command=tk._setit(self.category_var, category,
                              self.choose_category)
            self.category_drop['menu'].add_command(label=category,
                                                   command=command)

        self.category_var.set(new_category_list[0])

    def choose_category(self, arg):
        print arg
        # self.category_var.get(), self.platform_var.get()

# TODO: this seems pretty fast, but we might want to cache the results
# to be friendlier to the server
category_map = scrape_category.scrape_platforms()

root = tk.Tk()

app = App(root, category_map)

root.mainloop()

# root.destroy() # optional; see description below
