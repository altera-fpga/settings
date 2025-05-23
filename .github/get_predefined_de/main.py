#! /usr/bin/env python

import re
import json
import os
import requests
import optparse
import sys
import logging
import base64
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlunparse


VERSION = '1.0'

DEFAULT_USAGE_TEXT = ("""
===============================================================================================
Usage: %prog [options] arg
Tool to get predefined design examples
===============================================================================================
""")

LIST_JSON = 'list.json'
CONTROLLER_JSON = 'controller.json'
PREDEFINED_URL_FILE = 'predefined_url.json'


def is_github(url):
    return "github.com" in url

def metadata_formatize(metadata):
    return { "num": len(metadata), "designs": metadata }

def write_to_file(output_path, content):
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Write the content to the file
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(content, file, indent=4, ensure_ascii=False)

        logging.info(f"Successfully wrote content to {output_path}.")
    except Exception as e:
        logging.error(f"Failed to write to file {output_path}: {e}")

def add_controller(options, content):
    """
    This is to control whether the Quartus for a particular version should be always regenerate the list.json
    and shouldn't be using this pre-generated list.json.
    """
    if os.path.exists(options.controller):
        with open(options.controller, 'r', encoding='utf-8') as file:
            controller_content = json.load(file)

            # Combine content and controller into one.
            content = {**content, **controller_content} 
    else:
        logging.info("Controller not found.")
    return content

def replace_if_diff(options, all_list_json):
    logging.info("----------------------------------------")
    logging.info(f"Checking the content of {options.output} for updates...")
    all_list_json = add_controller(options, all_list_json)

    try:
        # Check if the output file exists
        if os.path.exists(options.output):
            with open(options.output, 'r', encoding='utf-8') as file:
                existing_content = json.load(file)

            # Compare the existing content with the generated content
            if existing_content == all_list_json:
                logging.info(f"The content of {options.output} is up-to-date. No changes are required. Exiting.")
            else:
                logging.info("Differences detected between the existing file and the generated content.")
                write_to_file(options.output, all_list_json)
        else:
            logging.info(f"The file {options.output} does not exist. Creating a new file...")
            write_to_file(options.output, all_list_json)
    except Exception as e:
        logging.error(f"An error occurred while verifying the file {options.output}: {e}")
        sys.exit(1)

def get_design_examples_list(data):
    # Possibility 1: { "data": { "designs": [] } }
    if "data" in data:
        if "designs" in data["data"]:
            data = data["data"]["designs"]
    # Possibility 2: { "designs": [] }
    elif "designs" in data:
        data = data["designs"]
    else:
        logging.warning(f"The data format is invalid: {data}. Skipping this entry...")
        data = []
    return data

