# Streamlit Community Cloud Deployment Guide

*How to deploy the Checkout Flow Optimization dashboard for your portfolio*

---

## Prerequisites

✅ GitHub account  
✅ Repository pushed to GitHub (public or private)  
✅ Streamlit Community Cloud account (free at [share.streamlit.io](https://share.streamlit.io))

---

## Step-by-Step Deployment

### 1. Prepare Your Repository

Ensure these files are committed and pushed to GitHub:

```
checkout-flow-optimization/
├── src/dashboard.py          # Main Streamlit app
├── requirements.txt           # Python dependencies
├── Makefile                   # Build commands
├── configs/                   # Experiment configuration
├── sql/                       # Database schemas and marts
├── src/data/simulate.py       # Data generator
└── README.md                  # Project documentation
```

**Important:** Make sure your repository is pushed to GitHub:
```bash
git add .
git commit -m "Prepare for Streamlit deployment"
git push origin main
```

### 2. Sign Up for Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **"Sign up with GitHub"**
3. Authorize Streamlit to access your GitHub account
4. Accept terms of service

### 3. Create New App

1. Click **"New app"** button
2. Fill in the deployment form:

   **Repository:**
   - Select: `yourusername/checkout-flow-optimization`
   
   **Branch:**
   - Select: `main`
   
   **Main file path:**
   - Enter: `src/dashboard.py`
   
   **App URL (optional):**
   - Custom: `checkout-flow-optimization` (if available)
   - Or let Streamlit auto-generate: `yourusername-checkout-flow-optimization`

3. Click **"Deploy!"**

### 4. Wait for Build

Streamlit will:
1. Clone your repository
2. Install dependencies from `requirements.txt`
3. Run the app
4. Show build logs in real-time

**Expected build time:** 2-3 minutes

### 5. Verify Deployment

Once deployed, you'll see:
- ✅ Green "Running" status
- 🌐 Public URL: `https://checkout-flow-optimization.streamlit.app`
- 👀 Live preview of your dashboard

**Test the app:**
1. Navigate to Overview tab → Should see key metrics cards
2. Click Summary tab → Should see variant funnel data
3. Click Diagnostics tab → Should see step-through rates
4. Click Sensitivity tab → Should see "not yet run" message (until you run `make sensitivity`)

---

## Important Configuration Notes

### Running `make pipeline` on Streamlit Cloud

**Challenge:** Streamlit Cloud doesn't have `make` installed by default.

**Solution 1: Pre-generate Data (Recommended for Demo)**

Before deploying, run locally and commit generated data:

```bash
# Generate data locally
make pipeline

# Add generated files to git (normally ignored)
git add -f duckdb/warehouse.duckdb
git add -f reports/REPORT.md
git add -f reports/results/*.json
git add -f reports/results/*.csv

# Commit
git commit -m "Add pre-generated data for Streamlit Cloud"
git push origin main
```

Then redeploy on Streamlit Cloud - it will use the committed data files.

**Solution 2: Run Pipeline on App Startup**

Add a startup script that runs the pipeline automatically:

Create `.streamlit/config.toml`:
```toml
[server]
runOnSave = false
```

Modify `src/dashboard.py` to check if data exists and generate if not:

```python
import subprocess
from pathlib import Path

# At the top of dashboard.py, before st.set_page_config
db_path = Path("duckdb/warehouse.duckdb")
if not db_path.exists():
    with st.spinner("First-time setup: Generating sample data..."):
        subprocess.run(["python", "src/data/simulate.py", "--days", "4", "--users", "10000"])
        subprocess.run(["python", "-c", "import duckdb; duckdb.connect('duckdb/warehouse.duckdb')"])
        # ... run other setup steps
```

**Solution 3: Streamlit Secrets for Make Alternative**

If you want to use `make` commands, create a bootstrap script:

```bash
# .streamlit/setup.sh
#!/bin/bash
if [ ! -f "duckdb/warehouse.duckdb" ]; then
    python src/data/simulate.py --days 4 --users 10000
    # Run remaining pipeline steps
fi
```

### Memory Limits

Streamlit Community Cloud provides:
- **Free tier:** 1 GB RAM
- **Shared resources:** CPU-limited

**Optimization tips:**
1. Keep simulated data small (`--days 4 --users 10000`)
2. Use smaller sample sizes for sensitivity analysis
3. Cache expensive computations with `@st.cache_data`
4. Consider upgrading to Streamlit Enterprise for larger datasets

---

## Managing Your App

### Update Your Deployment

Any push to the `main` branch automatically redeploys:

```bash
git add src/dashboard.py
git commit -m "Update dashboard styling"
git push origin main
```

Streamlit Cloud detects the push and rebuilds (2-3 minutes).

### View Logs

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click on your app
3. Click **"Manage app"**
4. View real-time logs in "Logs" tab

### Reboot App

If your app is stuck or needs a fresh start:
1. Click **"Manage app"**
2. Click **"Reboot app"** (cloud icon)
3. Wait for restart (~30 seconds)

### Delete App

To remove your deployment:
1. Click **"Manage app"**
2. Scroll to bottom
3. Click **"Delete app"**
4. Confirm deletion

---

## Custom Domain (Optional)

Streamlit Community Cloud provides a free `.streamlit.app` subdomain.

For a custom domain (e.g., `analytics.yourdomain.com`):
1. Upgrade to **Streamlit Enterprise** (paid)
2. Configure DNS CNAME record
3. Add custom domain in Streamlit settings

---

## Sharing Your Dashboard

### For Portfolio Use

Add the Streamlit URL to:

**1. GitHub README:**
```markdown
## 🌐 Live Demo

**Dashboard:** [View Live Dashboard](https://checkout-flow-optimization.streamlit.app)
```

**2. LinkedIn Profile:**
- Add to "Featured" section
- Include in project description
- Link in posts

**3. Resume/CV:**
```
Checkout Flow Optimization | A/B Testing Framework
• Live Dashboard: checkout-flow-optimization.streamlit.app
• GitHub: github.com/yourusername/checkout-flow-optimization
```

**4. Portfolio Website:**
```html
<a href="https://checkout-flow-optimization.streamlit.app" target="_blank">
  View Live Dashboard
</a>
```

### Privacy Settings

**Public Apps (Default):**
- Anyone with the URL can access
- App is discoverable on Streamlit Community Cloud
- Best for portfolio/demo purposes

**Private Apps (Requires Authentication):**
- Viewers must sign in with email
- Managed via Streamlit settings
- Good for internal team demos

---

## Troubleshooting

### Issue: "FileNotFoundError: duckdb/warehouse.duckdb"

**Cause:** Database file doesn't exist on Streamlit Cloud.

**Solution:** Either:
1. Commit `duckdb/warehouse.duckdb` to git (temporary for demo)
2. Add startup logic to generate database if missing

### Issue: "ModuleNotFoundError: No module named 'X'"

**Cause:** Missing dependency in `requirements.txt`.

**Solution:**
```bash
pip freeze > requirements.txt
git add requirements.txt
git commit -m "Update dependencies"
git push
```

### Issue: "MemoryError" or "Killed"

**Cause:** App exceeds 1 GB RAM limit.

**Solution:**
1. Reduce simulated data size (`--days 2 --users 5000`)
2. Use `@st.cache_data` to avoid recomputation
3. Consider Streamlit Enterprise for higher limits

### Issue: App is slow to load

**Cause:** Large data files or expensive computations on startup.

**Solution:**
1. Pre-compute results and commit to repo
2. Use `@st.cache_resource` for database connections
3. Lazy-load data (only fetch what's needed)
4. Show loading spinners for better UX

---

## Example: Full Deployment Workflow

```bash
# 1. Ensure repository is ready
git status
git add .
git commit -m "Prepare for Streamlit deployment"
git push origin main

# 2. Generate sample data locally
make pipeline

# 3. Commit generated data for demo
git add -f duckdb/warehouse.duckdb
git add -f reports/REPORT.md
git add -f reports/results/*.json
git commit -m "Add sample data for Streamlit Cloud"
git push origin main

# 4. Deploy on Streamlit Cloud
# - Visit share.streamlit.io
# - Click "New app"
# - Select repo: checkout-flow-optimization
# - Branch: main
# - Main file: src/dashboard.py
# - Click "Deploy"

# 5. Wait 2-3 minutes for build

# 6. Visit your live URL!
# https://checkout-flow-optimization.streamlit.app
```

---

## Acceptance Criteria

✅ Dashboard runs online at stable URL  
✅ Overview tab loads with key metrics  
✅ All four tabs (Overview, Summary, Diagnostics, Sensitivity) render correctly  
✅ No critical errors in Streamlit logs  
✅ URL is suitable for portfolio (shareable, professional)  
✅ App performs well under normal usage  

---

## Next Steps

Once deployed:

1. **Update docs/portfolio_writeup.md:**
   - Replace `https://checkout-flow-optimization.streamlit.app` placeholder with actual URL

2. **Add badge to README.md:**
   ```markdown
   [![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://checkout-flow-optimization.streamlit.app)
   ```

3. **Share on LinkedIn:**
   - Post about your project
   - Include live dashboard link
   - Tag relevant topics (#DataScience #ABTesting #Python)

4. **Monitor usage:**
   - Check Streamlit analytics
   - Review logs for errors
   - Collect feedback

---

*Happy deploying! 🚀*

*For questions or issues, see [Streamlit Community Cloud Docs](https://docs.streamlit.io/streamlit-community-cloud)*

