"""允许 python -m spice2svg 调用。"""

import sys
from .cli import main

sys.exit(main())
