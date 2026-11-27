import os
import sys
import datetime
import logging
import argparse
from pathlib import Path
from typing import Sequence

import runner.commands as commands
import util.customLogger as logger

DEFAULT_PREFIX = 'Test'
DEFAULT_RUN_N = 10
DEFAULT_RUN_T = 3


def _log_level(value: str) -> int:
	"""Convert a log level name or number into a logging constant.

	Args:
		value: A level name such as ``"DEBUG"`` or a number such as ``"10"``.

	Returns:
		The corresponding ``logging`` level as an int.

	Raises:
		argparse.ArgumentTypeError: If the value is not a valid log level.
	"""
	if value.isdigit():
		return int(value)
	level = logging.getLevelName(value.upper())
	if not isinstance(level, int):
		raise argparse.ArgumentTypeError(f'invalid log level: {value!r}')
	return level


def build_parser() -> argparse.ArgumentParser:
	"""Create the command-line parser for ``simulation.py``.

	The built-in ``-h`` is disabled so ``help`` / ``--help`` can be routed
	to ``commands.usage()`` and ``commands.do_help()`` instead.

	Returns:
		A configured ``argparse.ArgumentParser``.
	"""
	parser = argparse.ArgumentParser(
		prog='simulation.py', add_help=False, allow_abbrev=False
	)
	parser.add_argument('N', type=int, nargs='?', help='number of agents')
	parser.add_argument('T', type=int, nargs='?', help='number of time steps')
	parser.add_argument('-c', '--config', type=Path, metavar='FILE',
						help='path to the configuration file')
	parser.add_argument('-f', dest='filename', metavar='FILENAME',
						help='output filename')
	parser.add_argument('-verbose', '--v', dest='log_level', type=_log_level,
						metavar='LOG_LEVEL', default=None,
						help='log level (e.g. DEBUG, INFO, or a number)')
	parser.add_argument('--run', action='store_true',
						help='run a quick default simulation')
	parser.add_argument('--help', action='store_true', help='show usage')
	return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
	"""Parse arguments, accepting a trailing bare ``run`` or ``help``.

	Only the last token is translated, matching the original
	``sys.argv[-1]`` checks, so ``run`` elsewhere stays a normal value.

	Args:
		argv: Arguments without the program name. Defaults to ``sys.argv[1:]``.

	Returns:
		The parsed arguments as a ``Namespace``.
	"""
	argv = sys.argv[1:] if argv is None else list(argv)
	if argv and argv[-1] in ('run', 'help'):
		argv[-1] = '--' + argv[-1]
	return build_parser().parse_args(argv)


# Normal interface

def main(argv: Sequence[str] | None = None) -> int:
	"""Configure settings from the command line, then run or start the CLI.

	Args:
		argv: Optional argument list, mainly for testing.

	Returns:
		A process exit code.
	"""
	args = parse_args(argv)
	print(args)

	if args.help:
		commands.usage()
		commands.do_help()
		return 0

	# Config file first, so explicit command-line values override it
	if args.config is not None:
		path = args.config.expanduser().resolve()
		if not path.is_file():
			print(f'Config file not found: {path}', file=sys.stderr)
			return 1
		commands.settings.update(commands.load_config(path))

	# One user-supplied prefix for both the log file and the output files
	prefix = args.filename or commands.settings.get('filename') or DEFAULT_PREFIX
	if args.filename or 'filename' in commands.settings:
		commands.settings['filename'] = prefix

	log_name = f'{prefix}-{datetime.datetime.now():%Y%m%d}'
	root_logger = logger.gen_logging(
		log_name, os.path.splitext(os.path.basename(__file__))[0], args.log_level
	)

	if args.N is not None:
		commands.settings['N'] = args.N
	if args.T is not None:
		commands.settings['T'] = args.T

	n = commands.settings.get('N')
	t = commands.settings.get('T')

	# Express run: fill in defaults for anything missing, then exit
	if args.run:
		commands.settings['N'] = n if n is not None else DEFAULT_RUN_N
		commands.settings['T'] = t if t is not None else DEFAULT_RUN_T
		commands.do_run_default()
		return 0

	# Initial settings: prompt only for what is still missing
	if n is None and t is None:
		commands.basic_settings()
	elif t is None:
		commands.set_T()
	elif n is None:
		commands.set_N()

	# Not an express run, so hand over to the internal command line
	cmd = ''
	root_logger.info('Welcome to the Agent Based Simulator!')
	root_logger.info('Please enter your command below: ')
	while cmd.lower() not in ['exit', 'quit']:
		cmd = input('> ')
		handler = getattr(commands, f'do_{cmd}', None)
		root_logger.debug(f'Looking for: do_{cmd}, found: {handler}')
		if handler is not None:
			handler()
		else:
			root_logger.warning(f"Unknown command: '{cmd}'")

	return 0

if __name__ == "__main__":
    main()