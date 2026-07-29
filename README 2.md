# MJ Bets 26 Pro v4

A mobile-first Streamlit football prediction dashboard.

## New in v4

- Bet of the Day banner
- Top three correct-score probabilities
- Colour confidence bars
- BTTS Yes/No selection and confidence
- Over/Under 2.5 selection and confidence
- Model accumulator builder
- Improved mobile layout

## Model inputs

- Recent completed matches
- Home and away form
- Goals scored and conceded
- Current league standings where available
- Head-to-head meetings within available season data
- Poisson score model

## Install

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Streamlit secret

Keep the key in Streamlit Community Cloud **Secrets**, not GitHub:

```toml
FOOTBALL_DATA_API_KEY = "your-key"
```

## Upload to GitHub

Upload every file in this package to the repository root and replace the existing files. Do not upload a real `.streamlit/secrets.toml` file.

## Important

Predictions are estimates, not guarantees. API coverage varies by plan and competition.
