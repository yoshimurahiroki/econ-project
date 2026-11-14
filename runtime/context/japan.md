# Japan

Country context for questions about the Japanese economy. Check current values (policy rates, thresholds, base years) at the source before using them; this file names where they live and which conventions trip analyses.

## Data sources

| Area | Source | Notes |
| --- | --- | --- |
| Portal for official statistics | e-Stat (`research_data.py acquire`, provider `estat`, needs `ESTAT_APP_ID`) | most government tables by statsDataId |
| Population | Population Census (国勢調査, every five years, 1 October), population estimates (人口推計) | municipal boundaries change with mergers |
| Labour market | Labour Force Survey (労働力調査, monthly), Employment Status Survey (就業構造基本調査, every five years), employment referrals (職業安定業務統計: openings-to-applicants ratio) | regular and non-regular employment are separate categories |
| Wages and hours | Monthly Labour Survey (毎月勤労統計), Basic Survey on Wage Structure (賃金構造基本統計調査, June wages) | sample rotation and the 2019 irregularity revisions create breaks; bonuses arrive in summer and winter |
| Prices | CPI (消費者物価指数, base revised every five years), CGPI and SPPI (Bank of Japan) | use one base year per series; check the core definitions in use |
| National accounts | SNA by the Cabinet Office ESRI (quarterly QE and annual benchmarks) | QE revisions are large; record the vintage |
| Firms | Financial Statements Statistics of Corporations (法人企業統計, MOF), Economic Structure surveys (経済構造実態調査), Tankan (Bank of Japan) | firm-size classes follow capital thresholds |
| Money and finance | Bank of Japan time series: money stock, flow of funds, interest rates; DBnomics provider `BOJ` | |
| Research series | DBnomics providers `ESRI`, `METI`, `JILPT`; RIETI and Bank of Japan discussion papers for prior estimates | |
| Microdata | secondary use of survey records under the Statistics Act (調査票情報の二次利用), anonymized data, on-site facilities | application and access conditions go into the project context |

## Institutions that shape identification

- **Fiscal year** runs April to March; budgets, firm accounts and many administrative series use it. State calendar or fiscal year in every variable.
- **Minimum wages** are set by prefecture and revised once a year, usually effective in October, after national guidance that groups prefectures into ranks; the rank and the effective date matter for timing.
- **Wage setting** follows the spring wage negotiations (春闘) and seniority-linked pay at large firms; summer and winter bonuses move monthly earnings.
- **Employment categories** (regular, non-regular, dispatched, part-time) differ in protection, social insurance and wages; many policies apply to one category.
- **Tax and social-insurance income thresholds** create bunching in spouses' and part-timers' earnings; the thresholds have been revised, so the applicable year's values are read from the source.
- **Monetary policy**: the Bank of Japan ended negative interest rates and yield-curve control in 2024; long samples cross the zero-lower-bound, quantitative easing and normalization regimes.
- **Local government**: 47 prefectures and about 1,700 municipalities; boundary changes from municipal mergers require a fixed-boundary crosswalk for panels.

## Conventions

- Convert Japanese era years (和暦) to calendar years at loading and keep the original field.
- Use official seasonally adjusted series as published and record the adjustment method; do not mix adjusted and unadjusted series in one comparison.
- Monetary amounts in yen; state nominal or real with the deflator and base year.
- Japanese output follows the academic-ja profile; variable names and table labels keep the official Japanese term next to the English one in the data dictionary.
