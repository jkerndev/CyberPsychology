import sqlite3
import pandas as pd
import numpy as np
from collections import defaultdict
from scipy.stats import fisher_exact
import statsmodels.formula.api as smf
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

# ——— 1. CONFIGURATION ———
DB_PATH = "PIIsurvey/instance/database.db"

# question weights
WEIGHTS = {
    **dict.fromkeys([1,2,3,11,12,13], 1),
    **dict.fromkeys([4,5,6,14,15,16], 2),
    **dict.fromkeys([7,8,9,17,18,19], 3),
}

# which majors count as “cyber‐aware”
CYBER_SET = {"computer science","information technology","cybersecurity"}

# ——— 2. LOAD & DE-DUPLICATE ———
conn = sqlite3.connect(DB_PATH)
query = """
SELECT
  r.participant_id,
  p.is_ai,
  LOWER(p.major)    AS major_lc,
  r.question_id,
  r.answered,
  r.skipped
FROM response_table r
JOIN (
    SELECT MIN(id) AS keep_id
    FROM response_table
    GROUP BY participant_id, question_id
) AS first_rows
  ON r.id = first_rows.keep_id
JOIN participant_table p
  ON r.participant_id = p.id
"""
df = pd.read_sql_query(query, conn)
conn.close()

# ——— 3. FISHER’S EXACT (WEIGHTED) ———
# tally answered/skipped by (is_ai, is_cyber) keys
data = defaultdict(lambda: [0,0])
for _, row in df.iterrows():
    w = WEIGHTS.get(row.question_id, 0)
    key = (bool(row.is_ai), row.major_lc in CYBER_SET)
    if row.answered:
        data[key][0] += w
    else:
        data[key][1] += w

def fisher_for(key_ai, key_nonai):
    a1, s1 = data[key_ai]
    a2, s2 = data[key_nonai]
    return fisher_exact([[a1, a2],
                         [s1, s2]])

# cyber‐majors only
or_cyber, p_cyber = fisher_for((True, True), (False, True))

# non-cyber‐majors only
or_other, p_other = fisher_for((True, False), (False, False))

# all participants
def sum_group(is_ai_flag):
    a = sum(data[(is_ai_flag, maj)][0] for maj in (True, False))
    s = sum(data[(is_ai_flag, maj)][1] for maj in (True, False))
    return a, s

aA, sA = sum_group(True)
aN, sN = sum_group(False)
or_all, p_all = fisher_exact([[aA, aN],
                              [sA, sN]])

print("Fisher’s exact results (weighted):")
print(f"  Cyber‐majors only:    OR = {or_cyber:.2f}, p = {p_cyber:.4f}")
print(f"  Non-cyber‐majors only: OR = {or_other:.2f}, p = {p_other:.4f}")
print(f"  All participants:     OR = {or_all:.2f}, p = {p_all:.4f}")
print()

# ——— 4. LOGISTIC REGRESSION WITH INTERACTION ———
# prepare regression dataframe
df["interface"] = df["is_ai"].astype(int)             # 1 = AI, 0 = static
df["cyber"]     = df["major_lc"].isin(CYBER_SET).astype(int)

# fit a GLM (binomial logit) with interaction
model = smf.glm(
    formula="answered ~ interface * cyber",
    data=df,
    family=sm.families.Binomial()
).fit()

print(model.summary())
print()

# ——— 5. EXTRACT ODDS RATIOS & CIs ———
params = model.params
conf   = model.conf_int()
or_df  = pd.DataFrame({
    "OR":       np.exp(params),
    "2.5% CI":  np.exp(conf[0]),
    "97.5% CI": np.exp(conf[1]),
    "p-value":  model.pvalues
})
print("Odds Ratios and 95% CIs:")
print(or_df)
print()

# ——— 6. MULTICOLLINEARITY (VIF) ———
X = model.model.exog
vif = pd.Series(
    [variance_inflation_factor(X, i) for i in range(X.shape[1])],
    index=model.model.exog_names
)
print("Variance Inflation Factors:")
print(vif)
print()

# ——— 7. PREDICTED-PROBABILITY RANGE ———
preds = model.predict()
print(f"Predicted probability range: {preds.min():.3f} to {preds.max():.3f}")
