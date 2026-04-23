import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
import sys

# Add the current directory and trisense directory to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trisense.main import main

if __name__ == "__main__":
    main()
