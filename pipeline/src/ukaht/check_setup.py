import platform
import sys


def main() -> int:
    print(f"Python: {platform.python_version()}")
    if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
        print("Use Python 3.10, 3.11 or 3.12 for this project.")
        return 1

    try:
        import numpy
        import pandas
        import PIL
        import pyarrow
        import torch
        import transformers
    except ImportError as error:
        print(f"Missing package: {error.name}")
        print("Install the packages from requirements.txt.")
        return 1

    from ukaht.config import load_config

    config = load_config()
    print(f"PyTorch: {torch.__version__}")
    print(f"Transformers: {transformers.__version__}")
    print(f"Pandas: {pandas.__version__}")
    print(f"NumPy: {numpy.__version__}")
    print(f"Pillow: {PIL.__version__}")
    print(f"PyArrow: {pyarrow.__version__}")
    print(f"Device: {'cuda' if torch.cuda.is_available() else 'cpu'}")
    print(f"Image folder: {config.image_directory}")
    print(f"Inventory: {config.inventory_file}")
    print("Setup looks ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
