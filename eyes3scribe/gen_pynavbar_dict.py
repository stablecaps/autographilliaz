import logging
from collections import defaultdict

from rich import print as rprint

from eyes3scribe.helpo import hcollections, hfile
from eyes3scribe.helpo.hstrops import (
    clean_str_pline,
    get_lines_between_tag_and_blank_line,
)
from eyes3scribe.regex_patterns import *

LOG = logging.getLogger(__name__)


# TODO: rename this function and put it somewhere more appropriate
def walk_nested_dicts_with_lists(obj):
    if isinstance(obj, list):  # could replace with collections.abc.MutableSequence
        myiterable = enumerate(obj)
    elif isinstance(obj, dict):  # could replace with collections.abc.MutableMapping
        myiterable = obj.items()
    else:
        return  # don't iterate -- pass back up

    for key, value in myiterable:
        if isinstance(value, str):
            # TODO: allow custiom function to be passed in using partial
            obj[key] = value.replace("docshw/", "")
        else:
            walk_nested_dicts_with_lists(value)
    return obj


# TODO: refactor the hell out of this ;o)
# TODO: sort out conversion of relative paths sooner
class GenPyNavbarDict:
    def __init__(self, cnf, search_path, toclinks_map_all) -> None:
        ### For every mdfile
        # 1. establish if it has a TOC
        # 2. Map the hierarchy of nav-doc links via the TOC
        # 3. We will use the anchor "## Table of Contents" to find md TOC

        # TODO: bad var name
        self.project_docs_dir_local = cnf.project_docs_dir + "/"
        LOG.debug("project_docs_dir: %s", self.project_docs_dir_local)
        self.project_docs_dir = cnf.project_docs_dir
        self.toclinks_map_all = toclinks_map_all
        self.hierarchy_dict = defaultdict(list)
        self.navbar_dict = {}

        self.mdtoc_path_list = hcollections.flatten_list(
            nested_list=hfile.find_files_with_grep_patt(
                search_path=search_path,
                file_glob="*.md",
                txt_pattern="## Table of Contents",
            )
        )
        rprint("mdtoc_path_list", self.mdtoc_path_list)

    @staticmethod
    def gen_cleaned_mdtoc_list(toc_mdlist):
        clean_toc_mdlist = []
        for line in toc_mdlist:
            line_stripped = line.strip()
            if "## Table of Contents" in line_stripped:
                pass
            elif line_stripped == "":
                pass
            else:
                mdlink_match = mdlink_patt.search(line_stripped)
                if mdlink_match is not None:
                    mdlink = mdlink_match.group(2)
                    clean_toc_mdlist.append(mdlink)
        return clean_toc_mdlist

    def gen_toc_dict_from_mdindex_files(self):
        for mdpath in self.mdtoc_path_list:
            print("mdpath", mdpath)
            mdpath_rel = mdpath.replace(self.project_docs_dir_local, "")
            print("mdpath_rel", mdpath_rel)

            if mdpath_rel not in self.toclinks_map_all:
                filetext = hfile.read_file_2string(filepath=mdpath)
                table_of_contents = get_lines_between_tag_and_blank_line(
                    filetext, start_tag="## Table of Contents"
                )

                clean_toc_mdlist = GenPyNavbarDict.gen_cleaned_mdtoc_list(
                    toc_mdlist=table_of_contents
                )
                self.toclinks_map_all[mdpath_rel].extend(clean_toc_mdlist)

        rprint("\ntoc_dict", self.toclinks_map_all)

    def reorder_toc_dict_so_index_first(self):
        # copy index files to front of list
        # catnames_list = list(self.toclinks_map_all.keys())
        for mdpath, toc_links in self.toclinks_map_all.items():
            rprint("mdpath", mdpath)
            toc_links_with_index = []
            if mdpath == "docshw/index.md":
                # TODO: fix this hard coded hack - think we need to specify main index in config
                continue
            for mdlink in toc_links:
                if mdpath != mdlink:
                    rprint("mdlink", mdlink)
                    ### deletes the index.mdfile from the list
                    # (as we want to make this the forst element in the list)
                    toc_links_with_index.append(mdlink)
            toc_links_with_index.insert(
                0, mdpath
            )  ### inserts the index.mdfile at the start of the list
            self.toclinks_map_all[mdpath] = toc_links_with_index
        rprint("toc_dict index ordered", self.toclinks_map_all)

    def gen_toc_hierarchy_dict(self):
        for mdpath, _ in self.toclinks_map_all.items():
            rprint("mdpath", mdpath)
            for file_path2, toc_links2 in self.toclinks_map_all.items():
                rprint("file_path2", file_path2)
                mdpath_rel = mdpath.replace(self.project_docs_dir_local, "")
                if mdpath_rel in toc_links2:
                    self.hierarchy_dict[file_path2].append(mdpath_rel)
                    break
        rprint("\nhierarchy_dict", self.hierarchy_dict)

    @staticmethod
    def clean_tockvs(mylink, myvalue):
        """This function splits the category and returns the toc key and value."""
        tockey = clean_str_pline(mylink.split("/")[-1], [".md"])
        tocvalue = clean_str_pline(mylink, [myvalue])

        return {tockey: tocvalue}

    def gen_navbar_dict(self):
        for key, link_list in sorted(
            self.hierarchy_dict.items(), key=lambda x: len(x[1]), reverse=True
        ):
            rprint("link_list", link_list)

            self.navbar_dict[key] = self.toclinks_map_all[key]
            rprint("navbar_dict", self.navbar_dict)

            new_link_list = []
            for mdlink in self.navbar_dict[key]:
                if mdlink in link_list:
                    rprint("mdlink", mdlink)
                    category_split = mdlink.split("/")
                    if category_split[-1] == "index.md":
                        category_name = clean_str_pline(category_split[-2], [".md"])
                    else:
                        category_name = clean_str_pline(category_split[-1], [".md"])

                    yaml2_sublist = [
                        GenPyNavbarDict.clean_tockvs(
                            mylink=link, myvalue=self.project_docs_dir_local
                        )
                        for link in self.toclinks_map_all[mdlink]
                    ]

                    sub_dict = {category_name: yaml2_sublist}
                    new_link_list.append(sub_dict)
                else:
                    toc_kvdict = GenPyNavbarDict.clean_tockvs(
                        mylink=mdlink, myvalue=self.project_docs_dir_local
                    )
                    new_link_list.append(toc_kvdict)
            self.navbar_dict[key] = new_link_list
        rprint("navbar_dict", self.navbar_dict)

    def main(self):
        self.gen_toc_dict_from_mdindex_files()

        ## 1. Check which mdtoc_path is in which list to figure out rough order
        ## 2. If it is in the list, then it is suboridnate
        ## 3. Create ranked order of mdfiles
        self.gen_toc_hierarchy_dict()

        self.reorder_toc_dict_so_index_first()

        self.gen_navbar_dict()

        #####################
        walk_nested_dicts_with_lists(obj=self.navbar_dict)

        print("#####################")
        self.navbar_cleaned_dict = {"nav": []}
        for key, values in self.navbar_dict.items():
            if key == "docshw/index.md":
                key_home = "Home"
                self.navbar_cleaned_dict["nav"].append({key_home: "index.md"})
                if isinstance(values, list):
                    for kvdict in values:
                        for k, v in kvdict.items():
                            self.navbar_cleaned_dict["nav"].append({k: v})

            else:
                key_renamed = key.replace("docshw/", "")
                self.navbar_cleaned_dict["nav"].append({key_renamed: values})

        for key, values in self.navbar_cleaned_dict.items():
            rprint("**", key, values)

        rprint("\nnavbar_cleaned_dict", self.navbar_cleaned_dict)

        return self.navbar_cleaned_dict
