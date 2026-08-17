# UKAHT image pipeline

Run these commands from the `pipeline` folder.
## 1. Add the image inventory

Put the images inside `data\images`
Then run:

```powershell
python -m ukaht.ingest.build_inventory
```

The script scans the image folder and creates `data\inventory.csv` 

`image_uid` is generated once and remains permanent. `relative_path` is the
location below the configured image folder, and `file_name` is the original
filename. Running the script again preserves existing IDs and adds rows only for
new image paths. If an existing image is moved or renamed, edit its existing row
so it keeps the same `image_uid`.


## 2. Create the Python environment


```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
```

## 3. Check the setup

```powershell
python -m ukaht.check_setup
```

This only checks Python, installed packages and the selected device.
## 4. Run the pipeline

Run CLIP first:

```powershell
python -m ukaht.run_pipeline --steps clip
```

Then run Florence-2:

```powershell
python -m ukaht.run_pipeline --steps florence
```

```powershell
python -m ukaht.run_pipeline
```

## 5. Test CLIP search

After the CLIP part has finished:

```powershell
python -m ukaht.tagging.search_clip "snow-covered hut" --top-k 10
```

The query is converted to a CLIP text embedding and compared with the saved
normalised image embeddings. Results are printed in ranked order. This test does
not create a separate search-results CSV because the later UI can call the same
`ClipSearchEngine.search()` method.

## 6. Apply the controlled vocabulary

After CLIP embeddings have been created, run:

```powershell
python -m ukaht.tagging.classify_vocabulary
```

This reuses `clip_embeddings.npy`. It does not open or reprocess the images.
The official vocabulary prompts are converted to text embeddings and compared
with the saved image embeddings. The result is written to
`clip_vocabulary_tags.csv`.

## Output files

- `clip_embeddings.npy` contains one normalised CLIP vector for each indexed image.
- `clip_index.csv` connects each vector row to its `image_uid` and image path.
- `clip_vocabulary_tags.csv` contains the official facet and term assignments.
- `florence_descriptions.csv` contains only `image_uid`, `file_name` and `description`.
- `processing_manifest.csv` records what has already been processed.
- `processing_errors.csv` is created only if an image fails. It records the image,
  pipeline part and error message so the failed files can be corrected and retried.
