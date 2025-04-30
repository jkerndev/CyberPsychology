import sqlite3
from collections import defaultdict
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import fisher_exact
import statsmodels.formula.api as smf
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

# ——— CONFIG ———
DB_PATH = "PIIsurvey/instance/database.db"   # ← update this

CYBER_SET = {"computer science", "information technology", "cybersecurity"}
WEIGHTS = {
    **dict.fromkeys([1,2,3,11,12,13], 1),
    **dict.fromkeys([4,5,6,14,15,16], 2),
    **dict.fromkeys([7,8,9,17,18,19], 3),
}

# ——— LOAD & DEDUPE ———
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("""
  SELECT r.id, r.participant_id, p.is_ai, LOWER(p.major) AS major_lc,
         r.question_id, r.answered, r.skipped
  FROM response_table r
  JOIN (
    SELECT MIN(id) AS keep_id
    FROM response_table
    GROUP BY participant_id, question_id
  ) AS fr ON r.id = fr.keep_id
  JOIN participant_table p ON r.participant_id = p.id
""", conn)
conn.close()

# ——— FISHER’S EXACT (WEIGHTED) ———
# tally weighted answers vs skips by (is_ai, is_cyber)
data = defaultdict(lambda: [0,0])
for _, row in df.iterrows():
    w = WEIGHTS.get(row.question_id, 0)
    key = (bool(row.is_ai), row.major_lc in CYBER_SET)
    data[key][0 if row.answered else 1] += w

def run_fisher(key_a, key_b):
    a1,s1 = data[key_a]
    a2,s2 = data[key_b]
    or_, p = fisher_exact([[a1,a2],[s1,s2]])
    return or_, p

or_cyber, p_cyber = run_fisher((True,True),(False,True))
or_other, p_other = run_fisher((True,False),(False,False))
aA = sum(data[(True,m)][0] for m in (True,False))
sA = sum(data[(True,m)][1] for m in (True,False))
aN = sum(data[(False,m)][0] for m in (True,False))
sN = sum(data[(False,m)][1] for m in (True,False))
or_all, p_all = fisher_exact([[aA,aN],[sA,sN]])

fisher_df = pd.DataFrame({
    "Group": ["Cyber-aware","Non-cyber-aware","All"],
    "OR":    [or_cyber, or_other, or_all],
    "p-value":[p_cyber, p_other, p_all]
})
print("\nWeighted Fisher’s Exact Test Results:")
print(fisher_df.to_string(index=False))

# — Plot Fisher ORs — 
plt.figure()
plt.bar(fisher_df["Group"], fisher_df["OR"])
plt.axhline(1, linestyle="--")
plt.title("Fisher’s Exact Test Odds Ratios")
plt.ylabel("OR (answered vs skipped)")
plt.tight_layout()
plt.show()


# ——— LOGISTIC REGRESSION ———
df["interface"] = df["is_ai"].astype(int)      # 1=AI, 0=static
df["cyber"]     = df["major_lc"].isin(CYBER_SET).astype(int)
model = smf.glm("answered ~ interface * cyber",
                data=df, family=sm.families.Binomial()).fit()

# ORs + 95% CIs
params = model.params
conf   = model.conf_int()
logit_df = pd.DataFrame({
    "OR":       np.exp(params),
    "2.5% CI":  np.exp(conf[0]),
    "97.5% CI": np.exp(conf[1]),
    "p-value":  model.pvalues
})
print("\nLogistic Regression ORs & 95% CIs:")
print(logit_df)

# — Plot logistic ORs w/ error bars —
plt.figure()
errs = np.vstack([
    logit_df["OR"] - logit_df["2.5% CI"],
    logit_df["97.5% CI"] - logit_df["OR"]
])
plt.errorbar(logit_df.index, logit_df["OR"], yerr=errs, fmt="o")
plt.axhline(1, linestyle="--")
plt.title("Logistic Regression Odds Ratios")
plt.ylabel("OR")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# ——— PREDICTED PROBABILITIES ———
pred = pd.DataFrame({
    "interface": [0,1,0,1],
    "cyber":     [0,0,1,1]
})
pred["p_answer"] = model.predict(pred)
pred["Group"] = ["Non-cyber Static","Non-cyber AI","Cyber Static","Cyber AI"]
print("\nPredicted Probability of Answering by Group:")
print(pred[["Group","p_answer"]])

# — Plot predicted probabilities —
plt.figure()
plt.plot(pred["Group"], pred["p_answer"], marker="o")
plt.title("Predicted Answering Probability")
plt.ylabel("P(answer)")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
