Getting Started
===============

Hey! Welcome to my checkout flow optimization project. I built this A/B testing framework to address a common challenge in e-commerce, how do you know if your checkout improvements actually work? This guide will get you up and running quickly.

What You'll Need
----------------

I've kept the requirements pretty minimal:

* **Python 3.8+** - I tested this on Python 3.8 and up
* **Git** - You'll need this to clone the repo
* **Make** - Most systems have this already, but if you're on Windows you might need to install it

System Specs
~~~~~~~~~~~~

* **RAM**: 4GB minimum, but 8GB+ makes it much smoother
* **Storage**: About 1GB for all the data and dependencies
* **OS**: Works great on macOS and Linux, Windows users should use WSL

Let's Get You Set Up
--------------------

Here's how I usually set this up on a fresh machine:

1. **Grab the Code**
   .. code-block:: bash
   
      git clone https://github.com/nandinisankarabukta-git/checkout-flow-optimization.git
      cd checkout-flow-optimization

2. **Set Up Your Python Environment**
   .. code-block:: bash
   
      python -m venv .venv
      source .venv/bin/activate  # On Windows: .venv\Scripts\activate

3. **Install Everything You Need**
   .. code-block:: bash
   
      make requirements

   This pulls in all the good stuff I use:
   - DuckDB (my favorite for fast analytics)
   - Streamlit (makes the dashboard super easy)
   - SciPy/Statsmodels (for the heavy statistical lifting)
   - Pandas (because who doesn't love pandas?)

4. **Make Sure Everything Works**
   .. code-block:: bash
   
      make test_environment

The Magic Command
-----------------

Once you're set up, here's the one command that does everything:

.. code-block:: bash
   
   make pipeline

This is my favorite part, it just works! Here's what happens behind the scenes:
1. Generates realistic checkout data (I spent way too much time making this look real)
2. Builds the DuckDB warehouse (so fast!)
3. Creates all the analytical tables
4. Runs my data quality checks
5. Does all the statistical heavy lifting
6. Spits out a beautiful report

Takes about 3 minutes on my laptop, should be similar for you.

Check Out the Dashboard
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash
   
   make app

Then head to `http://localhost:8501` - I'm pretty proud of how this turned out. You can explore all the metrics interactively and see exactly what's happening with your experiment.

Your First Run
---------------

Here's what I do when I want to see results:

1. **Fire Up the Pipeline**
   .. code-block:: bash
   
      make pipeline

2. **Dig Into the Results**
   - `reports/REPORT.md` - This is where I put the executive summary (boss-friendly)
   - `make app` - The interactive dashboard I mentioned
   - `reports/results/` - All the raw numbers if you want to get nerdy

3. **Peek Under the Hood**
   - `data/raw/` - The synthetic data I generate (partitioned by date)
   - `duckdb/warehouse.duckdb` - The database where all the magic happens
   - `notebooks/` - My analysis notebooks if you want to see how I think through problems

What You're Looking At
----------------------

When the pipeline finishes, you'll see:

* **CCR (Conditional Conversion Rate)** - This is the main thing I care about. Did more people actually buy stuff?
* **Statistical Tests** - I use proper z-tests with confidence intervals (no p-hacking here!)
* **Guardrails** - Making sure we didn't break anything important like payment success
* **The Decision** - Clear "ship it" or "don't ship it" recommendation

Files I Generate for You
~~~~~~~~~~~~~~~~~~~~~~~~

* `reports/REPORT.md` - The executive summary (I spent time making this readable)
* `reports/results/ccr_summary.json` - The main metric results
* `reports/results/guardrails_summary.json` - Safety check results
* `reports/results/variant_funnel.csv` - Detailed breakdown of each step

Troubleshooting
--------------------

I've run into these issues myself, so here's how I fix them:

**Python Version Problems**
   .. code-block:: bash
   
      python --version  # Should be 3.8+
      # If not, install Python 3.8+ or use pyenv

**Virtual Environment Acting Up**
   .. code-block:: bash
   
      deactivate
      rm -rf .venv
      python -m venv .venv
      source .venv/bin/activate
      make requirements

**DuckDB Being Stubborn**
   .. code-block:: bash
   
      make clean
      make pipeline

**Windows Being Windows**
   - Run Command Prompt as Administrator
   - Or use WSL (I highly recommend this)

**Still Stuck?**

* `README.md` - I put the project overview here
* `docs/commands.rst` - All the commands I built
* `notebooks/` - My analysis notebooks (might give you ideas)
* `src/` - The actual code if you want to see how I did things

What's Next?
------------

Once you've got the basics working:

1. **Tweak the Experiment** - Edit `configs/experiment.yml` to match your needs
2. **Power Analysis** - `make sensitivity` tells you how many users you need
3. **Dive Deeper** - Check out `notebooks/` for more advanced stuff
4. **Make It Your Own** - Modify `src/data/simulate.py` for different scenarios

Want to know about all the commands I built? Check out :doc:`commands` - I documented everything!
