import os
import sys

# Add the current directory and trisense directory to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trisense.main import main

if __name__ == "__main__":
    main()
