# Evident Engine — Quick Start (Hindi/Hinglish)

### Start kaise karein
1. ZIP ko extract karo.
2. `START_EVIDENT.bat` double-click karo.
3. First run par virtual environment aur dependencies install hongi; ismein kuch time lag sakta hai.
4. Browser automatic open hoga; nahi toh `http://127.0.0.1:8765` kholo.
5. Configuration mein API base URL, API key aur model ID set karke save karo.
6. Optional live web search ke liye server band karo, `.env` mein `TAVILY_API_KEY` set karo, phir app restart karo.

### Language
Workspace query response auto-detect kar sakta hai. Language override mein Hindi (Devanagari), Roman Hinglish, English ya Auto choose karo.

### Tabs
Overview, Intelligence Workspace, Verification Room, Evidence Explorer, Stability Lab, Audit History, Configuration.

### API usage/cost
Quick review 2 model calls, Balanced 3, Deep 4. Stability Lab har run mein 4 calls karta hai. API provider ke usage charges lag sakte hain.

### Important limitation
Stability Lab 4 live model-response conditions run karta hai (baseline, paraphrase, missing-evidence prompt, hypothetical contradiction), experiment history save karta hai, aur ek lexical-overlap metric dikhata hai. Ye correctness/semantic stability score nahi hai; ground-truth scoring abhi included nahi. Query review AI provider ke bina nahi chalega. Search ke liye Tavily key optional hai. AI confidence label calibrated probability nahi hai.

### Local privacy
API key and saved query history local `evident.db` file mein store hote hain; database encryption nahi hai. Folder private rakho.
