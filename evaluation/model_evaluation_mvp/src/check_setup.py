import sys


def main() -> int:
    if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
        print("Version check failed")
        return 1

    try:
        import pandas
        import PIL
        import torch
        import transformers
    except ImportError as error:
        print(f"Missing package: {error.name}")
        return 1

    print(f"Python: {sys.version.split()[0]}")
    print(f"PyTorch: {torch.__version__}")
    print(f"Transformers: {transformers.__version__}")
    print(f"Pandas: {pandas.__version__}")
    print(f"Pillow: {PIL.__version__}")
    print(f"Device: {'cuda' if torch.cuda.is_available() else 'cpu'}")
    print("Compatible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

