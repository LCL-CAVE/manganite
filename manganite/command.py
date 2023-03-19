import argparse
import sys

from panel import __version__ as pn_version
from panel.command.serve import Serve as PnServe

from manganite import __version__, preprocessor


def main():
    parser = argparse.ArgumentParser(prog='mnn')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s {} (panel {})'.format(__version__, pn_version))

    subs = parser.add_subparsers(title='subcommands')

    serve_subparser = subs.add_parser(PnServe.name, help=PnServe.help)
    serve_subcommand = PnServe(parser=serve_subparser)
    serve_subparser.set_defaults(invoke=serve_subcommand.invoke)

    if len(sys.argv) == 1:
        args = parser.parse_args(['--help'])
        args.invoke(args)
        sys.exit()

    args = parser.parse_args()
    preprocessor._patch_python_exporter()

    args.invoke(args)

if __name__ == '__main__':
    main()
