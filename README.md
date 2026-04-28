# NYT Identity Construction: China & Russia Coverage (2020–2024)

Replication code for the thesis *How Does The New York Times Construct American National Identity in Its Coverage of the United States, China, and Russia?* (Luo, 2026).

This repository contains the data-collection pipeline and the analysis notebooks used to produce every figure, table, and statistic reported in the thesis. The corpus itself is not distributed (see [Data](#data) below).

## Repository structure

```
.
├── README.md                              this file
├── LICENSE                                MIT License
├── requirements.txt                       Python dependencies
├── .gitignore
├── EDA.ipynb                              §4 macro-structural analysis
├── Main_Part.ipynb                        §5–§7 China-coverage analysis
├── Data/
│   └── README.md                          (data not redistributed)
└── scraping/
    ├── nyt_scraper.py                     NYT Archive API + full-text scraper
    ├── combined_china_keywords.csv        keyword list for China subset
    └── combined_russia_keywords.csv       keyword list for Russia subset
```

## What's in each notebook

| Notebook | Section | Outputs |
| --- | --- | --- |
| `EDA.ipynb` | §4 (macro-structural analysis) | Figures 1, 2, 3, 4 + Appendix A1 + Appendix B1, B2 |
| `Main_Part.ipynb` | §5–§7 (sentiment, emotion, identity lexicons, word embeddings) | Figures 5–17 + Appendix C (Table C1) + the regression results in §5.7 |

Each notebook opens with a contents table mapping every code block to a figure or table in the manuscript.

## Reproducing the analysis

### 1. Install dependencies

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"
```

GPU strongly recommended for `Main_Part.ipynb` — the notebook trains transformer pipelines (DistilBERT for sentiment, j-hartmann/emotion-english-distilroberta-base for emotion) and 10-iteration Word2Vec bootstraps. CPU runtime is several hours; GPU is ~30 minutes.

### 2. Rebuild the corpus

The corpus is not distributed in this repository (see [Data](#data) below). To regenerate it:

```bash
export NYT_API_KEY=your_key_here    # get one at https://developer.nytimes.com

# China subset, year by year
python scraping/nyt_scraper.py --start 2020-01 --end 2020-12 \
    --keywords scraping/combined_china_keywords.csv
python scraping/nyt_scraper.py --start 2021-01 --end 2021-12 \
    --keywords scraping/combined_china_keywords.csv
# ...repeat through 2024

# Russia subset, year by year
python scraping/nyt_scraper.py --start 2020-01 --end 2020-12 \
    --keywords scraping/combined_russia_keywords.csv
# ...repeat through 2024
```

Concatenate the per-year CSVs into the merged files the notebooks expect:

- `Data/China_Metadata_Merged_2020-2024.csv`
- `Data/Russia_Metadata_Merged_2020-2024.csv`
- `Data/China_Fulltext_Merged_2020-2024.csv`

Full-text scraping for ~12,000 articles takes 12–24 hours on a single machine. The scraper requires being logged into nytimes.com in a local Chrome profile (it uses `browser_cookie3` to read session cookies).

### 3. Run the notebooks

Open `EDA.ipynb` and Run All (~5 minutes). This produces the §4 figures and writes `Data/NYT_Master_Cleaned_2020-2024.csv` for downstream use.

Open `Main_Part.ipynb` and Run All. This produces the §5–§7 figures, the Appendix C table, and intermediate files (`Yearly_Changes_Expanded.csv`, `NYT_Identity_Final_Results.csv`, `Final_Geometry_Plot.png`).

## Data

The corpus is not distributed in this repository, for two reasons:

1. The full-text file (~250 MB across 5,396 articles) exceeds GitHub size limits.
2. Article body text is copyrighted by The New York Times and cannot be redistributed.

The metadata files derive from the publicly available NYT Archive API and could in principle be redistributed, but for consistency with the full-text restriction this repository contains code only. The thesis itself reports all aggregated statistics, figures, and tables derived from the corpus.

To rebuild the corpus, follow step 2 in [Reproducing the analysis](#reproducing-the-analysis). A NYT Developer API key (free) and an active NYT subscription (for paywalled content) are required.

## Note on outputs and reproducibility

Cell outputs have been stripped from both notebooks to keep file sizes small and avoid embedding large image blobs. Running all cells reproduces the figures end-to-end.

Two analyses involve stochastic components: the sentence-level disaggregation in §5.4 draws a random 20,000-sentence sample, and the Word2Vec models in §7 are trained with multi-core parallelism. Re-running these cells produces results within ±0.01 of the thesis numbers but not exact bitwise replicas. The figures and exact statistics reported in the manuscript correspond to a specific run preserved in the author's working directory.

## Citation

If you use this code, please cite the thesis:

```
Luo, Jiahang. (2026). How Does The New York Times Construct American National
Identity in Its Coverage of the United States, China, and Russia? MA thesis,
University of Chicago, Master of Arts Program in Computational Social Science.
```

## License

MIT License — see [LICENSE](LICENSE).

## Contact

Jiahang Luo — jiahangluo@icloud.com
