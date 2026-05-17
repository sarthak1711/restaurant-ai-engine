Day 1 - Environment setup. WSL2, Python 3.10, PostgreSQL, FastAPI installed. 
First endpoint live at localhost:8000. GitHub repo created and first commit pushed.

Day 2 - Built database schema (5 tables: restaurants, orders, daily_revenue, customers, campaigns).
Seeded 6 months of realistic mock data with lull periods, peak periods, holiday recovery,
day-of-week patterns, and repeat vs new customer ratio. 60,345 orders generated.

Day 3 - Built revenue analyzer. Detects lull conditions by comparing 7-day average vs 
30-day baseline. Three severity levels: mild, moderate, severe. Wired into FastAPI endpoint.
Fixed bug: campaign query was returning future campaigns — fixed at root cause in SQL, not with abs().

Day 4 - Integrated Claude API. Campaign generator reads revenue analysis and generates 
personalized discount emails. Culturally aware output (Hindi-English for IN restaurants).
Correct no-send decision during peak periods.
Identified architectural issue: currently passing pre-computed lull flag to Claude instead 
of raw data. Claude should reason over raw signals, not pre-computed verdicts.
Next: refactor to Level 2 — pass raw revenue data and let Claude decide.