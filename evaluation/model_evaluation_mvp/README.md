# UKAHT Image Classification MVP

This is a local MVP test using the images placed in the sample folder. 

CLIP is used for image categories and text search. BLIP and Florence-2 create captions so their output can be compared.
## Project folders

```text
UKAHT_Image_Classification_MVP/
|-- config/
|   |-- categories.txt
|   `-- search_queries.txt
|-- data/
|   `-- sample_images/
|-- outputs/
|-- src/
|   |-- check_setup.py
|   |-- config.py
|   |-- image_utils.py
|   |-- run_mvp.py
|   `-- score_review.py
|-- .gitignore
|-- README.md
`-- requirements.txt
```


## 1. Create the virtual environment

Run these commands one at a time:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

The terminal should show `(.venv)` 

## 2. Install the packages

Run:

```powershell
python -m pip install -r requirements.txt
```

Check the setup:

```powershell
python src\check_setup.py
```

## 3. Add the sample images

Copy the images selected for the MVP into:

```text
data\sample_images
```

Supported file types are JPG, JPEG, PNG, BMP, WEBP, TIF and TIFF.

## 4. Check the categories and queries


```text
config\categories.txt
config\search_queries.txt
```


## 5. Run the MVP

For the first test, run CLIP by itself:

```powershell
python src\run_mvp.py --models clip
```

run BLIP:

```powershell
python src\run_mvp.py --models blip
```

run Florence-2:

```powershell
python src\run_mvp.py --models florence
```

Each separate run keeps the earlier results. Running the models separately is recommended on a CPU computer.


## 6. Generated files

The `outputs` folder can contain:

```text
categories.csv
clip_search_results.csv
captions.csv
mvp_results.csv
review_template.csv
```


## 7. Review the results

Open `outputs\review_template.csv` in Excel or VS Code. Fill in:

- `classification_correct_yes_no` with `yes` or `no`
- `best_caption_blip_florence_tie` with `blip`, `florence` or `tie`
- `notes` when something is incorrect or unclear

Save the file and run:

```powershell
python src\score_review.py
```

This creates `outputs\review_summary.csv`.
