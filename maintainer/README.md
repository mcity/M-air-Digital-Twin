# Maintainers: publishing the assets

The Hugging Face dataset is `M-Air/m-air_digital_twin`. Its archives and `manifest.json` are produced
from an installed plugin by `package_assets.py`:

```bash
python3 maintainer/package_assets.py --plugin <project>/Plugins/MAirCorridor \
    --terrain <MAirCorridor_Assets>/ue_rect_3m --out <dataset folder>
```

Then, inside the dataset folder:

```bash
hf auth login
hf upload-large-folder M-Air/m-air_digital_twin . --repo-type=dataset
```

Re-run both after the content changes. The installer compares the checksums in `manifest.json` with what
a user already has, so only changed files are downloaded again. If the dataset id changes, update
`HF_REPO` at the top of `install.py`, `README.md` and `docs/`.
