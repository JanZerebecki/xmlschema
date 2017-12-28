# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2017, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
Common imports and methods for unittest scripts of the 'xmlschema' package.
"""
import unittest
import re
import sys
import os
import glob
import fileinput
import argparse

from functools import wraps

try:
    import xmlschema
except ImportError:
    # Adds the path of the package that contains the test.
    os.chdir(os.path.dirname(__file__))
    pkg_search_path = os.path.abspath('../..')
    if sys.path[0] != pkg_search_path:
        sys.path.insert(0, pkg_search_path)
    import xmlschema
else:
    os.chdir(os.path.dirname(__file__))

header = "Test %r" % xmlschema
print("*" * len(header) + '\n' + header + '\n' + "*" * len(header))


class XMLSchemaTestCase(unittest.TestCase):
    longMessage = True


class SchemaObserver(object):
    components = []

    @classmethod
    def observe_builder(cls, builder):
        if isinstance(builder, type):
            class BuilderProxy(builder):
                def __init__(self, *args, **kwargs):
                    super(BuilderProxy, self).__init__(*args, **kwargs)
                    cls.components.append(self)
            BuilderProxy.__name__ = builder.__name__
            return BuilderProxy

        elif callable(builder):
            @wraps(builder)
            def builder_proxy(*args, **kwargs):
                result = builder(*args, **kwargs)
                cls.components.append(result)
                return result
            return builder_proxy

    @classmethod
    def clear(cls):
        del cls.components[:]


ObservedXMLSchema = xmlschema.create_validator(
    xsd_version='1.0',
    meta_schema=xmlschema.validators.schema.XSD_1_0_META_SCHEMA_PATH,
    base_schemas=xmlschema.validators.schema.BASE_SCHEMAS,
    facets=xmlschema.validators.XSD_FACETS,
    **{k: SchemaObserver.observe_builder(v)
       for k, v in xmlschema.validators.schema.DEFAULT_BUILDERS.items() if k != 'simple_type_class'}
)


def get_test_args(args_line):
    try:
        args_line, _ = args_line.split('#', 1)
    except ValueError:
        pass
    return re.split(r'(?<!\\) ', args_line.strip())


def xsd_version_number(value):
    if value not in ('1.0', '1.1'):
        msg = "%r is not an XSD version." % value
        raise argparse.ArgumentTypeError(msg)
    return value


def get_args_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.usage = """TEST_FILE [TOT_ERRORS] [-i] [-x=VERSION]"""
    parser.add_argument('filename', metavar='TEST_FILE', type=str, help="Test filename (relative path).")
    parser.add_argument('tot_errors', nargs='?', type=int, default=0, help="Total errors expected (default=0).")
    parser.add_argument(
        '-i', dest="inspect", action="store_true", default=False,
        help="inspect using an observed custom schema class."
    )
    parser.add_argument(
        "-v", dest="version", metavar='VERSION', type=xsd_version_number, default='1.0',
        help="XSD version to use for schema (default is 1.0)."
    )
    return parser


test_line_parser = get_args_parser()


def tests_factory(test_function_builder, pathname, label="validation", suffix="xml"):
    tests = {}
    test_num = 0
    for line in fileinput.input(glob.iglob(pathname)):
        line = line.strip()
        if not line or line[0] == '#':
            continue

        test_args = test_line_parser.parse_args(get_test_args(line))
        test_file = os.path.join(os.path.dirname(fileinput.filename()), test_args.filename)
        if not os.path.isfile(test_file) or os.path.splitext(test_file)[1].lower() != '.%s' % suffix:
            continue

        if test_args.inspect:
            schema_class = ObservedXMLSchema
        else:
            schema_class = xmlschema.XMLSchema

        test_func = test_function_builder(test_file, schema_class, test_args.tot_errors, test_args.inspect)
        test_name = os.path.join(os.path.dirname(sys.argv[0]), os.path.relpath(test_file))
        test_num += 1
        class_name = 'Test{0}{1:03}'.format(label.title(), test_num)
        tests[class_name] = type(
            class_name, (XMLSchemaTestCase,),
            {'test_{0}_{1:03}_{2}'.format(label, test_num, test_name): test_func}
        )
    return tests
