# Backend Scripts

This directory contains utility scripts for the Foresight AI pipeline.

## Classification Accuracy Validation

The `validate_classification.py` script helps validate AI classification accuracy by facilitating the manual review of 100 random cards.

### Prerequisites

1. Backend API running at `http://localhost:8000` (or configure `API_BASE_URL`)
2. Valid API authentication token (configure `API_TOKEN`)
3. Python 3.11+ with aiohttp installed

### Usage

#### 1. Check Current Accuracy

View the current classification accuracy statistics:

```bash
python -m scripts.validate_classification --mode accuracy
```

#### 2. Interactive Validation

Validate cards one at a time with an interactive CLI:

```bash
python -m scripts.validate_classification --mode interactive --count 100
```

For each card, you'll:
- See the card's name, summary, and predicted pillar
- Enter the correct pillar code (CH, EW, HG, HH, MC, PS)
- Optionally add notes explaining your decision

#### 3. Batch Export/Import

For offline review or team-based validation:

**Export cards for review:**
```bash
python -m scripts.validate_classification --mode export --count 100 --output cards_to_review.json
```

**After manual review, import the labels:**
```bash
python -m scripts.validate_classification --mode import --input reviewed_cards.json
```

#### 4. Generate Report

Generate a comprehensive validation report:

```bash
python -m scripts.validate_classification --mode report --output validation_report.md
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--mode` | Operation mode: interactive, export, import, accuracy, report | accuracy |
| `--count` | Number of cards to process | 100 |
| `--days` | Number of days to look back | 7 |
| `--output` | Output file path (for export/report) | - |
| `--input` | Input file path (for import) | - |
| `--api-url` | Backend API URL | http://localhost:8000 |
| `--api-token` | API authentication token | - |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `API_BASE_URL` | Backend API URL |
| `API_TOKEN` | Authentication token |
| `REVIEWER_ID` | Identifier for the reviewer |

### Strategic Pillar Codes

| Code | Pillar Name |
|------|-------------|
| CH | Community Health & Sustainability |
| EW | Economic & Workforce Development |
| HG | High-Performing Government |
| HH | Homelessness & Housing |
| MC | Mobility & Critical Infrastructure |
| PS | Public Safety |

### Validation Workflow

1. **Preparation**
   - Ensure the pipeline has run and generated cards
   - Have access to pillar definitions for reference

2. **Validation**
   - Use interactive mode or export/import for batch review
   - For each card, read the summary and determine the correct pillar
   - Submit ground truth labels via the API

3. **Analysis**
   - Run accuracy mode to check current metrics
   - Generate a report for documentation
   - Identify pillars with low accuracy for improvement

4. **Sign-off**
   - Verify accuracy meets >85% target
   - Document findings in the validation report
   - Submit for QA review

### API Endpoints Used

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/validation/pending` | GET | Get cards needing validation |
| `/api/v1/validation/submit` | POST | Submit ground truth label |
| `/api/v1/validation/accuracy` | GET | Get overall accuracy metrics |
| `/api/v1/validation/accuracy/by-pillar` | GET | Get per-pillar breakdown |

### Troubleshooting

**No cards found:**
- Check that the pipeline has run recently
- Verify cards have `pillar_id` set
- Check API authentication

**Validation submission fails:**
- Verify the card ID exists
- Check that pillar code is valid
- Ensure no duplicate validation for same card/reviewer

**Accuracy not computed:**
- Need at least one validation with `is_correct` determined
- Cards without predicted pillars are excluded

### Example Output

```
============================================================
Classification Accuracy Report
============================================================

Overall Accuracy:
  Total Validations: 100
  Correct: 87
  Accuracy: 87.00%
  Target: 85.0%
  Meets Target: Yes

Accuracy by Pillar:
--------------------------------------------------
  CH (Community Health & Sustainability): 90.0% (20 validations)
  EW (Economic & Workforce Development): 85.0% (20 validations)
  HG (High-Performing Government): 88.0% (25 validations)
  HH (Homelessness & Housing): 80.0% (10 validations)
  MC (Mobility & Critical Infrastructure): 85.0% (15 validations)
  PS (Public Safety): 90.0% (10 validations)

Top Misclassifications:
--------------------------------------------------
  HG predicted as EW: 3 times
  CH predicted as PS: 2 times
```
