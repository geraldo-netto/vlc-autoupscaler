"""Persist process evidence before interpreting benchmark output."""
import json
import subprocess


def output_text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''


def execute_capture(command, environment, timeout=150):
    try:
        result = subprocess.run(command, env=environment, capture_output=True, text=True,
                                errors='replace', timeout=timeout)
        return dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    except subprocess.TimeoutExpired as error:
        return dict(returncode=-1, failure='timeout', timeout_seconds=error.timeout,
                    stdout=output_text(error.stdout), stderr=output_text(error.stderr))
    except OSError as error:
        return dict(returncode=-1, failure='launch', error=str(error), stdout='', stderr='')


def save(path, row):
    path.write_text(json.dumps(row, indent=2) + '\n')


def checked_attempt(path, row, environment, parse, timeout):
    row.update(execute_capture(row['command'], environment, timeout))
    if row['returncode']:
        row.setdefault('failure', 'exit')
    save(path, row)
    if not row.get('failure'):
        try:
            row.update(parse(row['stdout']))
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            row.update(failure='output-parse', error=str(error))
        save(path, row)
    if row.get('failure'):
        raise RuntimeError('capture failed; partial evidence retained: ' + str(path))
    return row


def json_object(text):
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError('capture output must be a JSON object')
    return result
