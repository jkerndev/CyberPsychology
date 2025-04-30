import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

# ——— 1. Load & de-duplicate ———
DB = "PIIsurvey/instance/database.db"
conn = sqlite3.connect(DB)

query = """
SELECT
  r.participant_id,
  p.is_ai,
  LOWER(p.major) AS major_lc,
  r.question_id,
  r.answered,
  r.skipped
FROM response_table r
JOIN (
    SELECT MIN(id) AS keep_id
    FROM response_table
    GROUP BY participant_id, question_id
) AS first_rows ON r.id = first_rows.keep_id
JOIN participant_table p ON r.participant_id = p.id
"""
df = pd.read_sql_query(query, conn)
conn.close()

# ——— 2. Map to PII category & major group ———
category_map = {
    1:"age",11:"age",
    2:"biological sex",12:"biological sex",
    3:"time online/week",13:"time online/week",
    4:"name",14:"name",
    5:"race/ethnicity",15:"race/ethnicity",
    6:"personal email",16:"personal email",
    7:"postal address",17:"postal address",
    8:"phone number",18:"phone number",
    9:"SSN",19:"SSN",
}
CYBER_SET = {"computer science","information technology","cybersecurity"}

df["category"] = df["question_id"].map(category_map)
df["major_group"] = df["major_lc"].apply(
    lambda m: "Cyber-aware" if m in CYBER_SET else "Non-cyber-aware"
)

# ——— 3. Count participants in each major group & overall ———
participants = df[["participant_id","major_group"]].drop_duplicates()
counts = participants["major_group"].value_counts().to_dict()
counts["All"] = participants["participant_id"].nunique()

# ——— 4. Build answered & skipped counts by category & major_group ———
# answered:
ans = (
    df[df.answered == 1]
      .groupby(["category","major_group"])
      .size()
      .unstack(fill_value=0)
)
# skipped:
skp = (
    df[df.skipped == 1]
      .groupby(["category","major_group"])
      .size()
      .unstack(fill_value=0)
)

# ensure both columns exist on each
for tbl in (ans, skp):
    for grp in ("Cyber-aware","Non-cyber-aware"):
        if grp not in tbl.columns:
            tbl[grp] = 0
# add overall column as sum of the two groups
ans["All"] = ans.sum(axis=1)
skp["All"] = skp.sum(axis=1)

# ——— 5. Convert to proportions ———
ans_prop = ans.copy()
skp_prop = skp.copy()
for grp in ("Cyber-aware","Non-cyber-aware","All"):
    ans_prop[grp] /= counts[grp]
    skp_prop[grp] /= counts[grp]

# ——— 6. Per-participant answered counts & summary stats ———
per_part = (
    df.pivot_table(
      index="participant_id",
      columns="major_group",
      values="answered",
      aggfunc="sum",
      fill_value=0
    )
)
# ensure both columns exist
for grp in ("Cyber-aware","Non-cyber-aware"):
    if grp not in per_part.columns:
        per_part[grp] = 0
per_part["All"] = per_part["Cyber-aware"] + per_part["Non-cyber-aware"]

stats = {
    grp: {
      "mean": per_part[grp].mean(),
      "std":  per_part[grp].std()
    }
    for grp in ("All","Cyber-aware","Non-cyber-aware")
}

# ——— 7. Print proportion tables & stats ———
pd.set_option("display.precision", 3)

print("\n% Answered per PII category:")
print(ans_prop)

print("\n% Skipped per PII category:")
print(skp_prop)

print("\n# Answered per participant (mean ± std):")
for grp, v in stats.items():
    print(f"  {grp:17}: {v['mean']:.2f}  ± {v['std']:.2f}")

# ——— 8. Plot answered proportions ———
plt.figure(figsize=(10,6))
ans_prop[["Cyber-aware","Non-cyber-aware","All"]].plot(
    kind="bar", rot=45, xlabel="PII Category", ylabel="Proportion Answered"
)
plt.title("Proportion of Participants Who Answered, by PII Category & Major Group")
plt.legend(title="Group")
plt.tight_layout()
plt.show()

# ——— 9. Plot skipped proportions ———
plt.figure(figsize=(10,6))
skp_prop[["Cyber-aware","Non-cyber-aware","All"]].plot(
    kind="bar", rot=45, xlabel="PII Category", ylabel="Proportion Skipped"
)
plt.title("Proportion of Participants Who Skipped, by PII Category & Major Group")
plt.legend(title="Group")
plt.tight_layout()
plt.show()
