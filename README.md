# This is a tool for extracting tickets details from data pulled from Jira using API through browser

## Usage

### Filter issues by sprint word

```commandline
python extract_jira_data.py idp-data1.json idp-data2.json output.csv --sprint-filter "DEVOPS"
```
### Omit issues with not sprint information

```commandline
python extract_jira_data.py idp-data1.json idp-data2.json output.csv --omit-outside-sprint
```