def fetch_github_releases(repo_owner, repo_name, headers):
    """
    Fetches the list of releases from a GitHub repository.
    """
    releases_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
    try:
        response = requests.get(releases_url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch releases for repository {repo_owner}/{repo_name}. Error: {e}")
        sys.exit(1)

def process_github_url(url_detail):
    """
    Processes each release's assets to find and extend list.json content.
    """
    list_json = []

    releases = fetch_github_releases(url_detail["repo_owner"], url_detail["repo_name"], url_detail["headers"])

    for release in releases:
        design_package_maps = {}
        list_json_by_release = []

        # Flow to get list.json from a release
        for asset in release.get('assets', []):
            if 'name' in asset:
                # Example: s10_pcie_devkit_blinking_led_stp.zip => https://api.github.com/repos/intel-sandbox/personal.kbrunham.fpga-partial-reconfig/releases/assets/159359041
                design_package_maps[asset['name']] = asset['url']

                if asset['name'] == LIST_JSON:
                    list_json_url = asset['url']

                    # Set the header - please read https://docs.github.com/en/rest/releases/assets
                    headers = url_detail["headers"]
                    headers["Accept"] = "application/octet-stream" # This is required to download file

                    try:
                        list_json_response = requests.get(list_json_url, headers=headers)
                        list_json_response.raise_for_status()  # Raise an exception for HTTP errors
                        data = list_json_response.json()
                        list_json_by_release = get_design_examples_list(data)
                    except requests.exceptions.RequestException as e:
                        logging.error(f"Unable to fetch {LIST_JSON} from release '{release['tag_name']}': {e}")
                        sys.exit(1)
            else:
                logging.error(f"Missing 'name' field in asset: {asset}")
                sys.exit(1)

        # If list.json is found...
        if list_json_by_release:
            logging.info(f"Found {len(list_json_by_release)} design examples in release '{release['tag_name']}'")

            for item in list_json_by_release:
                if item['downloadUrl'] in design_package_maps:
                    item["Q_DOWNLOAD_URL"] = design_package_maps[ item['downloadUrl'] ]
                else:
                    logging.warning(f"Missing asset {item['downloadUrl']} in release {release['tag_name']}")
                    item["Q_DOWNLOAD_URL"] = ""

                item['Q_GITHUB_RELEASE'] = release['tag_name']

            list_json.extend(list_json_by_release)
        else:
            logging.warning(f"Unable to read {LIST_JSON} in release '{release['tag_name']}'. Skipping...")

    if not list_json:
        logging.error(f"Unable to read any {LIST_JSON} in URL {url_detail['url']}")
        sys.exit(1)

    return list_json

def process_non_github_url(url_detail):
    """
    Legacy function to cater for Intel Design Store.
    Will be removed when Intel Design Store is phased out by end of year 2025.
    Processes non-GitHub URLs to fetch and extend list.json content.
    """
    list_json = []
    try:
        response = requests.get(url_detail["url"], headers=url_detail["headers"])
        try:
            data = json.loads(response.text, strict=False)
            list_json_by_url = get_design_examples_list(data)

            if list_json_by_url:
                logging.info(f"Found {len(list_json_by_url)} design examples in this non GitHub URL")

                for item in list_json_by_url:
                    item["Q_DOWNLOAD_URL"] = item["downloadUrl"]

                list_json.extend( list_json_by_url )
            else:
                logging.error(f"Unable to find any design examples in URL {url_detail['url']}")
                sys.exit(1)
        except json.JSONDecodeError:
            logging.error(f"URL {url_detail['url']} did not return a valid JSON response.")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch URL {url_detail['url']}: {e}")
        sys.exit(1)
    return list_json

def extract_url_details(urls):
    urls_details = []
    for url in urls:
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.lstrip('/').split('/')

        if len(path_parts) >= 2:
            repo_owner = path_parts[0]
            repo_name = path_parts[1]
        else:
            repo_owner = ''
            repo_name = ''

        urls_details.append({
            "url": url,
            "headers": {},
            "repo_owner": repo_owner,
            "repo_name": repo_name
        })
    return urls_details

def get_legacy_predefined_url():
    return [
        "https://bsas.intel.com/api/design_examples/latest/"
    ]

def get_predefined_url():
    predefined_urls = get_legacy_predefined_url()
    try:
        with open(PREDEFINED_URL_FILE, 'r', encoding='utf-8') as file:
            data = json.load(file)
            for item in data:
                if "url" in item:
                    predefined_urls.append( item["url"] )
    except FileNotFoundError:
        logging.error(f"File not found: {PREDEFINED_URL_FILE}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON from file {PREDEFINED_URL_FILE}: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred while reading the file {PREDEFINED_URL_FILE}: {e}")
        sys.exit(1)
    return predefined_urls

def get_unique_urls(url_details):
    unique_list = []
    temp_list = []
    for item in url_details:
        if item['url'] not in temp_list:
            temp_list.append(item['url'])
            unique_list.append(item)
    return unique_list

def get_design_examples(options):
    all_list_json = []
    predefined_urls = get_predefined_url()
    url_details = extract_url_details(predefined_urls)
    url_details = get_unique_urls(url_details)

    for url_detail in url_details:
        logging.info("----------------------------------------")
        logging.info(f"Processing URL {url_detail['url']}")

        if is_github( url_detail["url"] ):
            list_json = process_github_url(url_detail)
        else:
            list_json = process_non_github_url(url_detail)

        # Added validation status for predefined URL
        for item in list_json:
            item["Q_VALIDATED"] = True

        all_list_json.extend( list_json )

    logging.info("----------------------------------------")
    if all_list_json:
        logging.info(f"Consolidating all {LIST_JSON} files into '{options.output}'...")
        logging.info(f"Total consolidated design examples: {len(all_list_json)}")
        all_list_json = metadata_formatize(all_list_json)
        replace_if_diff(options, all_list_json)
    else:
        logging.error(f"No {LIST_JSON} files were found.")
        sys.exit(1)

def check_prerequisite(options):
    # Example: /home/runner/work/settings/settings/scripts/catalog/list.json
    dir = os.path.join(os.getcwd(), ".github", "get_predefined_de", "catalog")
    options.output = os.path.join(dir, LIST_JSON)
    options.controller = os.path.join(dir, CONTROLLER_JSON)

def configure_logging(options):
    handlers = []
    handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s', 
        handlers=handlers
    )

def close_logging():
    for handler in logging.getLogger().handlers[:]:
        handler.close()
        logging.getLogger().removeHandler(handler)

def main(argv):
    option_parser = optparse.OptionParser(usage=DEFAULT_USAGE_TEXT, version=VERSION)
    options, args = option_parser.parse_args(argv)

    configure_logging(options)
    check_prerequisite(options)
    get_design_examples(options)
    close_logging()

if "__main__" == __name__:
    result = main(sys.argv)
    sys.exit(result)
