#!/usr/bin/python3.7

from aiogoogle import Aiogoogle
import os
import sys
import errno
import json
import asyncio
from aiohttp import ClientSession
import pprint


def _check_for_correct_cwd(current_dir):
    if current_dir[-9:] != "aiogoogle":  # current dir is aiogoogle
        print(current_dir)
        print("must be in aiogoogle's dir, not test dir")
        sys.exit()


def _pop_unstable_apis(all_apis: list):
    stable_apis = []
    for api in all_apis:
        if not len(api[1]) > 3:  # No funky versions because they break the tests alot
            stable_apis.append(api)
    return stable_apis


async def refresh_disc_docs_json():
    file_errors = []
    current_dir = os.getcwd()

    # Create new .data/ dir if one doesn't exists
    _check_for_correct_cwd(current_dir)

    # Refresh all_apis in tests/tests_globals.py
    all_apis = []
    print("Refreshing all_apis in tests_globals.py")
    async with ClientSession() as sess:
        apis_pref = await sess.get(
            "https://www.googleapis.com/discovery/v1/apis?preferred=true"
        )
        apis_pref = await apis_pref.json()
    for api in apis_pref["items"]:
        all_apis.append((api["name"], api["version"]))
    all_apis = _pop_unstable_apis(all_apis)
    with open("tests/test_globals.py", "w") as f:
        f.write("""### This file is autogenerated ###\n""")
        f.write(f"ALL_APIS = {pprint.pformat(all_apis)}")
        print("SUCCESS!")

    # Refresh discovery files in tests/data
    async with Aiogoogle() as aiogoogle:
        for name, version in all_apis:
            print(f"Downloading {name}-{version}")
            try:
                google_api = await aiogoogle.discover(name, version)
            except Exception as e:
                file_errors.append({f"{name}-{version}": str(e)})
                continue

            data_dir_name = current_dir + "/tests/data/"
            try:
                if not os.path.exists(data_dir_name):
                    os.makedirs(data_dir_name)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

            # Save discovery docuemnt as .json file to the newly created data dir
            file_name = (
                current_dir
                + "/tests/data/"
                + name
                + "_"
                + version
                + "_discovery_doc.json"
            )
            with open(file_name, "w") as discovery_file:
                json.dump(google_api.discovery_document, discovery_file)
            print(f"saved {name}-{version} to {file_name}")

    print("Done")
    if file_errors:
        print(f"Errors found: {str(file_errors)}")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(refresh_disc_docs_json())
