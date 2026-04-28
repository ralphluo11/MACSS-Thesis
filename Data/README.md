# Data Directory

This directory is intentionally empty. The corpus is not redistributed in this repository.

## Why

1. **Copyright.** Article body text from The New York Times is copyrighted; redistributing it is not permitted under fair use for the volume involved (~5,400 China-related articles).
2. **Size.** The full-text file (~250 MB) exceeds GitHub's per-file size limit and would inflate clone times.

## How to populate this directory

Run the scraping pipeline described in [`../scraping/`](../scraping/) and concatenate the per-year output files into the three CSVs the notebooks expect:

- `China_Metadata_Merged_2020-2024.csv` — China-related article metadata, 2020–2024
- `Russia_Metadata_Merged_2020-2024.csv` — Russia-related article metadata, 2020–2024
- `China_Fulltext_Merged_2020-2024.csv` — China-related articles with full body text, 2020–2024

The notebooks in the repository root read these three files. `EDA.ipynb` writes one additional intermediate file here (`NYT_Master_Cleaned_2020-2024.csv`); `Main_Part.ipynb` writes two more in the working directory (`Yearly_Changes_Expanded.csv`, `NYT_Identity_Final_Results.csv`). All generated files are git-ignored.

## Required inputs

The scraper produces per-year files of the form:

```
China_articles_fulltext_202001_to_202012.csv
China_articles_fulltext_202101_to_202112.csv
... (one per year, 2020–2024)
all_article_metadata_2020.csv
all_article_metadata_2021.csv
... (one per year)
```

Concatenate them with pandas:

```python
import pandas as pd, glob

china_meta = pd.concat([pd.read_csv(f) for f in sorted(glob.glob('all_article_metadata_*.csv'))], ignore_index=True)
china_meta = china_meta[china_meta['is_keyword_match']].drop_duplicates(subset='web_url')
china_meta.to_csv('Data/China_Metadata_Merged_2020-2024.csv', index=False)

china_full = pd.concat([pd.read_csv(f) for f in sorted(glob.glob('China_articles_fulltext_*.csv'))], ignore_index=True)
china_full = china_full.drop_duplicates(subset='web_url')
china_full.to_csv('Data/China_Fulltext_Merged_2020-2024.csv', index=False)
```

(Repeat with the Russia keyword list for `Russia_Metadata_Merged_2020-2024.csv`.)
