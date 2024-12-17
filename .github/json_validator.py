#! /usr/bin/env python

import sys
import json
import optparse
import logging
from jsonschema import validate, ValidationError


VERSION = "1.0"

DEFAULT_USAGE_TEXT = """
===============================================================================================
Usage: %prog [options] arg
JSON Validator
===============================================================================================
"""


def read_json_file(file_path):
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON from file: {file_path}. Error: {e.msg}")
        sys.exit(1)


def validate_json(options):
    try:
        validate(instance=options.json_data, schema=options.json_schema)
        logging.info("JSON validation pass: JSON is valid.")
    except ValidationError as e:
        logging.info(f"JSON validation error: {e.message}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error during JSON validation: {str(e)}")
        sys.exit(1)


def check_prerequisite(options):
    if options.json_data:
        options.json_data = read_json_file(options.json_data)
    else:
        logging.error("Missing JSON data file. Please specify --data.")
        sys.exit(1)

    if options.json_schema:
        options.json_schema = read_json_file(options.json_schema)
    else:
        logging.error("Missing JSON schema file. Please specify --schema.")
        sys.exit(1)


def configure_logging():
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    logging.basicConfig(level=logging.DEBUG, format=log_format, handlers=handlers)


def close_logging():
    for handler in logging.getLogger().handlers[:]:
        handler.close()
        logging.getLogger().removeHandler(handler)


def main(argv):
    option_parser = optparse.OptionParser(usage=DEFAULT_USAGE_TEXT, version=VERSION)
    option_parser.add_option(
        "-d",
        "--data",
        dest="json_data",
        action="store",
        default="",
        help="Path to the JSON data file that needs to be validated. This option is required.",
    )
    option_parser.add_option(
        "-s",
        "--schema",
        dest="json_schema",
        action="store",
        default="",
        help="Path to the JSON schema file that defines the structure and rules for the JSON data. This option is required.",
    )
    options, args = option_parser.parse_args(argv)

    configure_logging()

    check_prerequisite(options)
    validate_json(options)

    close_logging()


if "__main__" == __name__:
    result = main(sys.argv)
    sys.exit(result)
