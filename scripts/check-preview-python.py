"""Check the preview runtime without PowerShell native-command string escaping."""
import sys

if sys.version_info < (3, 12):
    raise SystemExit('Python 3.12 or newer is required for the Sevlink preview.')

print('Python ' + sys.version.split()[0] + ' ready for the Sevlink preview.')
