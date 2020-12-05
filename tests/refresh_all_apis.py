#!/usr/bin/python3.7

from aiogoogle import Aiogoogle
import os
import sys
import errno
import json
import asyncio
from aiohttp import ClientSession
from aiogoogle import HTTPError
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
    final_all_apis = []

    async with ClientSession() as sess:
        apis_pref = await sess.get(
            "https://www.googleapis.com/discovery/v1/apis?preferred=true"
        )
        apis_pref = await apis_pref.json()

    for api in apis_pref["items"]:
        all_apis.append((api["name"], api["version"]))

    all_apis = _pop_unstable_apis(all_apis)
    final_all_apis = all_apis

    async with Aiogoogle() as google:
        tasks = [google.discover(name, version) for (name, version) in all_apis]
        print('Requesting all APIs, this might take a while')
        all_discovery_documents = await asyncio.gather(*tasks, return_exceptions=True)

    # Refresh discovery files in tests/data
    for i, google_api in enumerate(all_discovery_documents):
        name = all_apis[i][0]
        version = all_apis[i][1]
        if isinstance(google_api, HTTPError):
            e = google_api
            if e.res.status_code != 404:
                print('Non 404 error')
                print('\033[91m\n' + e + '\n\033[0m')

            if e.res.status_code == 404:
                # only ignore if it's a 404 error. Should raise an error otherwise
                final_all_apis = list(filter(lambda api: (api[0] != name), final_all_apis))

            file_errors.append({f"{name}-{version}": str(e)})
            print(f'\033[91mError: Failed to download {name} {version}\033[0m')
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

    with open("tests/ALL_APIS.py", "w") as f:
        f.write("""### This file is autogenerated ###\n""")
        f.write(f"ALL_APIS = {pprint.pformat(final_all_apis)}")
        print("SUCCESS!")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(refresh_disc_docs_json())
