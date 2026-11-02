"""Entry point of the packaged app (PyInstaller runs this file as a script)."""

import sys

from taleport.main import main

sys.exit(main())
